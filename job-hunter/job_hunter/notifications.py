"""Send a digest of newly-found eligible jobs to Telegram, a webhook
(Slack/Discord-compatible), and/or email.

Every channel is best-effort and independent: a failing channel is reported
back in the result dict rather than raising, so `job-hunter discover` (or
`watch`) never crashes because a webhook URL is stale. Nothing is sent, and
no error is raised, for channels that aren't configured.
"""

from __future__ import annotations

import smtplib
import sqlite3
from email.mime.text import MIMEText

import httpx

from job_hunter.config import NotificationConfig

MAX_JOBS_IN_DIGEST = 25


def _format_job_line(job: sqlite3.Row) -> str:
    loc = f" · {job['location'][:30]}" if job["location"] else ""
    score = f" · fit {job['score']}/100" if job["score"] else ""
    return f"• {job['title']} @ {job['company']} ({job['board']}){loc}{score}\n  {job['url']}"


def _digest_text(jobs: list[sqlite3.Row]) -> str:
    header = f"{len(jobs)} new job(s) for you:\n\n"
    body = "\n\n".join(_format_job_line(j) for j in jobs[:MAX_JOBS_IN_DIGEST])
    if len(jobs) > MAX_JOBS_IN_DIGEST:
        body += f"\n\n… and {len(jobs) - MAX_JOBS_IN_DIGEST} more. Run `job-hunter list` to see all."
    return header + body


def _send_telegram(text: str, cfg: NotificationConfig) -> None:
    url = f"https://api.telegram.org/bot{cfg.telegram_bot_token}/sendMessage"
    # Telegram messages are capped at 4096 chars; trim defensively.
    resp = httpx.post(url, json={
        "chat_id": cfg.telegram_chat_id,
        "text": text[:4000],
        "disable_web_page_preview": True,
    }, timeout=15.0)
    resp.raise_for_status()


def _send_webhook(text: str, cfg: NotificationConfig) -> None:
    # Slack and Discord both accept a plain `{"text": ...}` / `{"content": ...}`
    # payload for simple messages; send both keys so either works.
    resp = httpx.post(cfg.webhook_url, json={
        "text": text[:3000],
        "content": text[:1900],  # Discord's 2000-char message limit
    }, timeout=15.0)
    resp.raise_for_status()


def _send_email(text: str, cfg: NotificationConfig, subject: str) -> None:
    msg = MIMEText(text)
    msg["Subject"] = subject
    msg["From"] = cfg.smtp_from or cfg.smtp_user
    msg["To"] = cfg.smtp_to

    with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=15.0) as server:
        if cfg.smtp_use_tls:
            server.starttls()
        if cfg.smtp_user:
            server.login(cfg.smtp_user, cfg.smtp_password)
        server.sendmail(msg["From"], [cfg.smtp_to], msg.as_string())


def send_digest(jobs: list[sqlite3.Row], cfg: NotificationConfig) -> dict:
    """Send `jobs` to every configured channel. Returns per-channel results."""
    results: dict[str, str] = {}
    if not jobs:
        return results

    text = _digest_text(jobs)

    if cfg.telegram_bot_token and cfg.telegram_chat_id:
        try:
            _send_telegram(text, cfg)
            results["telegram"] = "sent"
        except Exception as exc:
            results["telegram"] = f"error: {exc}"

    if cfg.webhook_url:
        try:
            _send_webhook(text, cfg)
            results["webhook"] = "sent"
        except Exception as exc:
            results["webhook"] = f"error: {exc}"

    if cfg.smtp_host and cfg.smtp_to:
        try:
            _send_email(text, cfg, subject=f"job-hunter: {len(jobs)} new job(s)")
            results["email"] = "sent"
        except Exception as exc:
            results["email"] = f"error: {exc}"

    return results

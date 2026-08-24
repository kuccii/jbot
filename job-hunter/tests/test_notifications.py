from unittest.mock import MagicMock, patch

from job_hunter.config import NotificationConfig
from job_hunter.notifications import send_digest


def fake_job(**overrides):
    row = {
        "title": "Python Engineer", "company": "Acme", "board": "himalayas",
        "location": "Remote", "score": 80, "url": "https://example.com/1",
    }
    row.update(overrides)
    return row


class TestSendDigest:
    def test_no_channels_configured_returns_empty(self):
        cfg = NotificationConfig(enabled=True)
        assert send_digest([fake_job()], cfg) == {}

    def test_no_jobs_returns_empty_even_if_configured(self):
        cfg = NotificationConfig(enabled=True, webhook_url="https://hooks.example/x")
        assert send_digest([], cfg) == {}

    @patch("job_hunter.notifications.httpx.post")
    def test_telegram_sends_when_configured(self, mock_post):
        mock_post.return_value = MagicMock(raise_for_status=lambda: None)
        cfg = NotificationConfig(
            enabled=True, telegram_bot_token="TOKEN", telegram_chat_id="123"
        )
        results = send_digest([fake_job()], cfg)
        assert results["telegram"] == "sent"
        called_url = mock_post.call_args[0][0]
        assert "TOKEN" in called_url

    @patch("job_hunter.notifications.httpx.post")
    def test_telegram_error_is_captured_not_raised(self, mock_post):
        mock_post.side_effect = RuntimeError("boom")
        cfg = NotificationConfig(
            enabled=True, telegram_bot_token="TOKEN", telegram_chat_id="123"
        )
        results = send_digest([fake_job()], cfg)
        assert "error" in results["telegram"]

    @patch("job_hunter.notifications.httpx.post")
    def test_webhook_sends_when_configured(self, mock_post):
        mock_post.return_value = MagicMock(raise_for_status=lambda: None)
        cfg = NotificationConfig(enabled=True, webhook_url="https://hooks.example/x")
        results = send_digest([fake_job()], cfg)
        assert results["webhook"] == "sent"

    @patch("job_hunter.notifications.smtplib.SMTP")
    def test_email_sends_when_configured(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_server
        cfg = NotificationConfig(
            enabled=True, smtp_host="smtp.example.com", smtp_to="me@example.com",
            smtp_from="bot@example.com",
        )
        results = send_digest([fake_job()], cfg)
        assert results["email"] == "sent"
        mock_server.sendmail.assert_called_once()

    @patch("job_hunter.notifications.httpx.post")
    def test_multiple_channels_all_attempted(self, mock_post):
        mock_post.return_value = MagicMock(raise_for_status=lambda: None)
        cfg = NotificationConfig(
            enabled=True,
            telegram_bot_token="TOKEN", telegram_chat_id="123",
            webhook_url="https://hooks.example/x",
        )
        results = send_digest([fake_job()], cfg)
        assert results["telegram"] == "sent"
        assert results["webhook"] == "sent"
        assert mock_post.call_count == 2

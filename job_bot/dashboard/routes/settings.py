"""Settings management routes."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from job_bot.config import load_config
from job_bot.dashboard.routes._deps import get_repo

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    cfg = load_config()
    return templates.TemplateResponse(request, "settings.html", {
        "config": cfg, "page": "settings",
        "has_gemini_key": bool(cfg.llm.gemini_api_key),
        "has_nim_key": bool(cfg.llm.nim_api_key),
        "has_opencode_key": bool(cfg.llm.opencode_api_key),
        "has_whatsapp_token": bool(cfg.notifications.whatsapp.token),
        "has_firecrawl_key": bool(cfg.web_services.firecrawl_api_key),
        "has_jina_key": bool(cfg.web_services.jina_api_key),
        "has_tinyfish_key": bool(cfg.web_services.tinyfish_api_key),
    })


@router.post("/settings")
async def save_settings(request: Request):
    cfg = load_config()
    form = await request.form()
    cfg.profile.name = form.get("name", "")
    cfg.profile.email = form.get("email", "")
    cfg.profile.phone = form.get("phone", "")
    cfg.profile.skills = [s.strip() for s in form.get("skills", "").split(",") if s.strip()]
    cfg.llm.provider = form.get("llm_provider", "ollama")
    cfg.llm.model = form.get("llm_model", "llama3.1:8b")
    cfg.llm.embedding_model = form.get("embedding_model", "nomic-embed-text")
    cfg.llm.temperature = float(form.get("temperature", 0.3))
    cfg.llm.ollama_base_url = form.get("ollama_base_url", "http://localhost:11434")
    gemini_key = form.get("gemini_api_key", "")
    if gemini_key:
        cfg.llm.gemini_api_key = gemini_key
    nim_key = form.get("nim_api_key", "")
    if nim_key:
        cfg.llm.nim_api_key = nim_key
    opencode_key = form.get("opencode_api_key", "")
    if opencode_key:
        cfg.llm.opencode_api_key = opencode_key
    cfg.llm.opencode_base_url = form.get("opencode_base_url", "https://opencode.ai/zen/v1")
    cfg.discovery.companies = [c.strip() for c in form.get("companies", "").split("\n") if c.strip()]
    cfg.discovery.sources["google_search"] = form.get("source_google_search") == "on"
    cfg.discovery.sources["linkedin"] = form.get("source_linkedin") == "on"
    cfg.discovery.sources["twitter"] = form.get("source_twitter") == "on"
    cfg.discovery.sources["african_jobs"] = form.get("source_african_jobs") == "on"
    cfg.discovery.sources["company_pages"] = form.get("source_company_pages") == "on"
    cfg.discovery.interval_hours = int(form.get("interval_hours", 24))
    cfg.application.human_approval = form.get("human_approval") == "on"
    cfg.application.autonomous_apply = form.get("autonomous_apply") == "on"
    cfg.application.max_applications_per_run = int(form.get("max_applications_per_run", 5))
    cfg.notifications.whatsapp.enabled = form.get("whatsapp_enabled") == "on"
    cfg.notifications.whatsapp.phone_number_id = form.get("whatsapp_phone_number_id", "")
    whatsapp_token = form.get("whatsapp_token", "")
    if whatsapp_token:
        cfg.notifications.whatsapp.token = whatsapp_token
    cfg.notifications.whatsapp.recipient = form.get("whatsapp_recipient", "")
    firecrawl_key = form.get("firecrawl_api_key", "")
    if firecrawl_key:
        cfg.web_services.firecrawl_api_key = firecrawl_key
    jina_key = form.get("jina_api_key", "")
    if jina_key:
        cfg.web_services.jina_api_key = jina_key
    tinyfish_key = form.get("tinyfish_api_key", "")
    if tinyfish_key:
        cfg.web_services.tinyfish_api_key = tinyfish_key
    import yaml
    with open(Path.cwd() / "config.yaml", "w") as f:
        yaml.dump(cfg.model_dump(), f, default_flow_style=False)
    repo = get_repo()
    repo.log_audit("settings_updated", "dashboard", {})
    return templates.TemplateResponse(request, "settings.html", {
        "config": cfg, "page": "settings", "saved": True,
        "has_gemini_key": bool(cfg.llm.gemini_api_key),
        "has_nim_key": bool(cfg.llm.nim_api_key),
        "has_opencode_key": bool(cfg.llm.opencode_api_key),
        "has_whatsapp_token": bool(cfg.notifications.whatsapp.token),
        "has_firecrawl_key": bool(cfg.web_services.firecrawl_api_key),
        "has_jina_key": bool(cfg.web_services.jina_api_key),
        "has_tinyfish_key": bool(cfg.web_services.tinyfish_api_key),
    })

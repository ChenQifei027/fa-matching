import os, re
from pathlib import Path
from dotenv import load_dotenv, dotenv_values
from fastapi import APIRouter
from pydantic import BaseModel

load_dotenv()
router = APIRouter(prefix="/api/settings")
ENV_PATH = Path(".env")


class SettingsUpdate(BaseModel):
    anthropic_api_key: str = ""
    model: str = ""


@router.get("")
def get_settings():
    vals = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    key = vals.get("ANTHROPIC_API_KEY", "")
    return {
        "anthropic_api_key": (key[:10] + "••••••••••••••••") if len(key) > 8 else "",
        "model": vals.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        "db_path": vals.get("DB_PATH", "data/fa_matching.db"),
    }


@router.put("")
def update_settings(body: SettingsUpdate):
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    updates: dict[str, str] = {}
    if body.anthropic_api_key and "••" not in body.anthropic_api_key:
        updates["ANTHROPIC_API_KEY"] = body.anthropic_api_key
    if body.model:
        updates["ANTHROPIC_MODEL"] = body.model
    for key, val in updates.items():
        pat = re.compile(rf"^{key}=.*")
        new_line = f"{key}={val}"
        if any(pat.match(l) for l in lines):
            lines = [pat.sub(new_line, l) for l in lines]
        else:
            lines.append(new_line)
    ENV_PATH.write_text("\n".join(lines) + "\n")
    return {"ok": True}


@router.get("/verify-llm")
def verify_llm():
    from core.llm import llm_is_configured
    return {"configured": llm_is_configured()}


@router.post("/sync-cookies")
def sync_cookies():
    try:
        from core.cookie_sync import sync_safari_cookies
        state = os.getenv("BROWSER_STATE_PATH", "data/browser_state.json")
        return {"synced": sync_safari_cookies(state)}
    except ImportError:
        return {"synced": 0, "error": "not available"}

# app/auth_orchestrator.py
# Detects login/signup pages, pauses for manual auth in the VNC desktop,
# resumes once the application form is visible, and persists storage state.
from __future__ import annotations
import asyncio, json, os, re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from playwright.async_api import Browser, BrowserContext, Page

# SSE log bus (same one you already use)
try:
    from .runners.run_manager import RUN_BUS
except Exception:
    class _DummyBus:
        async def emit(self, *_args, **_kwargs): pass
    RUN_BUS = _DummyBus()

AUTH_DIR = os.getenv("AUTH_DIR", "./auth")  # per-host storageState
os.makedirs(AUTH_DIR, exist_ok=True)

# ---- helpers
def host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""

async def log(run_id: Optional[str], level: str, message: str):
    try:
        payload = {"type":"log","level":level,"message":message}
        await RUN_BUS.emit(run_id, json.dumps(payload))
    except Exception:
        pass

@dataclass
class AuthGate:
    provider: str   # e.g., "workday", "taleo", "icims", "generic"
    reason: str     # e.g., "login form detected"
    url: str

# ---- detection heuristics
RX_LOGIN_WORDS = re.compile(r"(sign\s*in|log\s*in|create\s*account|new\s*user|returning\s*user|register)", re.I)

def infer_provider(u: str) -> str:
    h = host(u)
    if "myworkdayjobs.com" in h or ".wd" in h:
        return "workday"
    if "taleo.net" in h or "oraclecloud" in h:  # some Taleo/Oracle portals
        return "taleo"
    if "icims.com" in h:
        return "icims"
    if "lever.co" in h or "jobs.lever.co" in h:
        return "lever"
    if "greenhouse.io" in h or "boards.greenhouse.io" in h:
        return "greenhouse"
    if "ashbyhq.com" in h or "jobs.ashbyhq.com" in h:
        return "ashby"
    return "generic"

async def looks_like_login_wall(page: Page) -> bool:
    # password field is the strongest signal
    if await page.locator("input[type='password']").count():
        return True
    # common login terms visible
    if await page.get_by_text(RX_LOGIN_WORDS, exact=False).count():
        return True
    # Taleo/iCIMS/Workday login routes
    u = page.url
    if ("taleo.net/careersection/iam/accessmanagement" in u or
        ("icims" in u and ("login" in u or "profile.ftl" in u)) or
        ("myworkdayjobs.com" in u and "SignIn" in u)):
        return True
    return False

async def application_ready(page: Page) -> bool:
    # "ready" when we can see resume upload or an application submit step
    if await page.locator("input[type='file']").count():
        return True
    if await page.get_by_text(re.compile(r"(upload|attach).*(resume|cv)", re.I)).count():
        return True
    if await page.get_by_role("button", name=re.compile(r"(submit|apply|next)", re.I)).count():
        # loose signal; still okay to proceed to filler (it will no-op if nothing matches)
        return True
    return False

async def try_continue_as_guest(page: Page) -> bool:
    # Some portals offer "Apply as guest" / "Continue as guest"
    buttons = page.get_by_role("button").filter(
        has_text=re.compile(r"(apply|continue)\s+as\s+guest", re.I)
    )
    if await buttons.count():
        try:
            await buttons.first.click()
            await page.wait_for_timeout(600)
            return True
        except Exception:
            return False
    # Alt phrasing
    links = page.get_by_text(re.compile(r"(apply|continue)\s+as\s+guest", re.I))
    if await links.count():
        try:
            await links.first.click()
            await page.wait_for_timeout(600)
            return True
        except Exception:
            return False
    return False

async def load_auth_state(browser: Browser, url: str) -> BrowserContext:
    h = host(url)
    state_file = os.path.join(AUTH_DIR, f"{h}.json")
    if os.path.exists(state_file):
        return await browser.new_context(storage_state=state_file, viewport={"width":1280,"height":860})
    return await browser.new_context(viewport={"width":1280,"height":860})

async def save_auth_state(ctx: BrowserContext, url: str):
    h = host(url)
    state_file = os.path.join(AUTH_DIR, f"{h}.json")
    await ctx.storage_state(path=state_file)

# ---- main entry
async def ensure_authenticated(browser: Browser, apply_url: str, run_id: Optional[str] = None) -> Page:
    """
    Returns a Page that is either already on the application form or
    has paused (via SSE gate) until the user signs in.
    """
    ctx = await load_auth_state(browser, apply_url)
    page = await ctx.new_page()
    await page.goto(apply_url, wait_until="domcontentloaded")

    # If a login wall appears, try "continue as guest", else gate.
    if await looks_like_login_wall(page):
        prov = infer_provider(page.url)
        if await try_continue_as_guest(page):
            await log(run_id, "info", "Clicked 'Continue as guest'")
            await page.wait_for_load_state("domcontentloaded")

        if await looks_like_login_wall(page):
            # Still a login page: pause for manual login in the VNC desktop
            gate_msg = {
                "type":"auth_gate",
                "provider": prov,
                "url": page.url,
                "instructions": (
                    "Please sign in / create an account in the desktop window. "
                    "Complete any 2FA or SSO. When you land on the application form, "
                    "click 'I'm signed in' in the UI."
                )
            }
            await RUN_BUS.emit(run_id, json.dumps(gate_msg))

            # Wait until the UI calls /runs/{id}/continue (your existing endpoint)
            # Your continue endpoint should set some asyncio.Event; we'll poll for readiness too.
            # Poll DOM as a secondary signal:
            for _ in range(600):  # up to ~5 minutes
                if await application_ready(page):
                    break
                await asyncio.sleep(1)

    # If we've reached the application form, persist auth cookies for next time.
    if await application_ready(page):
        await save_auth_state(ctx, apply_url)
        await log(run_id, "info", f"Authenticated on {host(apply_url)}; storageState saved.")
    else:
        await log(run_id, "warn", "Still on login — user may need to complete steps or click 'I'm signed in'.")

    return page

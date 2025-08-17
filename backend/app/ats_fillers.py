# app/ats_fillers.py
# Multi-ATS prefill strategies + common US-compliance answers.
# Requires: playwright==1.47+, BeautifulSoup4 (optional), your RUN_BUS for SSE logs

from __future__ import annotations
import asyncio, os, re
from typing import Optional, Protocol, List, Dict
from urllib.parse import urlparse

from playwright.async_api import Page, BrowserContext

# ---- Optional: import your SSE bus for logs (adjust path if needed)
try:
    from .runners.run_manager import RUN_BUS
except Exception:
    class _DummyBus:
        async def emit(self, *_args, **_kwargs): pass
    RUN_BUS = _DummyBus()


# -------------------------
# Applicant assumptions (you can load these from DB)
# -------------------------
class ApplicantAnswers:
    def __init__(
        self,
        full_name: str = "",
        first_name: str = "",
        last_name: str = "",
        email: str = "",
        phone: str = "",
        city: str = "",
        state: str = "",
        linkedin: Optional[str] = None,
        website: Optional[str] = None,
        github: Optional[str] = None,
        # Assumptions below per user request:
        us_citizen: bool = True,
        needs_sponsorship_now_or_future: bool = False,
        protected_veteran: bool = False,
        has_disability: bool = False,
    ):
        self.full_name = full_name
        self.first_name = first_name or (full_name.split()[0] if full_name else "")
        self.last_name = last_name or (full_name.split()[-1] if full_name else "")
        self.email = email
        self.phone = phone
        self.city = city
        self.state = state
        self.linkedin = linkedin
        self.website = website
        self.github = github

        self.us_citizen = us_citizen
        self.needs_sponsorship_now_or_future = needs_sponsorship_now_or_future
        self.protected_veteran = protected_veteran
        self.has_disability = has_disability


# -------------------------
# Helpers
# -------------------------
def _rx(pattern: str) -> re.Pattern:
    return re.compile(pattern, flags=re.I)

LABELS_NAME = [
    _rx(r"full\s*name"),
    _rx(r"legal\s*name"),
]
LABELS_FIRST = [_rx(r"first\s*name")]
LABELS_LAST  = [_rx(r"last\s*name")]
LABELS_EMAIL = [_rx(r"email")]
LABELS_PHONE = [_rx(r"phone")]
LABELS_CITY  = [_rx(r"city|town")]
LABELS_STATE = [_rx(r"state|province|region")]
LABELS_LINKEDIN = [_rx(r"linkedin")]
LABELS_WEBSITE  = [_rx(r"website|portfolio|personal\s*site")]
LABELS_GITHUB   = [_rx(r"github")]

LABELS_RESUME = [
    _rx(r"resume|cv|upload.*resume|upload.*cv")
]

# Compliance / eligibility
Q_AUTH   = [_rx(r"(are you|i am).*(authorized|legally authorized).*work.*united states"),
            _rx(r"work authorization"), _rx(r"authorized to work in the us")]
Q_SPONS  = [_rx(r"(require|need).*(visa|sponsorship).*(now|future)?"),
            _rx(r"will you now or in the future require sponsorship")]
Q_VET    = [_rx(r"(protected\s*veteran|veteran\s*status)") ]
Q_DISAB  = [_rx(r"(disability|disabled)"), _rx(r"cc-?305"), _rx(r"ofccp")]

YES = ["yes", "y", "i am", "authorized", "do not require", "u.s. citizen", "us citizen"]
NO  = ["no", "n", "not", "i do not", "do not", "does not"]

async def log(run_id: Optional[str], level: str, message: str):
    payload = {"type": "log", "level": level, "message": message}
    try:
        if run_id:
            import json
            await RUN_BUS.emit(run_id, json.dumps(payload))
    except Exception:
        pass

async def upload_resume_by_best_effort(page: Page, resume_path: str) -> bool:
    """Try several strategies to set the resume file input."""
    # 1) Look for direct file inputs near 'Resume' text
    inputs = page.locator("input[type='file']")
    count = await inputs.count()
    for i in range(count):
        inp = inputs.nth(i)
        # if the input is within a label or section mentioning Resume/CV
        label_text = await inp.evaluate("""(el) => {
            const label = el.closest('label') || el.labels?.[0];
            return label ? label.innerText : '';
        }""")
        if label_text and re.search(r"resume|cv", label_text, re.I):
            await inp.set_input_files(resume_path)
            return True

    # 2) Look for any visible label 'Resume' and its associated input
    lab = page.get_by_text(re.compile(r"resume|cv", re.I), exact=False).locator("xpath=ancestor::label")
    if await lab.count():
        # input under same label
        file_inp = lab.locator("input[type='file']")
        if await file_inp.count():
            await file_inp.first.set_input_files(resume_path)
            return True

    # 3) Click obvious upload buttons to reveal a hidden input
    candidates = page.locator("button, [role='button']").filter(has_text=re.compile(r"upload|attach|resume|cv", re.I))
    if await candidates.count():
        try:
            await candidates.first.click()
            await page.wait_for_timeout(300)
            hidden = page.locator("input[type='file']")
            if await hidden.count():
                await hidden.first.set_input_files(resume_path)
                return True
        except Exception:
            pass

    # 4) Last resort: set the first file input on page
    if count:
        try:
            await inputs.first.set_input_files(resume_path)
            return True
        except Exception:
            pass

    return False

async def fill_text_input_by_label(page: Page, patterns: List[re.Pattern], value: str) -> bool:
    if not value: return False
    # Prefer semantic label associations
    for pat in patterns:
        lbl = page.get_by_label(pat)
        if await lbl.count():
            try:
                await lbl.first.fill(value)
                return True
            except Exception:
                pass

    # Fallback: search visible text near inputs
    for pat in patterns:
        text_nodes = page.get_by_text(pat, exact=False)
        n = await text_nodes.count()
        for i in range(min(n, 5)):
            node = text_nodes.nth(i)
            # find inputs inside same container
            inp = node.locator("xpath=ancestor::*[self::div or self::section or self::fieldset][1]").locator("input[type='text'],input[type='email'],input[type='tel'],textarea")
            if await inp.count():
                try:
                    await inp.first.fill(value)
                    return True
                except Exception:
                    pass
    return False

async def choose_radio_or_select(page: Page, question_patterns: List[re.Pattern], prefer_yes: bool) -> bool:
    """
    Find a block matching the question and click the appropriate option.
    Works with radios, selects, and "chip" buttons.
    """
    # Locate by question text
    for pat in question_patterns:
        q = page.get_by_text(pat, exact=False)
        if not await q.count():
            continue
        container = q.nth(0).locator("xpath=ancestor::*[self::section or self::div or self::fieldset][1]")
        # Try radio/checkbox labels
        options = container.locator("label:has(input[type='radio']),label:has(input[type='checkbox'])")
        if await options.count():
            # Heuristic: pick the option whose text best matches yes/no intent
            target = None
            for i in range(await options.count()):
                t = (await options.nth(i).inner_text()).strip().lower()
                if prefer_yes and re.search(r"\b(yes|i am|authorized|do not require)\b", t):
                    target = options.nth(i); break
                if not prefer_yes and re.search(r"\b(no|i do not|not|will not)\b", t):
                    target = options.nth(i); break
            if target is None:
                # fallback: first option
                target = options.first
            try:
                await target.click()
                return True
            except Exception:
                pass

        # Try select dropdowns
        select = container.locator("select")
        if await select.count():
            try:
                if prefer_yes:
                    await select.first.select_option(label=re.compile(r"yes|authorized|citizen|do not require", re.I))
                else:
                    await select.first.select_option(label=re.compile(r"no|not|will not|do not", re.I))
                return True
            except Exception:
                pass

        # Try button chips
        btns = container.locator("button,[role='button'],.chip,.option")
        if await btns.count():
            for i in range(await btns.count()):
                t = (await btns.nth(i).inner_text()).strip().lower()
                if prefer_yes and re.search(r"\b(yes|authorized|citizen|do not require)\b", t):
                    await btns.nth(i).click(); return True
                if not prefer_yes and re.search(r"\b(no|not|will not|do not)\b", t):
                    await btns.nth(i).click(); return True
    return False

async def answer_common_questions(page: Page, a: ApplicantAnswers) -> None:
    # Work authorization (Yes if authorized / US citizen)
    await choose_radio_or_select(page, Q_AUTH, prefer_yes=a.us_citizen)

    # Sponsorship (No)
    await choose_radio_or_select(page, Q_SPONS, prefer_yes=not a.needs_sponsorship_now_or_future)

    # Protected veteran (No)
    await choose_radio_or_select(page, Q_VET, prefer_yes=a.protected_veteran)

    # Disability (OFCCP CC-305): "No, I don't have a disability"
    # Some forms only offer "Yes / No / Decline". We prefer explicit No; if not found, fallback is handled by heuristic.
    await choose_radio_or_select(page, Q_DISAB, prefer_yes=a.has_disability)


async def fill_common_profile_fields(page: Page, a: ApplicantAnswers) -> None:
    await fill_text_input_by_label(page, LABELS_NAME, a.full_name)
    await fill_text_input_by_label(page, LABELS_FIRST, a.first_name)
    await fill_text_input_by_label(page, LABELS_LAST, a.last_name)
    await fill_text_input_by_label(page, LABELS_EMAIL, a.email)
    await fill_text_input_by_label(page, LABELS_PHONE, a.phone)
    await fill_text_input_by_label(page, LABELS_CITY, a.city)
    await fill_text_input_by_label(page, LABELS_STATE, a.state)

    # Links (best-effort)
    if a.linkedin:
        await fill_text_input_by_label(page, LABELS_LINKEDIN, a.linkedin)
    if a.website:
        await fill_text_input_by_label(page, LABELS_WEBSITE, a.website)
    if a.github:
        await fill_text_input_by_label(page, LABELS_GITHUB, a.github)


# -------------------------
# Strategy Protocol + Router
# -------------------------
class FormFiller(Protocol):
    def matches(self, url: str) -> bool: ...
    async def prefill(self, page: Page, resume_path: str, applicant: ApplicantAnswers, run_id: Optional[str]) -> None: ...


def host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


# -------------------------
# Greenhouse
# -------------------------
class GreenhouseFiller:
    """Greenhouse-hosted job boards (boards.greenhouse.io / app.greenhouse.io)."""
    def matches(self, url: str) -> bool:
        h = host(url)
        return "greenhouse.io" in h or "boards.greenhouse.io" in h

    async def prefill(self, page: Page, resume_path: str, applicant: ApplicantAnswers, run_id: Optional[str]):
        await log(run_id, "info", "Detected Greenhouse")
        await fill_common_profile_fields(page, applicant)
        if resume_path and os.path.exists(resume_path):
            ok = await upload_resume_by_best_effort(page, resume_path)
            await log(run_id, "info", f"Resume upload {'OK' if ok else 'not found'}")
        await answer_common_questions(page, applicant)


# -------------------------
# Lever
# -------------------------
class LeverFiller:
    """Lever job sites (jobs.lever.co/<company>)"""
    def matches(self, url: str) -> bool:
        h = host(url)
        return "lever.co" in h or "jobs.lever.co" in h

    async def prefill(self, page: Page, resume_path: str, applicant: ApplicantAnswers, run_id: Optional[str]):
        await log(run_id, "info", "Detected Lever")
        await fill_common_profile_fields(page, applicant)
        if resume_path and os.path.exists(resume_path):
            ok = await upload_resume_by_best_effort(page, resume_path)
            await log(run_id, "info", f"Resume upload {'OK' if ok else 'not found'}")
        await answer_common_questions(page, applicant)


# -------------------------
# Workday
# -------------------------
class WorkdayFiller:
    """Workday-hosted career portals (*.myworkdayjobs.com)"""
    def matches(self, url: str) -> bool:
        return "myworkdayjobs.com" in host(url) or ".wd" in host(url)

    async def prefill(self, page: Page, resume_path: str, applicant: ApplicantAnswers, run_id: Optional[str]):
        await log(run_id, "info", "Detected Workday")
        # Workday often uses steppers; fill visible step, then next
        await fill_common_profile_fields(page, applicant)
        if resume_path and os.path.exists(resume_path):
            ok = await upload_resume_by_best_effort(page, resume_path)
            await log(run_id, "info", f"Resume upload {'OK' if ok else 'not found'}")
        await answer_common_questions(page, applicant)
        # You can add step navigation (Next buttons), but we stop for human review anyway.


# -------------------------
# Ashby
# -------------------------
class AshbyFiller:
    """Ashby job boards (jobs.ashbyhq.com)"""
    def matches(self, url: str) -> bool:
        h = host(url)
        return "ashbyhq.com" in h

    async def prefill(self, page: Page, resume_path: str, applicant: ApplicantAnswers, run_id: Optional[str]):
        await log(run_id, "info", "Detected Ashby")
        await fill_common_profile_fields(page, applicant)
        if resume_path and os.path.exists(resume_path):
            ok = await upload_resume_by_best_effort(page, resume_path)
            await log(run_id, "info", f"Resume upload {'OK' if ok else 'not found'}")
        await answer_common_questions(page, applicant)


# -------------------------
# Generic fallback
# -------------------------
class GenericFiller:
    def matches(self, url: str) -> bool:
        return True

    async def prefill(self, page: Page, resume_path: str, applicant: ApplicantAnswers, run_id: Optional[str]):
        await log(run_id, "info", "Unknown ATS — using generic strategy")
        await fill_common_profile_fields(page, applicant)
        if resume_path and os.path.exists(resume_path):
            ok = await upload_resume_by_best_effort(page, resume_path)
            await log(run_id, "info", f"Resume upload {'OK' if ok else 'not found'}")
        await answer_common_questions(page, applicant)


# -------------------------
# Router
# -------------------------
FILLERS: List[FormFiller] = [
    GreenhouseFiller(),
    LeverFiller(),
    WorkdayFiller(),
    AshbyFiller(),
    GenericFiller(),
]

def resolve_filler(url: str) -> FormFiller:
    for f in FILLERS:
        if f.matches(url):
            return f
    return GenericFiller()


# -------------------------
# Entry point for your runner
# -------------------------
async def prefill_application(
    page: Page,
    apply_url: str,
    resume_path: Optional[str],
    applicant: ApplicantAnswers,
    run_id: Optional[str] = None,
):
    """Navigate to the apply_url and prefill fields + resume."""
    filler = resolve_filler(apply_url)
    await page.goto(apply_url, wait_until="domcontentloaded")
    await asyncio.sleep(0.5)
    await filler.prefill(page, resume_path or "", applicant, run_id)
    await log(run_id, "info", "Prefill complete — pausing for human review.")

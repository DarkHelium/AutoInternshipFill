import base64, os
import httpx, re
from bs4 import BeautifulSoup
from typing import List, Dict

GITHUB_API = "https://api.github.com"

def _gh_headers(token: str | None):
    h = {"Accept": "application/vnd.github+json"}
    if token: h["Authorization"] = f"Bearer {token}"
    return h

def fetch_readme(owner: str, repo: str, branch: str, token: str | None) -> str:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/README.md?ref={branch}"
    r = httpx.get(url, headers=_gh_headers(token), timeout=30)
    r.raise_for_status()
    data = r.json()
    content = base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
    return content

def parse_jobs_from_readme(markdown: str) -> List[Dict]:
    """
    The README has a 'Company Role Location Application/Link Date Posted' header,
    then lines with 'Company  Role  Location  [Apply](URL)  Aug 15'.
    We'll use a robust regex to catch lines that contain an [Apply](...) link.
    """
    jobs = []
    apply_line = re.compile(r"^(?P<company>.+?)\s{2,}(?P<role>.+?)\s{2,}(?P<location>.+?)\s{2,}\[.*?Apply.*?\]\((?P<url>https?://[^\s)]+)\)\s{1,}(?P<date>[^ \n\r]+.*)$")
    section = False
    for raw in markdown.splitlines():
        if raw.strip().startswith("Company Role Location"):
            section = True
            continue
        if not section: 
            continue
        if raw.strip().startswith("⬆️ Back to Top"):
            break
        m = apply_line.match(raw.strip())
        if m:
            d = m.groupdict()
            jobs.append({
                "company": d["company"].strip("↳ ").strip(),
                "role": d["role"].strip(),
                "location": d["location"].strip(),
                "apply_url": d["url"].strip(),
                "date_posted": d["date"].strip(),
                "raw_line": raw
            })
    return jobs

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
    """Fetch README markdown.

    Prefer RAW_README_URL if provided, else use GitHub API.
    """
    raw_url = os.getenv("RAW_README_URL")
    if raw_url:
        r = httpx.get(raw_url, timeout=30)
        r.raise_for_status()
        return r.text

    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/README.md?ref={branch}"
    r = httpx.get(url, headers=_gh_headers(token), timeout=30)
    r.raise_for_status()
    data = r.json()
    content = base64.b64decode(data.get("content", "")).decode("utf-8", errors="ignore")
    return content

def parse_jobs_from_readme(markdown: str) -> List[Dict]:
    """Parse jobs from README supporting both table and spaced formats.

    Supports markdown tables like:
    | Company | Role | Location | Application/Link | Date Posted |
    | ------- | ---- | -------- | ---------------- | ----------- |
    | Foo     | SWE  | Remote   | [Apply](https://..) | 2025-01-01 |

    Also supports space-delimited lines with an [Apply](...) link.
    """
    jobs: List[Dict] = []
    link_rx = re.compile(r"\[(?:Apply|Application|Link)[^\]]*\]\((https?://[^\s)]+)\)", re.I)
    url_rx = re.compile(r"https?://[^\s)]+")

    lines = markdown.splitlines()
    in_table = False
    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        # Detect start of table by header keywords
        if ("Company" in line and "Role" in line and ("Application" in line or "Apply" in line)):
            in_table = True
            continue
        # Skip separator rows
        if in_table and set(line.replace('|','').strip()) <= set('- :'):
            continue

        if '|' in line and in_table:
            parts = [p.strip() for p in line.strip('|').split('|')]
            if len(parts) >= 4:
                company = parts[0]
                role = parts[1]
                location = parts[2] if len(parts) > 2 else ''
                link_cell = parts[3]
                m = link_rx.search(link_cell) or url_rx.search(link_cell)
                url = m.group(1) if m and m.re is link_rx else (m.group(0) if m else '')
                date = parts[4] if len(parts) > 4 else ''
                if url:
                    jobs.append({
                        "company": company,
                        "role": role,
                        "location": location,
                        "apply_url": url,
                        "date_posted": date,
                        "raw_line": raw,
                    })
            continue

        # Fallback: spaced format
        m = link_rx.search(line)
        if m:
            url = m.group(1)
            # naive split by two+ spaces
            cols = re.split(r"\s{2,}", line)
            if len(cols) >= 4:
                company, role, location = cols[0], cols[1], cols[2]
                date = cols[4] if len(cols) > 4 else ''
                jobs.append({
                    "company": company.strip('↳ ').strip(),
                    "role": role.strip(),
                    "location": location.strip(),
                    "apply_url": url,
                    "date_posted": date.strip(),
                    "raw_line": raw,
                })

    return jobs

from playwright.async_api import async_playwright
import re
from typing import List, Dict

RAW_README_URL = "https://github.com/vanshb03/Summer2026-Internships/raw/dev/README.md"

async def read_jobs_from_readme() -> List[Dict]:
    """Scrape jobs from the raw GitHub README using Playwright"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(RAW_README_URL, wait_until="domcontentloaded")
        md = await page.text_content("pre, body")  # raw content
        await browser.close()

    jobs = []
    # lines: Company  Role  Location  [![Apply](...)](https://actual-job-url)  Aug 15
    pat = re.compile(r"^(?P<company>[^|]+?)\s{2,}(?P<role>[^|]+?)\s{2,}(?P<location>[^|]+?)\s{2,}\[.*?\]\((?P<url>https?://[^\s)]+)\)\s+(?P<date>.+)$")
    for line in (md or "").splitlines():
        m = pat.match(line.strip())
        if m:
            d = m.groupdict()
            jobs.append({
                "company": d["company"].strip("↳ ").strip(),
                "role": d["role"].strip(),
                "location": d["location"].strip(),
                "apply_url": d["url"].strip(),
                "date_posted": d["date"].strip()
            })
    return jobs

from urllib.parse import urlparse

def detect_ats(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "boards.greenhouse.io" in host or "greenhouse.io" in host:
        return "greenhouse"  # Greenhouse job/board URLs look like boards.greenhouse.io/<token>.
    if "lever.co" in host or "jobs.lever.co" in host:
        return "lever"       # Lever job sites run under jobs.lever.co/<company>.
    if "myworkdayjobs.com" in host or ".wd" in host:
        return "workday"     # Workday-hosted postings live under *.myworkdayjobs.com.
    if "ashbyhq.com" in host or "jobs.ashbyhq.com" in host:
        return "ashby"       # Ashby job boards & embeds.
    return "other"

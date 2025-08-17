import re
from collections import Counter
from html import escape
from typing import List

STOP = set("""
a an and or the is are was were to for of in on at with by from using use used built implemented developed 
software engineer developer internship intern summer systems backend frontend fullstack team
""".split())

def tokenize(txt: str) -> List[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-\+\.#]{1,}", txt.lower())
    return [w for w in words if w not in STOP and len(w) > 2]

def extract_keywords(jd_text: str, top_k=10) -> List[str]:
    toks = tokenize(jd_text)
    freq = Counter(toks)
    # prefer tech-y tokens (simple heuristics)
    ranked = sorted(freq.items(), key=lambda kv: (kv[0] in {"python","java","c++","typescript","react","next.js","aws","kubernetes","docker","sql","postgres","redis","go"}, kv[1]), reverse=True)
    return [w for w,_ in ranked[:top_k]]

def make_diff_html(base_resume_text: str, keywords: List[str]) -> str:
    # MVP: show a "suggested add" block and highlight missing keywords
    missing = [k for k in keywords if k.lower() not in base_resume_text.lower()]
    html = "<h4>Suggested Keywords</h4><ul>"
    for k in keywords:
        mark = "✅" if k not in missing else "➕"
        html += f"<li>{mark} {escape(k)}</li>"
    html += "</ul>"
    if missing:
        html += "<h4>Suggested line to add</h4><pre>• Applied "
        html += ", ".join(escape(k) for k in missing[:5])
        html += " across projects to reduce latency / improve reliability.</pre>"
    return html

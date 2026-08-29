#!/usr/bin/env python3
"""Fallback checks for official sources that block standard automated requests."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ROOT = Path(__file__).resolve().parent
STATE = ROOT / "fallback_state.json"
ALERT = ROOT / "fallback_alert.md"

SOURCES = [
    ("ncism", "National Commission for Indian System of Medicine", "ayurveda_pg", [
        "https://ncismindia.org/circular-notification.php",
        "https://www.ncismindia.org/circular-notification.php",
        # Jina Reader is used only as a read-through copy of the official NCISM URL when
        # NCISM's web firewall rejects a normal scheduled request with HTTP 409.
        "https://r.jina.ai/http://www.ncismindia.org/circular-notification.php",
        "https://r.jina.ai/https://www.ncismindia.org/circular-notification.php",
        "https://www.bing.com/search?format=rss&q=site%3Ancismindia.org+%28%22new+PG+courses%22+OR+%22open+new+PG%22+OR+%22increase+in+PG%22+OR+%22application%2Fscheme%22%29+Ayurveda",
    ]),
    ("ncahp", "National Commission for Allied and Healthcare Professions", "mpt", [
        "https://ncahp.krispsoft.com/",
        "https://ncahp.krispsoft.com/act-rules--notifications",
        "https://ncahp.krispsoft.com/draftregulations",
        "https://ncahp.krispsoft.com/draft-cariculam",
        "https://ahir.abdm.gov.in/",
        "https://r.jina.ai/https://ahir.abdm.gov.in/",
        "https://www.bing.com/search?format=rss&q=%28site%3Ancahp.krispsoft.com+OR+site%3Aahir.abdm.gov.in+OR+site%3Ancahp.abdm.gov.in%29+%28physiotherapy+OR+MPT+OR+%22allied+and+healthcare%22%29+%28application+OR+recognition+OR+institution+OR+%22new+course%22%29",
    ]),
]

ACTION = (
    "application", "apply", "scheme", "proposal", "establishment", "establish",
    "new institution", "new college", "new course", "higher course", "opening of",
    "increase in intake", "increase in seats", "increase of seats", "intake capacity",
    "recognition", "permission", "affiliation", "last date", "deadline", "extension",
    "extended", "corrigendum", "regulations for recognition", "institutional standards",
    "अर्ज", "प्रस्ताव", "योजना", "स्थापना", "नवीन संस्था", "नवीन महाविद्यालय",
    "नवीन अभ्यासक्रम", "प्रवेश क्षमता", "मान्यता", "परवानगी", "संलग्नता", "मुदतवाढ",
)
EXCLUDE = (
    "recruitment", "vacancy", "empanelment of advocate", "member selection", "counselling",
    "admission schedule", "neet", "student", "professional conduct", "ethics", "enrolment portal",
    "public comments", "draft curriculum", "समुपदेशन", "भरती", "पदभरती", "विद्यार्थी",
)
PG = (
    "new pg course", "new postgraduate course", "open new pg", "opening of new pg",
    "higher course", "pg course", "post graduate course", "postgraduate course",
    "increase in pg", "increase of pg", "md (ayu", "ms (ayu", "m.d. (ayu", "m.s. (ayu",
    "आयुर्वेद पदव्युत्तर", "पदव्युत्तर अभ्यासक्रम", "नवीन पीजी",
)
MPT = (
    "physiotherapy", "physical therapy", "mpt", "m.p.t", "allied health",
    "allied and healthcare", "allied & healthcare", "भौतिकोपचार", "फिजिओथेरपी", "एमपीटी",
)
ALLOWED = {
    "ncism": ("ncismindia.org",),
    "ncahp": ("ncahp.krispsoft.com", "abdm.gov.in", "mohfw.gov.in"),
}


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", value).strip()


def low(value: str) -> str:
    return norm(value).casefold()


def has(text: str, terms: tuple[str, ...]) -> bool:
    return any(term.casefold() in text for term in terms)


def official(key: str, url: str) -> bool:
    host = urlparse(url).hostname or ""
    return not url or any(host == domain or host.endswith("." + domain) for domain in ALLOWED[key])


def relevant(key: str, profile: str, title: str) -> bool:
    text = low(title)
    if not 8 <= len(text) <= 900 or not has(text, ACTION) or has(text, EXCLUDE):
        return False
    if profile == "ayurveda_pg":
        return has(text, PG)
    return has(text, MPT) or has(text, ("institution", "course", "recognition", "application"))


def fetch(session: requests.Session, key: str, url: str) -> list[tuple[str, str]]:
    response = session.get(url, timeout=50, verify=False, allow_redirects=True)
    response.raise_for_status()
    text = response.text
    if len(text) < 120:
        raise RuntimeError("source returned insufficient content")
    items: list[tuple[str, str]] = []
    if "<rss" in text[:1000].casefold():
        root = ET.fromstring(text)
        for item in root.findall(".//item"):
            title = norm(item.findtext("title") or "")
            desc = norm(item.findtext("description") or "")
            link = norm(item.findtext("link") or "")
            combined = norm(f"{title} {desc}")
            # The search query is hard-coded to the official domain. Prefer a direct official
            # result URL; otherwise use the authority's official notices page for verification.
            official_urls = re.findall(r"https?://(?:www\.)?(?:ncismindia\.org|ncahp\.krispsoft\.com|[^/]*\.abdm\.gov\.in)[^\s<>'\"]*", combined)
            verify_url = official_urls[0].rstrip(".,);]") if official_urls else link
            if combined:
                items.append((combined, verify_url))
        return items

    # Jina Reader returns Markdown/plain text copied from the official target page. Preserve
    # the official target URL for alerts and fingerprints rather than the proxy URL.
    is_reader = urlparse(response.url).hostname == "r.jina.ai"
    official_target = ""
    if is_reader:
        match = re.search(r"https?://(?:www\.)?(?:ncismindia\.org|[^/]*\.abdm\.gov\.in)[^\s<>'\"]*", text)
        if match:
            official_target = match.group(0).rstrip(".,);]")
        elif key == "ncism":
            official_target = "https://www.ncismindia.org/circular-notification.php"
        else:
            official_target = "https://ahir.abdm.gov.in/"

    soup = BeautifulSoup(text, "html.parser")
    for a in soup.find_all("a"):
        title = norm(a.get_text(" ", strip=True))
        parent = a.find_parent(["tr", "li", "article", "section", "div"])
        parent_text = norm(parent.get_text(" ", strip=True)) if parent else ""
        if len(title) < 15 or low(title) in {"click here", "view", "view details", "read more", "download"}:
            title = parent_text or title
        link = urljoin(response.url, a.get("href", ""))
        if title and (is_reader or official(key, link)):
            items.append((title, official_target or link))
    body = soup.get_text("\n", strip=True)
    body_url = official_target or response.url
    items.extend((norm(line), body_url) for line in body.splitlines() if 8 <= len(norm(line)) <= 700)
    return items


def fingerprint(key: str, title: str, url: str) -> str:
    return hashlib.sha256(f"{key}\n{low(title)}\n{url}".encode()).hexdigest()[:24]


def load_state() -> dict:
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = {}
    state.setdefault("initialized", {})
    state.setdefault("seen", {})
    state.setdefault("last_checked", {})
    return state


def output(name: str, value: str) -> None:
    path = os.getenv("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")
    else:
        print(f"{name}={value}")


def main() -> int:
    ALERT.unlink(missing_ok=True)
    state = load_state()
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
    })
    now = datetime.now().astimezone()
    new: list[dict[str, str]] = []
    successes = 0

    for key, name, profile, urls in SOURCES:
        raw: list[tuple[str, str]] = []
        errors = []
        for url in urls:
            try:
                raw.extend(fetch(session, key, url))
            except Exception as exc:
                errors.append(f"{url}: {type(exc).__name__}: {exc}")
        if not raw:
            print(f"WARNING: {name} fallback could not be checked")
            for error in errors:
                print(f"  {error}")
            continue
        successes += 1
        found: dict[str, dict[str, str]] = {}
        for title, url in raw:
            if relevant(key, profile, title):
                ident = fingerprint(key, title, url)
                found.setdefault(ident, {"title": title, "url": url})
        previous = set(state["seen"].get(key, []))
        if state["initialized"].get(key):
            for ident, item in found.items():
                if ident not in previous:
                    new.append({**item, "source": name})
        else:
            state["initialized"][key] = True
            print(f"FALLBACK BASELINE: {name}: {len(found)} matching item(s)")
        state["seen"][key] = list(dict.fromkeys([*previous, *found.keys()]))[-1500:]
        state["last_checked"][key] = now.isoformat()
        print(f"FALLBACK CHECKED: {name}: {len(found)} matching")

    if not successes:
        output("fallback_has_alert", "false")
        print("No fallback source could be reached; state not saved.", file=sys.stderr)
        return 1
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if new:
        lines = ["## New official notice found through a blocked-site fallback", ""]
        for item in new:
            title, url = item["title"], item["url"]
            lines.append(f"### [{title}]({url})" if url else f"### {title}")
            lines.extend((f"- **Official authority:** {item['source']}", ""))
        lines.append("Verify the original notice, academic year, deadline, fee, documents and any later corrigendum before filing.")
        ALERT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        output("fallback_has_alert", "true")
    else:
        output("fallback_has_alert", "false")
        print("No new relevant fallback announcement.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

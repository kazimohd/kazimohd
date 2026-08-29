#!/usr/bin/env python3
"""Official NCAHP fallback for pages that may block the primary monitor."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import unicodedata
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

SOURCE_KEY = "ncahp"
SOURCE_NAME = "National Commission for Allied and Healthcare Professions"
OFFICIAL_URLS = (
    "https://ncahp.krispsoft.com/",
    "https://ncahp.krispsoft.com/act-rules--notifications",
    "https://ncahp.krispsoft.com/draftregulations",
    "https://ncahp.krispsoft.com/draft-cariculam",
    "https://ahir.abdm.gov.in/",
)
OFFICIAL_DOMAINS = ("ncahp.krispsoft.com", "abdm.gov.in", "mohfw.gov.in")

ACTION = (
    "application", "apply", "scheme", "proposal", "establishment", "establish",
    "new institution", "new college", "new course", "higher course", "opening of",
    "increase in intake", "increase in seats", "increase of seats", "intake capacity",
    "recognition", "permission", "affiliation", "last date", "deadline", "extension",
    "extended", "corrigendum", "institutional standards", "institutional registration",
    "अर्ज", "प्रस्ताव", "योजना", "स्थापना", "नवीन संस्था", "नवीन महाविद्यालय",
    "नवीन अभ्यासक्रम", "प्रवेश क्षमता", "मान्यता", "परवानगी", "संलग्नता", "मुदतवाढ",
)
PROGRAM = (
    "physiotherapy", "physical therapy", "mpt", "m.p.t", "allied health",
    "allied and healthcare", "allied & healthcare", "healthcare institution",
    "healthcare professional institution", "भौतिकोपचार", "फिजिओथेरपी", "एमपीटी",
)
INSTITUTIONAL = (
    "institution", "college", "course", "programme", "program", "recognition",
    "application", "registration of institution", "institutional registration",
)
EXCLUDE = (
    "recruitment", "vacancy", "empanelment of advocate", "member selection",
    "counselling", "admission schedule", "neet", "student", "professional conduct",
    "ethics", "individual enrolment", "public comments", "draft curriculum",
    "समुपदेशन", "भरती", "पदभरती", "विद्यार्थी",
)
GENERIC = {"view", "view details", "details", "read more", "download", "click here", "more"}


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", value).strip()


def low(value: str) -> str:
    return norm(value).casefold()


def has(text: str, terms: tuple[str, ...]) -> bool:
    return any(term.casefold() in text for term in terms)


def official(url: str) -> bool:
    host = (urlparse(url).hostname or "").casefold()
    return any(host == domain or host.endswith("." + domain) for domain in OFFICIAL_DOMAINS)


def relevant(title: str) -> bool:
    text = low(title)
    if not 8 <= len(text) <= 800:
        return False
    if not has(text, ACTION) or has(text, EXCLUDE):
        return False
    # A physiotherapy/MPT-specific notice is relevant. A common NCAHP institutional
    # application or recognition notice is also relevant because it may govern MPT colleges.
    return has(text, PROGRAM) or has(text, INSTITUTIONAL)


def fetch(session: requests.Session, url: str) -> list[tuple[str, str]]:
    response = session.get(url, timeout=(10, 35), verify=False, allow_redirects=True)
    response.raise_for_status()
    if len(response.text) < 150:
        raise RuntimeError("official page returned insufficient content")
    soup = BeautifulSoup(response.text, "html.parser")
    items: list[tuple[str, str]] = []
    for anchor in soup.find_all("a"):
        title = norm(anchor.get_text(" ", strip=True))
        parent = anchor.find_parent(["tr", "li", "article", "section", "div"])
        parent_text = norm(parent.get_text(" ", strip=True)) if parent else ""
        if low(title) in GENERIC or len(title) < 12:
            title = parent_text or title
        link = urljoin(response.url, anchor.get("href", ""))
        if title and official(link):
            items.append((title, link))
    body = soup.get_text("\n", strip=True)
    items.extend((norm(line), response.url) for line in body.splitlines() if 8 <= len(norm(line)) <= 600)
    return items


def fingerprint(title: str, url: str) -> str:
    return hashlib.sha256(f"{SOURCE_KEY}\n{low(title)}\n{url}".encode()).hexdigest()[:24]


def load_state() -> dict:
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    data.setdefault("initialized", {})
    data.setdefault("seen", {})
    data.setdefault("last_checked", {})
    return data


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
        "User-Agent": "Mozilla/5.0 (compatible; HealthEducationNoticeMonitor/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
    })

    raw: list[tuple[str, str]] = []
    errors: list[str] = []
    for url in OFFICIAL_URLS:
        try:
            raw.extend(fetch(session, url))
        except Exception as exc:
            errors.append(f"{url}: {type(exc).__name__}: {exc}")

    if not raw:
        output("fallback_has_alert", "false")
        print(f"WARNING: {SOURCE_NAME} fallback could not be checked", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 1

    found: dict[str, dict[str, str]] = {}
    for title, url in raw:
        if relevant(title):
            ident = fingerprint(title, url)
            found.setdefault(ident, {"title": title, "url": url})

    now = datetime.now().astimezone()
    previous = set(state["seen"].get(SOURCE_KEY, []))
    new: list[dict[str, str]] = []
    if state["initialized"].get(SOURCE_KEY):
        for ident, item in found.items():
            if ident not in previous:
                new.append(item)
    else:
        state["initialized"][SOURCE_KEY] = True
        print(f"FALLBACK BASELINE: {SOURCE_NAME}: {len(found)} matching item(s)")

    state["seen"][SOURCE_KEY] = list(dict.fromkeys([*previous, *found.keys()]))[-1500:]
    state["last_checked"][SOURCE_KEY] = now.isoformat()
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"FALLBACK CHECKED: {SOURCE_NAME}: {len(found)} matching, {len(new)} new")

    if new:
        lines = ["## New NCAHP institutional notice detected", ""]
        for item in new:
            title, url = item["title"], item["url"]
            lines.append(f"### [{title}]({url})" if url else f"### {title}")
            lines.extend((f"- **Official authority:** {SOURCE_NAME}", ""))
        lines.append("Verify the original notice, academic year, deadline, fee, documents and any later corrigendum before filing.")
        ALERT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        output("fallback_has_alert", "true")
    else:
        output("fallback_has_alert", "false")
        print("No new relevant NCAHP announcement.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

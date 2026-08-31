#!/usr/bin/env python3
"""Alert only on new institutional notices and filing-date extensions relevant to monitored proposals."""
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
STATE = ROOT / "state.json"
ALERT = ROOT / "alert.md"

SOURCES = [
    ("nmc", "National Medical Commission", "mbbs", [
        "https://www.nmc.org.in/all-news/",
        "https://www.nmc.org.in/online-application-submit/",
    ]),
    ("ndc", "National Dental Commission", "bds", [
        "https://dciindia.gov.in/NewsSection.aspx?NewsType=Public+Notice",
    ]),
    ("ncism", "National Commission for Indian System of Medicine", "ayurveda_pg", [
        "https://ncismindia.org/circular-notification.php",
        "https://ncismindia.org/archives.php",
        "https://ncismindia.org/index.php",
        "https://www.ncismindia.org/circular-notification.php",
    ]),
    ("inc", "Indian Nursing Council", "nursing", [
        "https://www.indiannursingcouncil.org/special-attention",
        "https://www.indiannursingcouncil.org/online-application-forms",
    ]),
    ("ncahp", "National Commission for Allied and Healthcare Professions", "mpt", [
        "https://ahir.abdm.gov.in/",
        "https://ahir.abdm.gov.in/about-ncahp",
    ]),
    ("muhs", "Maharashtra University of Health Sciences", "all", [
        "https://muhs.ac.in/", "https://www.muhs.ac.in/",
    ]),
    ("medd", "Maharashtra Medical Education and Drugs Department", "all", [
        "https://medical.maharashtra.gov.in/",
    ]),
    ("dmer", "Directorate of Medical Education and Research, Maharashtra", "all", [
        "https://dmer.maharashtra.gov.in/english/",
        "https://dmer.maharashtra.gov.in/",
    ]),
    ("mnc", "Maharashtra Nursing Council", "nursing", [
        "https://maharashtranursingcouncil.org/notifications",
    ]),
    ("msotpt", "Maharashtra State OT/PT Council", "mpt", [
        "https://www.mahaotandptcouncil.in/",
    ]),
]

ACTION = (
    "application", "apply", "scheme", "proposal", "establishment", "establish",
    "new college", "new institution", "new course", "higher course", "opening of",
    "increase in seats", "increase of seats", "increase intake", "intake capacity",
    "enhancement of seats", "suitability", "recognition", "permission",
    "essentiality certificate", "no objection certificate", "consent of affiliation",
    "first time affiliation", "affiliation", "section 64", "last date", "deadline",
    "submission window", "extension", "extended", "corrigendum", "online application",
    "reopening", "re-open", "revised date", "revised schedule", "addendum",
    "अर्ज", "आवेदन", "प्रस्ताव", "योजना", "स्थापना", "नवीन महाविद्यालय",
    "नवीन संस्था", "नवीन अभ्यासक्रम", "उच्च अभ्यासक्रम", "जागांमध्ये वाढ",
    "प्रवेश क्षमता", "मान्यता", "परवानगी", "ना हरकत", "संलग्नता",
    "प्रथम वेळ संलग्नता", "कलम 64", "कलम ६४", "अंतिम मुदत", "मुदतवाढ",
    "मुदत वाढ", "शिफारस", "अधिसूचना", "जाहीर सूचना",
)

# These phrases are checked independently from ordinary application notices. This catches
# extensions, reopened portals, late-fee windows, corrigenda and revised filing schedules.
EXTENSION_TERMS = (
    "extension of last date", "last date is extended", "last date has been extended",
    "last date extended", "extended last date", "date is extended", "date has been extended",
    "date extended", "deadline extended", "extension of deadline", "extension of time",
    "time extension", "extension of timeline", "timeline extended", "revised last date",
    "revised deadline", "revised date", "revised timeline", "revised schedule",
    "submission date extended", "application date extended", "application window extended",
    "application window reopened", "application window re-opened", "portal reopened",
    "portal re-opened", "reopening of portal", "re-opening of portal", "reopen the portal",
    "with late fee", "late fee date", "late-fee date", "corrigendum", "addendum",
    "मुदतवाढ", "मुदत वाढ", "अंतिम मुदत वाढ", "अंतिम दिनांक वाढ",
    "अर्जाची मुदत वाढ", "अर्ज सादर करण्याची मुदत", "वाढीव मुदत",
    "सुधारित अंतिम दिनांक", "सुधारित अंतिम मुदत", "सुधारित वेळापत्रक",
    "पोर्टल पुन्हा सुरू", "उशिरा शुल्क", "विलंब शुल्क",
    "अंतिम तिथि बढ़ाई", "अंतिम तिथि का विस्तार", "समय सीमा बढ़ाई",
    "समय-सीमा बढ़ाई", "अवधि विस्तार", "संशोधित अंतिम तिथि",
    "संशोधित समय-सारणी", "पोर्टल पुनः खोला", "पोर्टल दोबारा खोला",
)

EXCLUDE = (
    "counselling", "counseling", "admission schedule", "choice filling", "merit list",
    "seat matrix", "neet", "exam centre", "exam center", "student registration",
    "hall ticket", "result", "award", "recruitment", "vacancy", "webinar", "campaign",
    "appeal", "annual disclosure", "biometric", "anti-ragging", "internship", "faculty",
    "stipend", "ph.d", "phd", "candidate", "scholarship", "समुपदेशन",
    "प्रवेश वेळापत्रक", "गुणवत्ता यादी", "परीक्षा केंद्र", "निकाल", "भरती", "पुरस्कार",
)

PROGRAM = {
    "mbbs": (
        "mbbs", "medical college", "undergraduate medical", "ug medical",
        "वैद्यकीय महाविद्यालय", "एमबीबीएस", "एम.बी.बी.एस",
    ),
    "bds": (
        "bds", "dental college", "dental institution", "दंत महाविद्यालय",
        "बीडीएस", "बी.डी.एस",
    ),
    "ayurveda_pg": (
        "new pg course", "new postgraduate course", "open new pg", "opening of new pg",
        "higher course", "pg course", "post graduate course", "postgraduate course",
        "increase in pg", "increase of pg", "md (ayu", "ms (ayu", "m.d. (ayu",
        "m.s. (ayu", "आयुर्वेद पदव्युत्तर", "पदव्युत्तर अभ्यासक्रम", "नवीन पीजी",
    ),
    "nursing": (
        "nursing", "m.sc nursing", "m.sc. nursing", "msc nursing", "post basic b.sc",
        "post basic bsc", "p.b.b.sc", "p b b sc", "nursing programme", "nursing program",
        "परिचर्या", "नर्सिंग", "suitability", "section 13", "section 14", "snrc",
    ),
    "mpt": (
        "physiotherapy", "physical therapy", "mpt", "m.p.t", "allied health",
        "allied and healthcare", "भौतिकोपचार", "फिजिओथेरपी", "एमपीटी", "एम.पी.टी",
    ),
}
PROGRAM["all"] = tuple(dict.fromkeys(sum(PROGRAM.values(), ())))

PROGRAM_CONTEXT = {"inc", "mnc", "ncahp", "msotpt"}
GENERAL_HEALTH_AUTHORITIES = {"muhs", "medd", "dmer"}
GENERAL_INSTITUTIONAL = (
    "section 64", "कलम 64", "कलम ६४", "new college", "new institution", "new course",
    "higher course", "increase in seats", "increase of seats", "intake capacity",
    "proposal", "scheme", "consent of affiliation", "first time affiliation",
    "essentiality certificate", "no objection certificate", "प्रस्ताव", "योजना",
    "नवीन महाविद्यालय", "नवीन संस्था", "नवीन अभ्यासक्रम", "प्रवेश क्षमता",
    "संलग्नता", "ना हरकत",
)
DEADLINE_SCOPE = tuple(dict.fromkeys(GENERAL_INSTITUTIONAL + (
    "application", "online application", "submission of application",
    "submission of applications", "application form", "application forms",
    "submit proposal", "submission of proposal", "submission of proposals",
    "permission", "recommendation", "affiliation", "suitability", "recognition",
    "essentiality", "noc", "registration of institution", "institutional registration",
    "portal", "window", "late fee", "अर्ज", "आवेदन", "प्रस्ताव सादर",
    "मान्यता", "परवानगी", "शिफारस", "संलग्नता", "पोर्टल",
)))
GENERIC_LINK = {"view", "view details", "details", "read more", "download", "click here", "more"}


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", value).strip()


def low(value: str) -> str:
    return norm(value).casefold()


def any_term(text: str, terms: tuple[str, ...]) -> bool:
    return any(term.casefold() in text for term in terms)


def extension_notice(key: str, profile: str, title: str) -> bool:
    """Return True only for filing-date extensions relevant to the monitored proposals."""
    text = low(title)
    if not 8 <= len(text) <= 900 or not any_term(text, EXTENSION_TERMS):
        return False

    # Student admissions, counselling, examinations and recruitment date changes are not
    # institutional proposal deadlines and must remain silent.
    if any_term(text, EXCLUDE):
        return False

    if any_term(text, PROGRAM[profile]):
        return True

    # Nursing and allied-health authority pages are already programme-specific. A generic
    # institutional application extension on those pages may govern the monitored course.
    if key in PROGRAM_CONTEXT and any_term(text, DEADLINE_SCOPE):
        return True

    # MUHS and Maharashtra authorities often issue generic Section 64/affiliation/proposal
    # extension notices covering several health-science programmes together.
    if key in GENERAL_HEALTH_AUTHORITIES and any_term(text, DEADLINE_SCOPE):
        return True

    return False


def relevant(key: str, profile: str, title: str) -> bool:
    text = low(title)
    if extension_notice(key, profile, title):
        return True
    if not 8 <= len(text) <= 800 or not any_term(text, ACTION):
        return False

    has_program = any_term(text, PROGRAM[profile])
    if key in PROGRAM_CONTEXT:
        has_program = True
    if key in GENERAL_HEALTH_AUTHORITIES and any_term(text, GENERAL_INSTITUTIONAL):
        has_program = True
    if not has_program:
        return False

    if any_term(text, EXCLUDE):
        strong = (
            "establishment", "new college", "new institution", "new course", "higher course",
            "increase in seats", "increase of seats", "scheme", "proposal", "suitability",
            "permission", "affiliation", "essentiality", "extension", "reopening",
            "नवीन महाविद्यालय", "नवीन अभ्यासक्रम", "प्रस्ताव", "मान्यता",
            "परवानगी", "संलग्नता", "मुदतवाढ",
        )
        if not any_term(text, strong):
            return False

    # The Ayurveda case is opening PG courses in an existing college. A notice only about
    # establishing a new undergraduate Ayurveda college must not trigger an alert.
    return profile != "ayurveda_pg" or any_term(text, PROGRAM["ayurveda_pg"])


def clean_url(base: str, href: str) -> str:
    href = norm(href)
    if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
        return ""
    absolute = urljoin(base, href)
    return absolute if urlparse(absolute).scheme in {"http", "https"} else ""


def request_official_page(session: requests.Session, url: str) -> requests.Response:
    """Fetch an official page, satisfying NCISM's simple JavaScript cookie challenge."""
    response = session.get(url, timeout=(8, 30), verify=False, allow_redirects=True)

    if response.status_code == 409 and "document.cookie" in response.text:
        matches = re.findall(
            r"document\.cookie\s*=\s*[\"']([^=;\"']+)=([^;\"']+)",
            response.text,
            flags=re.IGNORECASE,
        )
        if not matches and "humans_21909" in response.text:
            matches = [("humans_21909", "1")]

        host = urlparse(response.url).hostname or urlparse(url).hostname or ""
        for name, value in matches:
            session.cookies.set(name.strip(), value.strip(), domain=host, path="/")
        if matches:
            response = session.get(
                url,
                timeout=(8, 30),
                verify=False,
                allow_redirects=True,
                headers={"Referer": response.url},
            )

    response.raise_for_status()
    if "document.cookie" in response.text and "location.reload" in response.text:
        raise RuntimeError("official page cookie challenge was not satisfied")
    return response


def fetch(session: requests.Session, url: str) -> list[tuple[str, str]]:
    response = request_official_page(session, url)
    if len(response.text) < 150:
        raise RuntimeError("official page returned insufficient content")

    soup = BeautifulSoup(response.text, "html.parser")
    items: list[tuple[str, str]] = []
    for anchor in soup.find_all("a"):
        title = norm(anchor.get_text(" ", strip=True))
        parent = anchor.find_parent(["tr", "li", "article", "section", "div"])
        parent_text = norm(parent.get_text(" ", strip=True)) if parent else ""
        if low(title) in GENERIC_LINK or len(title) < 12:
            title = parent_text or title
        elif parent_text and len(parent_text) <= 700 and title.casefold() not in parent_text.casefold():
            title = f"{title} {parent_text}"
        if title:
            items.append((title, clean_url(response.url, anchor.get("href", ""))))

    body = soup.get_text("\n", strip=True)
    items.extend((norm(line), "") for line in body.splitlines() if 8 <= len(norm(line)) <= 600)
    return items


def fingerprint(key: str, title: str, url: str) -> str:
    return hashlib.sha256(f"{key}\n{low(title)}\n{url}".encode()).hexdigest()[:24]


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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
    })

    alerts: dict[tuple[str, str, str], dict[str, str]] = {}
    successful_sources = 0
    now = datetime.now().astimezone()

    for key, name, profile, urls in SOURCES:
        raw: list[tuple[str, str]] = []
        errors: list[str] = []
        for url in urls:
            try:
                raw.extend(fetch(session, url))
            except Exception as exc:
                errors.append(f"{url}: {type(exc).__name__}: {exc}")

        if not raw:
            print(f"WARNING: {name} could not be checked")
            for error in errors:
                print(f"  {error}")
            continue

        successful_sources += 1
        found: dict[str, dict[str, str]] = {}
        for title, url in raw:
            if relevant(key, profile, title):
                ident = fingerprint(key, title, url)
                kind = "Deadline extension / reopening / corrigendum" if extension_notice(
                    key, profile, title
                ) else "New application / permission notice"
                found.setdefault(
                    ident,
                    {"fingerprint": ident, "title": title, "url": url, "kind": kind},
                )

        previous = set(state["seen"].get(key, []))
        if state["initialized"].get(key):
            for ident, item in found.items():
                if ident not in previous:
                    alerts[(name, item["title"], item["url"])] = {**item, "source": name}
        else:
            state["initialized"][key] = True
            print(f"BASELINE: {name}: {len(found)} matching item(s)")

        state["seen"][key] = list(dict.fromkeys([*previous, *found.keys()]))[-3000:]
        state["last_checked"][key] = now.isoformat()
        extension_count = sum(
            1 for item in found.values()
            if item["kind"] == "Deadline extension / reopening / corrigendum"
        )
        print(
            f"CHECKED: {name}: {len(found)} matching "
            f"({extension_count} extension/reopening), "
            f"{len(set(found) - previous) if previous else 0} new"
        )

    if not successful_sources:
        output("has_alert", "false")
        print("No official source could be reached; state not saved.", file=sys.stderr)
        return 1

    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    new = list(alerts.values())
    if new:
        extension_total = sum(
            1 for item in new
            if item["kind"] == "Deadline extension / reopening / corrigendum"
        )
        heading = (
            "## Official deadline extension or reopening detected"
            if extension_total == len(new)
            else "## New official regulatory announcement detected"
        )
        lines = [
            heading, "",
            f"**Checked:** {now.strftime('%d %B %Y, %I:%M %p %Z')}", "",
        ]
        for item in new:
            title, url = item["title"], item["url"]
            lines.append(f"### [{title}]({url})" if url else f"### {title}")
            lines.extend((
                f"- **Alert type:** {item['kind']}",
                f"- **Official source:** {item['source']}",
                "",
            ))
        lines.extend((
            "Open the official notice and verify the academic year, original last date, "
            "extended/revised last date, late-fee period, fees, documents, portal and any "
            "later corrigendum before filing.",
            "",
            "This alert contains only publicly issued regulatory information and no institutional case documents.",
        ))
        ALERT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        output("has_alert", "true")
        output("alert_count", str(len(new)))
        output("extension_alert_count", str(extension_total))
    else:
        output("has_alert", "false")
        output("alert_count", "0")
        output("extension_alert_count", "0")
        print("No new relevant announcement or deadline extension.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

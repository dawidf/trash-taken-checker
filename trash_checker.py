import os
import re
import sys
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

SCHEDULE_URL = os.environ["SCHEDULE_URL"]
STREET = os.environ["STREET"].strip().upper()
CAL_POJEMNIKI = os.environ["CAL_POJEMNIKI"]
CAL_SEGREGACJA = os.environ["CAL_SEGREGACJA"]
SUMMARY_POJEMNIKI = os.environ["SUMMARY_POJEMNIKI"]
SUMMARY_SEGREGACJA = os.environ["SUMMARY_SEGREGACJA"]
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")

HA_API = "http://supervisor/core/api"
HA_HEADERS = {
    "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
    "Content-Type": "application/json",
}

ROMAN_MONTHS = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6,
    "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12,
}
ROMAN_TOKEN = r"[IVXL]{1,4}"

RANGE_RE = re.compile(
    rf"(?P<d1>\d{{1,2}})\s*(?P<m1>{ROMAN_TOKEN})?-\s*(?P<d2>\d{{1,2}})\s+(?P<m2>{ROMAN_TOKEN})"
)
SINGLE_RE = re.compile(rf"(?P<d>\d{{1,2}})\s+(?P<m>{ROMAN_TOKEN})")
YEAR_RE = re.compile(rf"{ROMAN_TOKEN}\s*-\s*{ROMAN_TOKEN}\s+(\d{{4}})")


def fetch_page():
    resp = requests.get(SCHEDULE_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return resp.text


def find_year(soup):
    match = YEAR_RE.search(soup.get_text())
    if match:
        return int(match.group(1))
    return date.today().year


def find_street_text(soup):
    # The source HTML has unclosed <p> tags, which makes BeautifulSoup nest
    # elements inconsistently. Sibling/parent traversal is unreliable here,
    # so we work on the fully linearized text instead, using heading text
    # positions as section boundaries.
    full_text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    headings = [
        re.sub(r"\s+", " ", h3.get_text(" ", strip=True)).strip()
        for h3 in soup.find_all("h3")
    ]
    headings = [h for h in headings if h]

    target_idx = None
    for i, heading in enumerate(headings):
        if STREET in heading.upper():
            target_idx = i
            break

    if target_idx is None:
        return None, headings

    start_pos = full_text.find(headings[target_idx])
    if start_pos == -1:
        return None, headings
    start_pos += len(headings[target_idx])

    end_pos = len(full_text)
    for heading in headings[target_idx + 1 :]:
        pos = full_text.find(heading, start_pos)
        if pos != -1:
            end_pos = pos
            break

    return full_text[start_pos:end_pos].strip(), headings


def extract_dates(text, year):
    if not text:
        return []

    results = []
    masked = text

    for m in RANGE_RE.finditer(text):
        m2 = m.group("m2")
        m1 = m.group("m1") or m2
        if m1 not in ROMAN_MONTHS or m2 not in ROMAN_MONTHS:
            continue
        try:
            start = date(year, ROMAN_MONTHS[m1], int(m.group("d1")))
        except ValueError:
            continue
        # A "from-to" range on the site (e.g. "9-10 IX") only ever means a
        # single pickup that may happen on either day, so only the first
        # day is recorded.
        results.append(start)
        span = m.span()
        masked = masked[: span[0]] + " " * (span[1] - span[0]) + masked[span[1] :]

    for m in SINGLE_RE.finditer(masked):
        mon = m.group("m")
        if mon not in ROMAN_MONTHS:
            continue
        try:
            results.append(date(year, ROMAN_MONTHS[mon], int(m.group("d"))))
        except ValueError:
            continue

    return sorted(set(results))


def split_sections(text):
    match = re.search(r"segregacj[ai]", text, flags=re.IGNORECASE)
    if not match:
        return text, ""
    return text[: match.start()], text[match.start() :]


def get_existing_dates(entity_id, start, end):
    url = f"{HA_API}/calendars/{entity_id}"
    params = {
        "start": f"{start.isoformat()}T00:00:00",
        "end": f"{end.isoformat()}T00:00:00",
    }
    resp = requests.get(url, headers=HA_HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    existing = set()
    for event in resp.json():
        raw = event.get("start")
        if isinstance(raw, dict):
            raw = raw.get("date") or raw.get("dateTime")
        if raw:
            existing.add(raw[:10])
    return existing


def create_event(entity_id, summary, day):
    url = f"{HA_API}/services/calendar/create_event"
    body = {
        "entity_id": entity_id,
        "summary": summary,
        "start_date": day.isoformat(),
        "end_date": (day + timedelta(days=1)).isoformat(),
    }
    resp = requests.post(url, headers=HA_HEADERS, json=body, timeout=30)
    resp.raise_for_status()


def sync_calendar(entity_id, summary, days):
    days = [d for d in days if d >= date.today()]
    if not days:
        print(f"Brak nadchodzących dat dla {entity_id}.")
        return

    existing = get_existing_dates(entity_id, min(days), max(days) + timedelta(days=1))
    added = 0
    for day in days:
        if day.isoformat() in existing:
            continue
        create_event(entity_id, summary, day)
        added += 1
        print(f"Dodano wydarzenie: {entity_id} -> {day.isoformat()} ({summary})")

    print(f"{entity_id}: dodano {added} nowych wydarzeń, pominięto {len(days) - added} istniejących.")


def main():
    html = fetch_page()
    soup = BeautifulSoup(html, "html.parser")

    year = find_year(soup)
    section_text, headings = find_street_text(soup)

    if section_text is None:
        print(f"Nie znaleziono sekcji dla ulicy '{STREET}'. Dostępne nagłówki: {headings}", file=sys.stderr)
        sys.exit(1)

    pojemniki_text, segregacja_text = split_sections(section_text)

    pojemniki_dates = extract_dates(pojemniki_text, year)
    segregacja_dates = extract_dates(segregacja_text, year)

    print(f"Rok harmonogramu: {year}")
    print(f"Pojemniki: {[d.isoformat() for d in pojemniki_dates]}")
    print(f"Segregacja: {[d.isoformat() for d in segregacja_dates]}")

    if not pojemniki_dates and not segregacja_dates:
        print(f"Nie znaleziono żadnych dat dla ulicy '{STREET}'.", file=sys.stderr)
        sys.exit(1)

    sync_calendar(CAL_POJEMNIKI, SUMMARY_POJEMNIKI, pojemniki_dates)
    sync_calendar(CAL_SEGREGACJA, SUMMARY_SEGREGACJA, segregacja_dates)


if __name__ == "__main__":
    main()

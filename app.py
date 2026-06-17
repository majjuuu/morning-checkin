"""
Morning Check-in — a peaceful local space to greet your day and reflect on it.

Reads today's events from a Google Calendar private iCal feed, offers a warm
note, and saves your daily reflections (3 wins + 1 thing to improve) to a
dated file so they build up into a little history over time.
"""
import json
import random
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
import icalendar
import recurring_ical_events
from flask import Flask, render_template, request, jsonify

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
JOURNAL_DIR = BASE_DIR / "journal"
JOURNAL_DIR.mkdir(exist_ok=True)

app = Flask(__name__)

# A small rotating set of gentle, motivating greetings.
GREETINGS = [
    "Good morning. However today unfolds, you get to meet it one breath at a time.",
    "A fresh page is open. There's no rush — just begin where you are.",
    "Morning. You've already done the hardest part: showing up for your day.",
    "Take a slow breath. Today is allowed to be soft and still count.",
    "Good morning. You don't have to do it all — just the next kind thing.",
    "A new day, quietly yours. Let's ease into it together.",
    "Morning light, fresh start. You're more ready than you feel.",
    "Hello, today. May it be gentle, and may you be gentle with yourself.",
]

# Warm notes shown alongside the schedule, chosen by how full the day looks.
NOTES_LIGHT = [
    "A spacious day ahead — room to breathe, wander, and choose your pace.",
    "Not much on the calendar. That open space is a gift, not a gap to fill.",
    "A calm schedule today. Let yourself enjoy the quiet between moments.",
]
NOTES_BALANCED = [
    "A nicely balanced day — enough to feel purposeful, enough to feel free.",
    "You've got a gentle rhythm ahead. Move through it one moment at a time.",
    "A few things to tend to, with breathing room in between. You've got this.",
]
NOTES_FULL = [
    "A full day ahead — pace yourself, and remember to pause and drink some water.",
    "Lots on the horizon today. You don't have to carry it all at once.",
    "A busy day, but you only ever have to do the next thing. One at a time.",
]


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def get_tz(cfg):
    try:
        return ZoneInfo(cfg.get("timezone") or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def fetch_todays_events(cfg, today, tz):
    """Return a sorted list of today's events from the iCal feed.

    Each event is a dict: {time_label, sort_key, summary, location, all_day}.
    Raises on network/parse errors so the caller can show a friendly message.
    """
    url = (cfg.get("ical_url") or "").strip()
    if not url or url.startswith("PASTE_"):
        raise RuntimeError("no-url")

    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    calendar = icalendar.Calendar.from_ical(resp.text)

    # Expand recurring events just for today's window.
    occurrences = recurring_ical_events.of(calendar).at(today)

    events = []
    for component in occurrences:
        summary = str(component.get("summary", "(untitled)"))
        location = str(component.get("location", "")).strip()
        start = component.get("dtstart")
        start_val = start.dt if start is not None else None

        if isinstance(start_val, dt.datetime):
            local = start_val.astimezone(tz) if start_val.tzinfo else start_val.replace(tzinfo=tz)
            time_label = local.strftime("%-I:%M %p").lower()
            sort_key = local.strftime("%H:%M")
            all_day = False
        else:
            time_label = "all day"
            sort_key = "00:00"
            all_day = True

        events.append({
            "time_label": time_label,
            "sort_key": sort_key,
            "summary": summary,
            "location": location,
            "all_day": all_day,
        })

    events.sort(key=lambda e: (not e["all_day"] is True, e["sort_key"]))
    # Put all-day items first, then timed events in order.
    events.sort(key=lambda e: (0 if e["all_day"] else 1, e["sort_key"]))
    return events


def note_for_day(events):
    count = len([e for e in events if not e["all_day"]])
    if count <= 1:
        return random.choice(NOTES_LIGHT)
    if count <= 4:
        return random.choice(NOTES_BALANCED)
    return random.choice(NOTES_FULL)


def journal_path(date_str):
    return JOURNAL_DIR / f"{date_str}.json"


@app.route("/")
def index():
    cfg = load_config()
    tz = get_tz(cfg)
    now = dt.datetime.now(tz)
    today = now.date()
    date_str = today.isoformat()

    calendar_error = None
    events = []
    try:
        events = fetch_todays_events(cfg, today, tz)
    except RuntimeError:
        calendar_error = "no-url"
    except Exception:
        calendar_error = "fetch-failed"

    note = note_for_day(events) if not calendar_error else random.choice(NOTES_BALANCED)

    # Load any reflection already saved for today.
    saved = None
    jp = journal_path(date_str)
    if jp.exists():
        try:
            saved = json.loads(jp.read_text(encoding="utf-8"))
        except Exception:
            saved = None

    return render_template(
        "index.html",
        greeting=random.choice(GREETINGS),
        note=note,
        events=events,
        calendar_error=calendar_error,
        date_pretty=now.strftime("%A, %B %-d"),
        date_str=date_str,
        display_name=(cfg.get("display_name") or "").strip(),
        saved=saved,
    )


@app.route("/save", methods=["POST"])
def save():
    data = request.get_json(force=True) or {}
    date_str = data.get("date") or dt.date.today().isoformat()
    wins = [str(w).strip() for w in data.get("wins", [])]
    improve = str(data.get("improve", "")).strip()

    entry = {
        "date": date_str,
        "wins": wins,
        "improve": improve,
        "saved_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    journal_path(date_str).write_text(
        json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return jsonify({"ok": True})


if __name__ == "__main__":
    print("\n  🌿 Morning Check-in is ready at  http://127.0.0.1:5001\n")
    app.run(host="127.0.0.1", port=5001, debug=False)

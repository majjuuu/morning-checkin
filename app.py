"""
Morning Check-in — a peaceful local space to greet your day and reflect on it.

Reads today's events from a Google Calendar private iCal feed, offers a warm
note, and saves your daily reflections (3 wins + 1 thing to improve) to a
dated file so they build up into a little history over time.
"""
import os
import json
import time
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
import icalendar
import recurring_ical_events
from flask import Flask, render_template, request, jsonify

import email_handler

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
JOURNAL_DIR = BASE_DIR / "journal"
JOURNAL_DIR.mkdir(exist_ok=True)
WEEKLY_PATH = BASE_DIR / "weekly.json"

app = Flask(__name__)

# A rotating set of gentle, motivating greetings — one per day, by date.
GREETINGS = [
    "Good morning. However today unfolds, you get to meet it one breath at a time.",
    "A fresh page is open. There's no rush — just begin where you are.",
    "Morning. You've already done the hardest part: showing up for your day.",
    "Take a slow breath. Today is allowed to be soft and still count.",
    "Good morning. You don't have to do it all — just the next kind thing.",
    "A new day, quietly yours. Let's ease into it together.",
    "Morning light, fresh start. You're more ready than you feel.",
    "Hello, today. May it be gentle, and may you be gentle with yourself.",
    "Good morning. Progress, not perfection — a little forward is still forward.",
    "Today doesn't need to be big. Small and steady is its own kind of brave.",
    "Morning. Whatever yesterday was, today gets to be its own thing.",
    "You woke up and chose to check in with yourself. That already matters.",
    "A gentle good morning. Trust that you'll figure out today as it comes.",
    "New light, new chance. Be as kind to yourself as you'd be to a friend.",
    "Morning. You've carried hard days before — you know how to do this.",
    "Good morning. Let today be about showing up, not about being perfect.",
    "Breathe in, breathe out. You're exactly where you need to begin.",
    "A soft start to a brand-new day. One small good thing at a time.",
    "Morning. You are allowed to go at your own pace today.",
    "Good morning. Somewhere in today there's a moment worth smiling at.",
    "Here's to today — may you meet it with calm hands and an open heart.",
]

# Warm notes shown alongside the schedule, chosen by how full the day looks.
NOTES_LIGHT = [
    "A spacious day ahead — room to breathe, wander, and choose your pace.",
    "Not much on the calendar. That open space is a gift, not a gap to fill.",
    "A calm schedule today. Let yourself enjoy the quiet between moments.",
    "An open day. Rest counts as a good use of it too.",
    "Light and airy today — follow what feels gentle and good.",
    "A quiet stretch ahead. Let it be slow; you've earned a softer day.",
]
NOTES_BALANCED = [
    "A nicely balanced day — enough to feel purposeful, enough to feel free.",
    "You've got a gentle rhythm ahead. Move through it one moment at a time.",
    "A few things to tend to, with breathing room in between. You've got this.",
    "A steady-looking day. Take the small wins as they come.",
    "Some plans, some space — a good shape for a day. Ease into it.",
    "Enough to do to feel good, with room to breathe. You're set.",
]
NOTES_FULL = [
    "A full day ahead — pace yourself, and remember to pause and drink some water.",
    "Lots on the horizon today. You don't have to carry it all at once.",
    "A busy day, but you only ever have to do the next thing. One at a time.",
    "A packed day — be sure to steal a few small moments just for you.",
    "Plenty on today's plate. Breathe between things; you don't have to rush.",
    "A bustling day ahead. Go gently — done is enough, perfect isn't required.",
]


# "What filled your day?" tags shown in the reflection. id == icon filename stem.
ACTIVITIES = [
    {"id": "capybara", "label": "Cozy"},
    {"id": "basketball", "label": "Basketball"},
    {"id": "cooking", "label": "Cooking"},
    {"id": "shopping", "label": "Shopping"},
    {"id": "makeup", "label": "Makeup"},
    {"id": "journaling", "label": "Journaling"},
    {"id": "gym", "label": "Gym"},
    {"id": "study", "label": "Study"},
]
ACTIVITY_IDS = {a["id"] for a in ACTIVITIES}

# A little companion that greets you each day — capybara shows up most often.
COMPANIONS = [
    "capybara", "basketball", "capybara", "cooking",
    "capybara", "shopping", "capybara", "makeup",
    "capybara", "journaling",
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


def pick_for_day(options, today, salt=0):
    """Pick one item, stable for a given date but rotating day to day.

    Indexing by the date's ordinal means each day gets a different item than
    the day before, cycling through the whole list — never random within a day.
    `salt` offsets different fields (e.g. greeting vs note) so they don't move
    in lockstep.
    """
    if not options:
        return ""
    return options[(today.toordinal() + salt) % len(options)]


def note_for_day(events, today):
    count = len([e for e in events if not e["all_day"]])
    if count <= 1:
        return pick_for_day(NOTES_LIGHT, today, salt=1)
    if count <= 4:
        return pick_for_day(NOTES_BALANCED, today, salt=1)
    return pick_for_day(NOTES_FULL, today, salt=1)


# --- Weather (Open-Meteo, no API key needed) ---
# WMO weather code -> (emoji icon, short phrase)
_WMO = {
    0: ("☀️", "clear skies"),
    1: ("🌤️", "mostly clear"),
    2: ("⛅", "partly cloudy"),
    3: ("☁️", "overcast"),
    45: ("🌫️", "foggy"), 48: ("🌫️", "foggy"),
    51: ("🌦️", "light drizzle"), 53: ("🌦️", "drizzle"), 55: ("🌦️", "heavy drizzle"),
    56: ("🌧️", "freezing drizzle"), 57: ("🌧️", "freezing drizzle"),
    61: ("🌧️", "light rain"), 63: ("🌧️", "rain"), 65: ("🌧️", "heavy rain"),
    66: ("🌧️", "freezing rain"), 67: ("🌧️", "freezing rain"),
    71: ("🌨️", "light snow"), 73: ("🌨️", "snow"), 75: ("❄️", "heavy snow"), 77: ("🌨️", "snow grains"),
    80: ("🌦️", "rain showers"), 81: ("🌦️", "rain showers"), 82: ("⛈️", "heavy showers"),
    85: ("🌨️", "snow showers"), 86: ("🌨️", "snow showers"),
    95: ("⛈️", "thunderstorms"), 96: ("⛈️", "thunderstorms"), 99: ("⛈️", "thunderstorms"),
}

_weather_cache = {"ts": 0.0, "data": None}


def _weather_line(temp, phrase, label):
    """A warm one-line description from temp + condition."""
    if temp <= 2:
        tip = "bundle up warm"
    elif temp <= 10:
        tip = "a jacket would be wise"
    elif temp <= 18:
        tip = "maybe a light layer"
    elif temp <= 27:
        tip = "lovely and mild"
    else:
        tip = "stay cool and hydrated"
    return f"{phrase.capitalize()} and {temp}° in {label} — {tip}."


def fetch_weather(cfg):
    """Current weather for the configured spot, cached for 15 minutes."""
    now = time.time()
    if _weather_cache["data"] is not None and now - _weather_cache["ts"] < 900:
        return _weather_cache["data"]
    lat = cfg.get("weather_lat", 37.5665)
    lon = cfg.get("weather_lon", 126.9780)
    label = cfg.get("weather_label", "Seoul")
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code,is_day&timezone=auto"
        )
        cur = requests.get(url, timeout=8).json()["current"]
        temp = round(cur["temperature_2m"])
        icon, phrase = _WMO.get(int(cur["weather_code"]), ("🌡️", "unsettled"))
        if int(cur["weather_code"]) == 0 and not cur.get("is_day", 1):
            icon = "🌙"  # clear night
        data = {"ok": True, "temp": temp, "icon": icon, "label": label,
                "line": _weather_line(temp, phrase, label)}
    except Exception:
        data = {"ok": False}
    _weather_cache.update(ts=now, data=data)
    return data


def journal_path(date_str):
    return JOURNAL_DIR / f"{date_str}.json"


def load_weekly():
    """Return all weekly focus/goal entries (oldest first; current is last)."""
    if not WEEKLY_PATH.exists():
        return []
    try:
        data = json.loads(WEEKLY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(data, dict) and isinstance(data.get("entries"), list):
        return data["entries"]
    return []


def load_notes(date_str):
    """Return a day's notes as a list (newest saves appended last).

    Handles both the current format {"date", "notes": [...]} and the older
    flat format {"date", "wins", "improve", "tags"} (treated as one note).
    """
    jp = journal_path(date_str)
    if not jp.exists():
        return []
    try:
        data = json.loads(jp.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(data, dict) and isinstance(data.get("notes"), list):
        return data["notes"]
    if isinstance(data, dict) and any(k in data for k in ("wins", "improve", "tags", "diary")):
        return [{
            "wins": data.get("wins", []),
            "improve": data.get("improve", ""),
            "tags": data.get("tags", []),
            "diary": data.get("diary", ""),
            "saved_at": data.get("saved_at", ""),
        }]
    return []


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

    note = note_for_day(events, today) if not calendar_error else pick_for_day(NOTES_BALANCED, today, salt=1)

    # The form always starts blank — each save is a fresh note. We just count
    # how many notes today already has, to gently acknowledge them.
    today_count = len(load_notes(date_str))

    # Current weekly focus/goal (the most recent one written).
    weekly_entries = load_weekly()
    weekly = weekly_entries[-1] if weekly_entries else None
    weekly_set_pretty = ""
    if weekly and weekly.get("set_at"):
        try:
            weekly_set_pretty = dt.datetime.fromisoformat(weekly["set_at"]).strftime("%b %-d")
        except (ValueError, TypeError):
            weekly_set_pretty = ""

    return render_template(
        "index.html",
        greeting=pick_for_day(GREETINGS, today),
        note=note,
        events=events,
        calendar_error=calendar_error,
        date_pretty=now.strftime("%A, %B %-d"),
        date_str=date_str,
        display_name=(cfg.get("display_name") or "").strip(),
        activities=ACTIVITIES,
        today_count=today_count,
        companion=pick_for_day(COMPANIONS, today),
        weekly=weekly,
        weekly_set_pretty=weekly_set_pretty,
        weather=fetch_weather(cfg),
        email_configured=email_handler.is_configured(cfg.get("email_accounts", [])),
    )


@app.route("/save", methods=["POST"])
def save():
    data = request.get_json(force=True) or {}
    date_str = _valid_date(data.get("date")) or dt.date.today().isoformat()
    wins = [str(w).strip() for w in data.get("wins", [])]
    improve = str(data.get("improve", "")).strip()
    # Keep only known activity tags, in their canonical order.
    chosen = set(data.get("tags", []) or [])
    tags = [a["id"] for a in ACTIVITIES if a["id"] in chosen]
    diary = str(data.get("diary", "")).strip()

    # Don't store a completely empty note.
    if not any(wins) and not improve and not tags and not diary:
        return jsonify({"ok": False, "empty": True}), 400

    note = {
        "wins": wins,
        "improve": improve,
        "tags": tags,
        "diary": diary,
        "saved_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    # Append to the day's notes — never overwrite earlier saves.
    notes = load_notes(date_str)
    notes.append(note)
    journal_path(date_str).write_text(
        json.dumps({"date": date_str, "notes": notes}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return jsonify({"ok": True, "count": len(notes)})


@app.route("/weekly/save", methods=["POST"])
def weekly_save():
    data = request.get_json(force=True) or {}
    focus = str(data.get("focus", "")).strip()
    goal = str(data.get("goal", "")).strip()
    if not focus and not goal:
        return jsonify({"ok": False, "empty": True}), 400

    entries = load_weekly()
    entry = {
        "focus": focus,
        "goal": goal,
        "set_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    entries.append(entry)
    WEEKLY_PATH.write_text(
        json.dumps({"entries": entries}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return jsonify({"ok": True, **entry})


@app.route("/api/weekly-history")
def weekly_history():
    return jsonify(list(reversed(load_weekly())))  # newest first


def _valid_date(date_str):
    """Return the date_str if it's a real YYYY-MM-DD, else None (guards paths)."""
    try:
        dt.date.fromisoformat(date_str)
        return date_str
    except (ValueError, TypeError):
        return None


@app.route("/calendar")
def calendar_view():
    cfg = load_config()
    tz = get_tz(cfg)
    now = dt.datetime.now(tz)
    return render_template(
        "calendar.html",
        today_str=now.date().isoformat(),
        display_name=(cfg.get("display_name") or "").strip(),
        activities=ACTIVITIES,
        companion=pick_for_day(COMPANIONS, now.date()),
    )


@app.route("/api/entry/<date_str>")
def api_entry(date_str):
    date_str = _valid_date(date_str)
    if not date_str:
        return jsonify({"error": "bad-date"}), 400
    notes = load_notes(date_str)
    return jsonify({"date": date_str, "exists": bool(notes), "notes": notes})


@app.route("/api/entry-dates")
def api_entry_dates():
    """All dates that have a saved reflection (for marking the calendar)."""
    dates = []
    for f in JOURNAL_DIR.glob("*.json"):
        if _valid_date(f.stem):
            dates.append(f.stem)
    return jsonify(sorted(dates))


_email_cache = {"ts": 0.0, "data": None}


@app.route("/api/emails")
def api_emails():
    cfg = load_config()
    accounts = cfg.get("email_accounts", [])
    if not email_handler.is_configured(accounts):
        return jsonify({"configured": False})

    now = time.time()
    if _email_cache["data"] is not None and now - _email_cache["ts"] < 300:
        return jsonify(_email_cache["data"])

    pending, not_connected = [], []
    for acct in accounts:
        items = email_handler.fetch_pending(acct)
        if items is None:
            not_connected.append(acct)
        else:
            pending.extend(items)
    pending.sort(key=lambda p: (not p["unread"],))  # unread first

    api_key = (cfg.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    model = cfg.get("summary_model", "claude-opus-4-8")
    summary = email_handler.summarize(pending, api_key, model) if pending else ""

    data = {"configured": True, "pending": pending, "summary": summary,
            "count": len(pending), "not_connected": not_connected}
    _email_cache.update(ts=now, data=data)
    return jsonify(data)


if __name__ == "__main__":
    print("\n  🌿 Morning Check-in is ready at  http://127.0.0.1:5001\n")
    app.run(host="127.0.0.1", port=5001, debug=False)

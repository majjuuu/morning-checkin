# 🌿 Morning Check-in

A peaceful, pastel local page to greet your day with your calendar + a warm
note, and to reflect each evening on **3 things you did well** and **1 thing you
can do better tomorrow**. Reflections are saved per day in `journal/`.

Built with Python + Flask. Your Google Calendar is read privately via its
"secret iCal address," so there's no OAuth or Google Cloud setup.

## Quick start (fresh clone)

```bash
git clone <your-repo-url> morning-checkin
cd morning-checkin

python3 -m venv venv
./venv/bin/pip install -r requirements.txt

cp config.example.json config.json   # then edit config.json (see below)
./venv/bin/python app.py             # open http://127.0.0.1:5001
```

Then follow **"Connect your calendar"** below to fill in `config.json`.

> ⚠️ `config.json` (your private calendar URL) and `journal/` (your reflections)
> are git-ignored on purpose — keep them out of version control.

> **Where the files actually live (the author's macOS setup):** the real project is at `~/.morning-checkin`
> (a hidden folder in your home directory, **local-only**). Your workspace path
> `~/Documents/!Claude/morning-checkin` is a **symlink** pointing to it, so you
> can open/edit it from your workspace as usual.
>
> Why this split: `~/Documents` is synced to iCloud, and a background service
> **cannot reliably read files from iCloud** — reads deadlock when iCloud has
> evicted a file. Keeping the real files local (with just a link in Documents)
> makes the auto-start rock-solid. Don't move the real files into Documents.

## Open it each morning

The server runs automatically in the background (see "Auto-start" below), so
each morning you just open **http://127.0.0.1:5001** and refresh. The page
fetches your calendar fresh on every load — no restart needed for a new day.
Bookmark it or pin the tab for one-click access.

## Connect your calendar

1. Copy the template: `cp config.example.json config.json`
2. Open **Google Calendar** in a browser → **Settings** → pick your calendar.
3. Scroll to **Integrate calendar** → copy the **Secret address in iCal format**
   (it ends in `.ics`).
4. Paste it into `config.json` as the `ical_url` value. Optionally set your
   `display_name` (for "Good morning, ___") and your `timezone`
   (e.g. `America/New_York`, `Asia/Seoul`).

> The secret iCal URL is read-only and private — keep it to yourself.

## Auto-start (already set up)

A macOS **LaunchAgent** at
`~/Library/LaunchAgents/com.majuyeon.morningcheckin.plist` starts the server
at every login and restarts it if it ever stops. You don't have to run anything.

Useful commands:

```bash
# stop it for now
launchctl unload ~/Library/LaunchAgents/com.majuyeon.morningcheckin.plist

# start it again
launchctl load -w ~/Library/LaunchAgents/com.majuyeon.morningcheckin.plist

# is it running? (shows a PID and last exit status 0 when healthy)
launchctl list | grep morningcheckin
```

### Remove auto-start completely
```bash
launchctl unload ~/Library/LaunchAgents/com.majuyeon.morningcheckin.plist
rm ~/Library/LaunchAgents/com.majuyeon.morningcheckin.plist
```

## Run it manually (if you ever disable auto-start)

Double-click **`start.command`**, or in Terminal:

```bash
cd ~/.morning-checkin
./venv/bin/python app.py
```

## Where your reflections live

Each day is saved as `journal/YYYY-MM-DD.json`. Reopening the page later the
same day shows what you already wrote, so you can keep adding to it.

## Notes
- Recurring events are expanded correctly for the current day.
- If the calendar can't be reached, the page still works for reflecting.
- Logs (for troubleshooting) are in `server.out.log` and `server.err.log`.

# 📬 Connecting your email ("Emails to handle")

This section reads your **important, unanswered** emails via the Gmail API
(read-only) and writes a short Claude summary at the bottom. It's optional —
the rest of the app works without it.

There are three one-time steps: **(A)** create a Google OAuth client, **(B)**
authorize each account, **(C)** add a Claude API key for the summary.

> Everything stays on your machine. `credentials.json`, `token_*.json`, and your
> API key in `config.json` are all git-ignored.

---

## A. Create a Google OAuth client (~5 min, once)

1. Go to **https://console.cloud.google.com** and create a project (any name).
2. **APIs & Services → Library →** search **"Gmail API" → Enable**.
3. **APIs & Services → OAuth consent screen:**
   - User type: **External** → Create.
   - Fill the app name + your email; **Save and continue** through the screens.
   - **Audience / Test users → Add users:** add **both** addresses
     (`juyeonma@umich.edu` and `majuyeon695@gmail.com`). In "Testing" mode this
     is what lets you authorize without app verification.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID:**
   - Application type: **Desktop app** → Create.
   - **Download JSON**, rename it to **`credentials.json`**, and put it in this
     folder (`~/.morning-checkin/`).

> ⚠️ **U-M (umich) caveat:** University Google Workspace accounts sometimes block
> third-party apps. If step B fails for `juyeonma@umich.edu` with an
> "admin policy" / "access blocked" error, that account can't be connected this
> way — your personal Gmail will still work. Just remove the umich address from
> `"email_accounts"` in `config.json`.

## B. Authorize each account (browser, once each)

In Terminal, from this folder:

```bash
cd ~/.morning-checkin
./venv/bin/python auth_email.py majuyeon695@gmail.com
./venv/bin/python auth_email.py juyeonma@umich.edu
```

Each opens a browser — sign in with **that** account and approve read-only
Gmail access. (You'll see an "unverified app" warning because it's your own
personal client — click **Advanced → Continue**.) This saves a
`token_<account>.json` file.

## C. Add a Claude API key for the summary

1. Get a key at **https://console.anthropic.com** → API Keys.
2. Put it in `config.json`:
   ```json
   "anthropic_api_key": "sk-ant-...",
   ```
   (Or set an `ANTHROPIC_API_KEY` environment variable instead.)

The summary uses `claude-opus-4-8` by default. To use a cheaper/faster model,
set `"summary_model": "claude-haiku-4-5"` in `config.json`.

---

## Done

Open **http://127.0.0.1:5001** — the "Emails to handle" card fills with
important threads still awaiting your reply, each with a **Reply** button that
opens the thread in Gmail, and a one-line summary at the bottom.

If you change `config.json` or add a token, restart the background server:
`launchctl kickstart -k gui/$(id -u)/com.majuyeon.morningcheckin`

### What counts as "to handle"
Threads in your inbox marked **Important** by Gmail, from the last 21 days,
where the **most recent message isn't from you** (i.e. the ball's in your court).

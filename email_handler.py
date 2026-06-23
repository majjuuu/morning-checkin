"""Gmail (read-only) integration for Morning Check-in.

Reads important, unreplied emails from one or more Google accounts via the
Gmail API, and optionally summarizes them with Claude.

Heavy imports (google, anthropic) are deferred so the app boots even before
email is set up. This module only READS already-saved OAuth tokens — the
interactive authorization flow lives in auth_email.py (run once per account).
"""
import datetime as dt
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_PATH = BASE_DIR / "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def token_path(account):
    safe = account.replace("@", "_at_").replace(".", "_")
    return BASE_DIR / f"token_{safe}.json"


def is_configured(accounts):
    """True if credentials.json exists and at least one account is authorized."""
    if not CREDENTIALS_PATH.exists():
        return False
    return any(token_path(a).exists() for a in accounts)


def _service(account):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    tp = token_path(account)
    if not tp.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(tp), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            tp.write_text(creds.to_json())
        else:
            return None
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _parse_sender(raw):
    raw = (raw or "").strip()
    if "<" in raw:
        name = raw.split("<")[0].strip().strip('"')
        return name or raw.split("<")[1].rstrip(">")
    return raw


def fetch_pending(account, max_threads=8):
    """Important inbox threads still awaiting your reply.

    'Awaiting reply' = the most recent message in the thread is not from you.
    Returns a list of dicts, or None if the account isn't connected.
    """
    service = _service(account)
    if service is None:
        return None
    out = []
    try:
        q = "is:important in:inbox newer_than:21d"
        resp = service.users().threads().list(
            userId="me", q=q, maxResults=max_threads
        ).execute()
        for t in resp.get("threads", []):
            thread = service.users().threads().get(
                userId="me", id=t["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            msgs = thread.get("messages", [])
            if not msgs:
                continue
            last = msgs[-1]
            headers = {h["name"].lower(): h["value"]
                       for h in last.get("payload", {}).get("headers", [])}
            frm = headers.get("from", "")
            if account.lower() in frm.lower():
                continue  # last message is from me — already replied
            out.append({
                "account": account,
                "thread_id": t["id"],
                "subject": headers.get("subject", "(no subject)"),
                "from": _parse_sender(frm),
                "snippet": last.get("snippet", ""),
                "unread": "UNREAD" in last.get("labelIds", []),
                "url": f"https://mail.google.com/mail/?authuser={account}#all/{t['id']}",
            })
    except Exception:
        return out
    return out


def summarize(pending, api_key, model="claude-opus-4-8"):
    """A short, warm summary of the pending emails, written by Claude."""
    if not api_key or not pending:
        return ""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        lines = [f"- From {p['from']}: {p['subject']} — {p['snippet'][:160]}"
                 for p in pending]
        msg = client.messages.create(
            model=model,
            max_tokens=220,
            system=("You write a brief, warm morning summary of a person's unanswered "
                    "important emails for a calm dashboard. 1–2 sentences, gentle and "
                    "specific; mention what seems most time-sensitive. No greeting, no lists."),
            messages=[{"role": "user",
                       "content": "My unanswered important emails:\n" + "\n".join(lines)}],
        )
        return "".join(b.text for b in msg.content if b.type == "text").strip()
    except Exception:
        return ""

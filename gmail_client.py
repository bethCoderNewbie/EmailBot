"""Gmail API client — authenticates, fetches, and marks emails."""
import base64
import time
from datetime import datetime, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import config
from retry import with_backoff

# Gmail API quota: 250 units/user/second; messages.get = 5 units → safe at ~1 req/s
_GMAIL_INTER_REQUEST_DELAY = 0.2   # seconds between individual message fetches

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",   # needed to mark read
]


def _authenticate() -> Credentials:
    token_path = Path(config.GMAIL_TOKEN_PATH)
    creds = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.GMAIL_CREDENTIALS_PATH, SCOPES
            )
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())

    return creds


def _build_query(since_epoch: int | None) -> str:
    """Build a Gmail search query from config filters + optional timestamp."""
    parts = []

    # Sender filter
    if config.GMAIL_SENDER_FILTER:
        sender_q = " OR ".join(f"from:{s}" for s in config.GMAIL_SENDER_FILTER)
        parts.append(f"({sender_q})")

    # Only unread messages
    parts.append("is:unread")

    # Since last run (epoch seconds → Gmail uses seconds)
    if since_epoch:
        parts.append(f"after:{since_epoch}")

    return " ".join(parts) if parts else "is:unread"


def _decode_body(payload: dict) -> str:
    """Recursively extract plain text from a message payload."""
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    if mime.startswith("multipart/"):
        for part in payload.get("parts", []):
            text = _decode_body(part)
            if text:
                return text
    return ""


def fetch_emails(since_epoch: int | None = None) -> list[dict]:
    """
    Fetch unread emails matching config filters.

    Returns a list of dicts:
        {id, thread_id, subject, sender, date, snippet, body}
    """
    creds   = _authenticate()
    service = build("gmail", "v1", credentials=creds)
    users   = service.users()

    query = _build_query(since_epoch)
    label_ids = config.GMAIL_LABELS if config.GMAIL_LABELS else ["INBOX"]

    messages_resource = users.messages()
    request  = messages_resource.list(userId="me", q=query, labelIds=label_ids, maxResults=200)
    ids: list[str] = []

    while request:
        resp = request.execute()
        ids += [m["id"] for m in resp.get("messages", [])]
        request = messages_resource.list_next(request, resp)

    @with_backoff(exceptions=(HttpError,), retries=4, base_delay=2.0)
    def _fetch_one(msg_id: str) -> dict:
        raw     = messages_resource.get(userId="me", id=msg_id, format="full").execute()
        headers = {h["name"]: h["value"] for h in raw["payload"].get("headers", [])}
        body    = _decode_body(raw["payload"])
        return {
            "id":        msg_id,
            "thread_id": raw.get("threadId"),
            "subject":   headers.get("Subject", "(no subject)"),
            "sender":    headers.get("From", "unknown"),
            "date":      headers.get("Date", ""),
            "snippet":   raw.get("snippet", ""),
            "body":      body[:4000],
        }

    emails = []
    for msg_id in ids:
        emails.append(_fetch_one(msg_id))
        time.sleep(_GMAIL_INTER_REQUEST_DELAY)   # respect quota burst limit

    return emails


@with_backoff(exceptions=(HttpError,), retries=4, base_delay=2.0)
def mark_as_read(message_ids: list[str]) -> None:
    """Remove the UNREAD label from the given message IDs."""
    if not message_ids:
        return
    creds   = _authenticate()
    service = build("gmail", "v1", credentials=creds)
    service.users().messages().batchModify(
        userId="me",
        body={"ids": message_ids, "removeLabelIds": ["UNREAD"]},
    ).execute()

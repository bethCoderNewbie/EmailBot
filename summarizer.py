"""AI summarization via OpenRouter (OpenAI-compatible API)."""
from openai import OpenAI

import config

_client = OpenAI(
    api_key=config.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    default_headers={"HTTP-Referer": "emailbot", "X-Title": "EmailBot"},
)

_SYSTEM = """You are an expert email analyst. Your job is to produce a concise,
structured summary of a batch of emails. For each email write:
- **Subject** (bold)
- Sender and date (one line)
- 2–4 sentence summary of the key information or action required
Group them by category if possible (News, Work, Newsletters, Personal, etc.).
Be factual. Do not invent information. Use plain English."""


def summarize_emails(emails: list[dict]) -> str:
    """
    Given a list of email dicts (subject, sender, date, body),
    return a Markdown string summary suitable for a newsletter.
    """
    if not emails:
        return "_No new emails this period._"

    # Build a compact representation to keep token usage low
    lines = []
    for i, e in enumerate(emails, 1):
        lines.append(
            f"--- Email {i} ---\n"
            f"Subject: {e['subject']}\n"
            f"From: {e['sender']}\n"
            f"Date: {e['date']}\n"
            f"Body:\n{e['body'][:2000]}\n"
        )
    user_content = "\n".join(lines)

    response = _client.chat.completions.create(
        model=config.OPENROUTER_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": user_content},
        ],
        temperature=0.3,
        max_tokens=2000,
    )
    return response.choices[0].message.content or "_Summary unavailable._"

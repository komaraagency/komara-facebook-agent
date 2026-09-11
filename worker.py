"""Komara Agent: local, deterministic Facebook message/comment responder.

No external AI service is used. Responses are selected from local rules,
FAQ content, and kb.json.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DB_PATH = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "memory.db")))
KB_PATH = BASE_DIR / "kb.json"
FAQ_PATH = BASE_DIR / "docs" / "faq.md"
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v23.0")
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "1966578313568105")
PAGE_ACCESS_TOKEN = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN = os.getenv("FACEBOOK_VERIFY_TOKEN", "")
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"

app = FastAPI(title="Komara Agent", version="1.0.0")


def connect_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with connect_db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_key TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                source_text TEXT,
                response_text TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS conversations (
                contact_id TEXT PRIMARY KEY,
                last_message TEXT,
                last_response TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_faq() -> list[tuple[str, str]]:
    if not FAQ_PATH.exists():
        return []
    pairs: list[tuple[str, str]] = []
    question = ""
    answer_lines: list[str] = []
    for raw_line in FAQ_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            if question and answer_lines:
                pairs.append((question, " ".join(answer_lines).strip()))
            question = line[3:].strip()
            answer_lines = []
        elif question and line and not line.startswith("#"):
            answer_lines.append(line.lstrip("- "))
    if question and answer_lines:
        pairs.append((question, " ".join(answer_lines).strip()))
    return pairs


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def choose_response(text: str, sender_name: str = "") -> str:
    """Select a contextual answer using only local deterministic rules."""
    kb = load_json(KB_PATH)
    normalized = normalize(text)
    faq_pairs = load_faq()

    for item in kb.get("rules", []):
        keywords = [normalize(str(keyword)) for keyword in item.get("keywords", [])]
        if any(keyword and keyword in normalized for keyword in keywords):
            return str(item.get("response", kb.get("fallback", "Merci pour votre message.")))

    for question, answer in faq_pairs:
        question_terms = [term for term in re.findall(r"[a-zà-ÿ0-9]+", normalize(question)) if len(term) > 3]
        if question_terms and sum(term in normalized for term in question_terms) >= max(1, len(question_terms) // 2):
            return answer

    if re.search(r"\b(bonjour|salut|bonsoir|hello|coucou)\b", normalized):
        greeting = kb.get("greeting", "Bonjour ! Merci pour votre message.")
        return f"{greeting}"

    fallback = kb.get("fallback", "Merci pour votre message. Notre équipe revient vers vous rapidement.")
    if sender_name:
        fallback = fallback.replace("{name}", sender_name)
    return str(fallback)


def event_key(event_type: str, source_id: str, text: str) -> str:
    raw = f"{event_type}:{source_id}:{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def already_processed(key: str) -> bool:
    with connect_db() as connection:
        row = connection.execute("SELECT 1 FROM events WHERE event_key = ?", (key,)).fetchone()
        return row is not None


def remember_event(key: str, event_type: str, source_id: str, text: str, response: str, status: str) -> None:
    with connect_db() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO events(event_key, event_type, source_id, source_text, response_text, status) VALUES (?, ?, ?, ?, ?, ?)",
            (key, event_type, source_id, text, response, status),
        )
        connection.execute(
            "INSERT INTO conversations(contact_id, last_message, last_response) VALUES (?, ?, ?) "
            "ON CONFLICT(contact_id) DO UPDATE SET last_message=excluded.last_message, last_response=excluded.last_response, updated_at=CURRENT_TIMESTAMP",
            (source_id, text, response),
        )


def graph_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    if DRY_RUN:
        return {"dry_run": True, "path": path, "payload": payload}
    if not PAGE_ACCESS_TOKEN:
        raise RuntimeError("FACEBOOK_PAGE_ACCESS_TOKEN is missing")
    response = requests.post(
        f"{GRAPH_API_BASE}/{path.lstrip('/')}",
        data={**payload, "access_token": PAGE_ACCESS_TOKEN},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def reply_to_comment(comment_id: str, response_text: str) -> dict[str, Any]:
    return graph_post(f"{comment_id}/comments", {"message": response_text})


def reply_to_message(recipient_id: str, response_text: str) -> dict[str, Any]:
    return graph_post("me/messages", {"recipient": json.dumps({"id": recipient_id}), "message": json.dumps({"text": response_text})})


def process_comment(comment_id: str, text: str, sender_id: str, sender_name: str = "") -> dict[str, Any]:
    if not text or sender_id == PAGE_ID:
        return {"status": "ignored"}
    key = event_key("comment", comment_id, text)
    if already_processed(key):
        return {"status": "duplicate", "event_key": key}
    response_text = choose_response(text, sender_name)
    try:
        result = reply_to_comment(comment_id, response_text)
        status = "dry_run" if DRY_RUN else "sent"
    except Exception as exc:  # Keep webhook acknowledgement resilient.
        result = {"error": str(exc)}
        status = "error"
    remember_event(key, "comment", comment_id, text, response_text, status)
    return {"status": status, "response": response_text, "result": result}


def process_message(message_id: str, text: str, sender_id: str, sender_name: str = "") -> dict[str, Any]:
    if not text or sender_id == PAGE_ID:
        return {"status": "ignored"}
    key = event_key("message", message_id, text)
    if already_processed(key):
        return {"status": "duplicate", "event_key": key}
    response_text = choose_response(text, sender_name)
    try:
        result = reply_to_message(sender_id, response_text)
        status = "dry_run" if DRY_RUN else "sent"
    except Exception as exc:
        result = {"error": str(exc)}
        status = "error"
    remember_event(key, "message", message_id, text, response_text, status)
    return {"status": status, "response": response_text, "result": result}


def process_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if change.get("field") == "feed" or "comment_id" in value:
                comment_id = str(value.get("comment_id") or value.get("id") or "")
                text = str(value.get("message") or value.get("text") or "")
                sender = value.get("from") or {}
                sender_id = str(sender.get("id") or "")
                sender_name = str(sender.get("name") or "")
                if comment_id:
                    results.append(process_comment(comment_id, text, sender_id, sender_name))
        for messaging in entry.get("messaging", []):
            message = messaging.get("message") or {}
            text = str(message.get("text") or "")
            sender = messaging.get("sender") or {}
            sender_id = str(sender.get("id") or "")
            message_id = str(message.get("mid") or messaging.get("timestamp") or "")
            if message_id:
                results.append(process_message(message_id, text, sender_id))
    return results


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "mode": "dry_run" if DRY_RUN else "live", "external_ai": False}


@app.get("/webhook", response_class=PlainTextResponse)
def verify_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> str:
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN and hub_challenge:
        return hub_challenge
    raise HTTPException(status_code=403, detail="Webhook verification failed")


@app.post("/webhook")
async def receive_webhook(request: Request) -> dict[str, Any]:
    payload = await request.json()
    return {"received": True, "results": process_payload(payload)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("worker:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))

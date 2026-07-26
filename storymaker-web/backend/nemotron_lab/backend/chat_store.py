# -*- coding: utf-8 -*-
import sqlite3
import os
import uuid
import json
from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
DB_PATH = os.getenv("STORYMAKER_DB_PATH", "/data/storymaker.db")

def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_tables():
    with _get_db() as conn:
        cur = conn.cursor()
        cur.execute('''
        CREATE TABLE IF NOT EXISTS v1_nemotron_conversations (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            persona_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        ''')
        cur.execute('''
        CREATE TABLE IF NOT EXISTS v1_nemotron_messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            token_usage INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(conversation_id) REFERENCES v1_nemotron_conversations(id) ON DELETE CASCADE
        );
        ''')
        cur.execute('''
        CREATE TABLE IF NOT EXISTS v1_user_nemotron_personas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            company_name TEXT DEFAULT '',
            industry_key TEXT DEFAULT '',
            region TEXT DEFAULT '',
            website_url TEXT DEFAULT '',
            persona_json TEXT DEFAULT '{}',
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        ''')
        conn.commit()

init_tables()

def list_conversations(user_id: int):
    with _get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, title, created_at, updated_at FROM v1_nemotron_conversations WHERE user_id = ? ORDER BY updated_at DESC LIMIT 50",
            (user_id,)
        )
        return [dict(row) for row in cur.fetchall()]

def create_conversation(user_id: int, title: str = "새 대화"):
    conv_id = f"conv_{uuid.uuid4().hex[:12]}"
    now = datetime.now(KST).isoformat(timespec="seconds")
    with _get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO v1_nemotron_conversations (id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (conv_id, user_id, title, now, now)
        )
        conn.commit()
    return {"id": conv_id, "user_id": user_id, "title": title, "created_at": now, "updated_at": now}

def get_conversation_messages(conv_id: str, user_id: int):
    with _get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id, title FROM v1_nemotron_conversations WHERE id = ?", (conv_id,))
        conv = cur.fetchone()
        if not conv or dict(conv)["user_id"] != user_id:
            return None
        cur.execute(
            "SELECT id, role, content, token_usage, created_at FROM v1_nemotron_messages WHERE conversation_id = ? ORDER BY rowid ASC",
            (conv_id,)
        )
        messages = [dict(row) for row in cur.fetchall()]
        return {"id": conv_id, "title": dict(conv)["title"], "messages": messages}

def delete_conversation(conv_id: str, user_id: int):
    with _get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM v1_nemotron_messages WHERE conversation_id = ?", (conv_id,))
        cur.execute("DELETE FROM v1_nemotron_conversations WHERE id = ? AND user_id = ?", (conv_id, user_id))
        conn.commit()
        return True

def add_message(conv_id: str, role: str, content: str, token_usage: int = 0):
    msg_id = f"msg_{uuid.uuid4().hex[:10]}"
    now = datetime.now(KST).isoformat(timespec="seconds")
    with _get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO v1_nemotron_messages (id, conversation_id, role, content, token_usage, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (msg_id, conv_id, role, content, token_usage, now)
        )
        cur.execute(
            "UPDATE v1_nemotron_conversations SET updated_at = ? WHERE id = ?",
            (now, conv_id)
        )
        conn.commit()
    return {"id": msg_id, "conversation_id": conv_id, "role": role, "content": content, "token_usage": token_usage, "created_at": now}

def update_conversation_title(conv_id: str, title: str):
    with _get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE v1_nemotron_conversations SET title = ? WHERE id = ?", (title[:50], conv_id))
        conn.commit()

def save_user_persona(user_id: int, company_name: str, industry_key: str, region: str, website_url: str, persona_json: dict):
    now = datetime.now(KST).isoformat(timespec="seconds")
    with _get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE v1_user_nemotron_personas SET is_active = 0 WHERE user_id = ?", (user_id,))
        cur.execute(
            "INSERT INTO v1_user_nemotron_personas (user_id, company_name, industry_key, region, website_url, persona_json, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)",
            (user_id, company_name, industry_key, region, website_url, json.dumps(persona_json, ensure_ascii=False), now, now)
        )
        conn.commit()
    return get_active_user_persona(user_id)

def get_active_user_persona(user_id: int):
    with _get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, company_name, industry_key, region, website_url, persona_json, is_active, updated_at FROM v1_user_nemotron_personas WHERE user_id = ? AND is_active = 1 ORDER BY id DESC LIMIT 1",
            (user_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["persona"] = json.loads(d.get("persona_json") or "{}")
        except Exception:
            d["persona"] = {}
        return d

def deactivate_user_persona(user_id: int):
    with _get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE v1_user_nemotron_personas SET is_active = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        return True


"""Small single-process MVP store. Credentials are never persisted verbatim."""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def owner_key(token: str | None, device_id: str) -> str:
    return hashlib.sha256(((token or "loopback") + "\0" + device_id).encode()).hexdigest()


class Store:
    def __init__(self, root: Path):
        self.path = root / "velapet.sqlite3"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, persona TEXT NOT NULL, messages TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, idem TEXT NOT NULL,
                    digest TEXT NOT NULL, body TEXT NOT NULL, UNIQUE(owner, idem));
                CREATE TABLE IF NOT EXISTS appearances (owner TEXT PRIMARY KEY, pet_id TEXT NOT NULL);
            """)
            # A process restart cannot safely recreate a possibly billable request.
            for row in db.execute("SELECT id, body FROM jobs").fetchall():
                body = json.loads(row[1])
                if body["status"] in {"queued", "processing"}:
                    body.update(status="failed", error_code="PROCESS_INTERRUPTED")
                    db.execute("UPDATE jobs SET body=? WHERE id=?", (json.dumps(body), row[0]))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def history(self, cid: str, owner: str, persona: str):
        with self.connect() as db:
            row = db.execute("SELECT owner, persona, messages FROM conversations WHERE id=?", (cid,)).fetchone()
        if row is None:
            return []
        if row[0] != owner or row[1] != persona:
            raise PermissionError("Conversation unavailable")
        return json.loads(row[2])

    def save_history(self, cid: str, owner: str, persona: str, history: list):
        with self.connect() as db:
            db.execute("INSERT INTO conversations VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET messages=excluded.messages",
                       (cid, owner, persona, json.dumps(history[-12:], ensure_ascii=False)))

    def clear_history(self, cid: str, owner: str):
        with self.connect() as db:
            db.execute("DELETE FROM conversations WHERE id=? AND owner=?", (cid, owner))

    def job(self, jid: str, owner: str):
        with self.connect() as db:
            row = db.execute("SELECT body FROM jobs WHERE id=? AND owner=?", (jid, owner)).fetchone()
        return json.loads(row[0]) if row else None

    def create_job(self, body: dict, owner: str, idem: str, digest: str):
        with self.connect() as db:
            row = db.execute("SELECT digest, body FROM jobs WHERE owner=? AND idem=?", (owner, idem)).fetchone()
            if row:
                if row[0] != digest:
                    raise ValueError("IDEMPOTENCY_CONFLICT")
                return json.loads(row[1]), False
            db.execute("INSERT INTO jobs VALUES(?,?,?,?,?)", (body["job_id"], owner, idem, digest, json.dumps(body)))
        return body, True

    def update_job(self, body: dict):
        with self.connect() as db:
            db.execute("UPDATE jobs SET body=? WHERE id=?", (json.dumps(body), body["job_id"]))

    def appearance(self, owner: str):
        with self.connect() as db:
            row = db.execute("SELECT pet_id FROM appearances WHERE owner=?", (owner,)).fetchone()
        return row[0] if row else "nova-cat"

    def save_appearance(self, owner: str, pet_id: str):
        with self.connect() as db:
            db.execute("INSERT INTO appearances VALUES(?,?) ON CONFLICT(owner) DO UPDATE SET pet_id=excluded.pet_id",
                       (owner, pet_id))

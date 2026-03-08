import os
import sqlite3
import threading
from datetime import datetime, timezone


class DedupCache:
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = os.environ.get("SQLITE_PATH", "/data/ss_navigator.db")
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._run_migrations()

    def _run_migrations(self):
        with self._lock:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
            """)
            cursor = self.conn.execute(
                "SELECT MAX(version) FROM schema_version"
            )
            row = cursor.fetchone()
            current_version = row[0] if row[0] is not None else 0

            if current_version < 1:
                self._migrate_v1()

            self.conn.commit()

    def _migrate_v1(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_articles (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                status TEXT DEFAULT 'new',
                source_feed TEXT,
                relevance_score INTEGER
            )
        """)
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_seen_articles_first_seen ON seen_articles(first_seen_at)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_seen_articles_source ON seen_articles(source)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_seen_articles_status ON seen_articles(status)"
        )
        self.conn.execute(
            "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?)",
            (1, datetime.now(timezone.utc).isoformat()),
        )

    def insert(self, article_id: str, url: str, title: str, source: str, source_feed: str) -> bool:
        with self._lock:
            cursor = self.conn.execute(
                "SELECT 1 FROM seen_articles WHERE id = ?", (article_id,)
            )
            if cursor.fetchone() is not None:
                return False
            self.conn.execute(
                """INSERT INTO seen_articles (id, url, title, source, first_seen_at, source_feed)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (article_id, url, title, source, datetime.now(timezone.utc).isoformat(), source_feed),
            )
            self.conn.commit()
            return True

    def exists(self, article_id: str) -> bool:
        cursor = self.conn.execute(
            "SELECT 1 FROM seen_articles WHERE id = ?", (article_id,)
        )
        return cursor.fetchone() is not None

    def list_by_feed(self, source_feed: str) -> list[dict]:
        cursor = self.conn.execute(
            "SELECT id, url, title, source, first_seen_at, source_feed FROM seen_articles WHERE source_feed = ?",
            (source_feed,),
        )
        return [dict(row) for row in cursor.fetchall()]

import os
import sqlite3
import threading
from datetime import datetime, timezone


class OAuthDB:
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

            if current_version < 2:
                self._migrate_v2()

            self.conn.commit()

    def _migrate_v2(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS oauth_clients (
                client_id TEXT PRIMARY KEY,
                client_info_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS oauth_pending_requests (
                request_id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                params_json TEXT NOT NULL,
                expires_at REAL NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS oauth_auth_codes (
                code TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                scopes TEXT NOT NULL,
                expires_at REAL NOT NULL,
                code_challenge TEXT NOT NULL,
                redirect_uri TEXT NOT NULL,
                redirect_uri_provided_explicitly INTEGER NOT NULL,
                resource TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_oauth_auth_codes_expires
                ON oauth_auth_codes(expires_at);

            CREATE TABLE IF NOT EXISTS oauth_tokens (
                token TEXT PRIMARY KEY,
                token_type TEXT NOT NULL,
                client_id TEXT NOT NULL,
                scopes TEXT NOT NULL,
                expires_at REAL,
                resource TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_oauth_tokens_client
                ON oauth_tokens(client_id);
            CREATE INDEX IF NOT EXISTS idx_oauth_tokens_type
                ON oauth_tokens(token_type);
            CREATE INDEX IF NOT EXISTS idx_oauth_tokens_expires
                ON oauth_tokens(expires_at);
        """)
        self.conn.execute(
            "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?)",
            (2, datetime.now(timezone.utc).isoformat()),
        )

    # -- Clients --

    def save_client(self, client_id: str, client_info_json: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO oauth_clients (client_id, client_info_json, created_at) VALUES (?, ?, ?)",
                (client_id, client_info_json, datetime.now(timezone.utc).isoformat()),
            )
            self.conn.commit()

    def get_client(self, client_id: str) -> str | None:
        with self._lock:
            cursor = self.conn.execute(
                "SELECT client_info_json FROM oauth_clients WHERE client_id = ?",
                (client_id,),
            )
            row = cursor.fetchone()
            return row["client_info_json"] if row else None

    # -- Pending Requests --

    def save_pending_request(
        self, request_id: str, client_id: str, params_json: str, expires_at: float
    ) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO oauth_pending_requests (request_id, client_id, params_json, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
                (request_id, client_id, params_json, expires_at, datetime.now(timezone.utc).isoformat()),
            )
            self.conn.commit()

    def get_pending_request(self, request_id: str) -> dict | None:
        with self._lock:
            cursor = self.conn.execute(
                "SELECT request_id, client_id, params_json, expires_at FROM oauth_pending_requests WHERE request_id = ?",
                (request_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_pending_request(self, request_id: str) -> None:
        with self._lock:
            self.conn.execute(
                "DELETE FROM oauth_pending_requests WHERE request_id = ?",
                (request_id,),
            )
            self.conn.commit()

    # -- Auth Codes --

    def save_auth_code(
        self,
        code: str,
        client_id: str,
        scopes_json: str,
        expires_at: float,
        code_challenge: str,
        redirect_uri: str,
        redirect_uri_provided_explicitly: bool,
        resource: str | None,
    ) -> None:
        with self._lock:
            self.conn.execute(
                """INSERT INTO oauth_auth_codes
                   (code, client_id, scopes, expires_at, code_challenge, redirect_uri,
                    redirect_uri_provided_explicitly, resource, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    code,
                    client_id,
                    scopes_json,
                    expires_at,
                    code_challenge,
                    redirect_uri,
                    int(redirect_uri_provided_explicitly),
                    resource,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            self.conn.commit()

    def get_auth_code(self, code: str) -> dict | None:
        with self._lock:
            cursor = self.conn.execute(
                "SELECT * FROM oauth_auth_codes WHERE code = ?",
                (code,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_auth_code(self, code: str) -> None:
        with self._lock:
            self.conn.execute(
                "DELETE FROM oauth_auth_codes WHERE code = ?",
                (code,),
            )
            self.conn.commit()

    # -- Tokens --

    def save_token(
        self,
        token: str,
        token_type: str,
        client_id: str,
        scopes_json: str,
        expires_at: float | None,
        resource: str | None,
    ) -> None:
        with self._lock:
            self.conn.execute(
                """INSERT INTO oauth_tokens
                   (token, token_type, client_id, scopes, expires_at, resource, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    token,
                    token_type,
                    client_id,
                    scopes_json,
                    expires_at,
                    resource,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            self.conn.commit()

    def get_token(self, token: str) -> dict | None:
        with self._lock:
            cursor = self.conn.execute(
                "SELECT * FROM oauth_tokens WHERE token = ?",
                (token,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_token(self, token: str) -> None:
        with self._lock:
            self.conn.execute(
                "DELETE FROM oauth_tokens WHERE token = ?",
                (token,),
            )
            self.conn.commit()

    def delete_tokens_by_client(self, client_id: str) -> None:
        with self._lock:
            self.conn.execute(
                "DELETE FROM oauth_tokens WHERE client_id = ?",
                (client_id,),
            )
            self.conn.commit()

import hmac
import json
import secrets
import time

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from src.oauth.db import OAuthDB

# Token lifetimes
AUTH_CODE_TTL = 300  # 5 minutes
ACCESS_TOKEN_TTL = 3600  # 1 hour
REFRESH_TOKEN_TTL = 30 * 24 * 3600  # 30 days
PENDING_REQUEST_TTL = 600  # 10 minutes


class SubstackOAuthProvider:
    """OAuth 2.1 provider backed by SQLite. Implements OAuthAuthorizationServerProvider protocol."""

    def __init__(self, db: OAuthDB, password: str, issuer_url: str):
        self.db = db
        self._password = password
        self._issuer_url = issuer_url.rstrip("/")

    # -- Protocol methods --

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        json_str = self.db.get_client(client_id)
        if json_str is None:
            return None
        return OAuthClientInformationFull.model_validate_json(json_str)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self.db.save_client(
            client_info.client_id,
            client_info.model_dump_json(),
        )

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        request_id = secrets.token_hex(32)
        self.db.save_pending_request(
            request_id=request_id,
            client_id=client.client_id,
            params_json=params.model_dump_json(),
            expires_at=time.time() + PENDING_REQUEST_TTL,
        )
        return f"{self._issuer_url}/login?request_id={request_id}"

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        row = self.db.get_auth_code(authorization_code)
        if row is None:
            return None
        if row["client_id"] != client.client_id:
            return None
        return AuthorizationCode(
            code=row["code"],
            client_id=row["client_id"],
            scopes=json.loads(row["scopes"]),
            expires_at=row["expires_at"],
            code_challenge=row["code_challenge"],
            redirect_uri=row["redirect_uri"],
            redirect_uri_provided_explicitly=bool(row["redirect_uri_provided_explicitly"]),
            resource=row["resource"],
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        self.db.delete_auth_code(authorization_code.code)

        access_token = secrets.token_hex(32)
        refresh_token = secrets.token_hex(32)
        scopes_json = json.dumps(authorization_code.scopes)
        now = time.time()

        self.db.save_token(
            token=access_token,
            token_type="access",
            client_id=client.client_id,
            scopes_json=scopes_json,
            expires_at=now + ACCESS_TOKEN_TTL,
            resource=authorization_code.resource,
        )
        self.db.save_token(
            token=refresh_token,
            token_type="refresh",
            client_id=client.client_id,
            scopes_json=scopes_json,
            expires_at=now + REFRESH_TOKEN_TTL,
            resource=authorization_code.resource,
        )

        scope_str = " ".join(authorization_code.scopes) if authorization_code.scopes else None
        return OAuthToken(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_TTL,
            scope=scope_str,
            refresh_token=refresh_token,
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        row = self.db.get_token(refresh_token)
        if row is None or row["token_type"] != "refresh":
            return None
        if row["client_id"] != client.client_id:
            return None
        return RefreshToken(
            token=row["token"],
            client_id=row["client_id"],
            scopes=json.loads(row["scopes"]),
            expires_at=int(row["expires_at"]) if row["expires_at"] else None,
        )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        self.db.delete_token(refresh_token.token)

        new_access = secrets.token_hex(32)
        new_refresh = secrets.token_hex(32)
        scopes_json = json.dumps(scopes)
        now = time.time()

        self.db.save_token(
            token=new_access,
            token_type="access",
            client_id=client.client_id,
            scopes_json=scopes_json,
            expires_at=now + ACCESS_TOKEN_TTL,
            resource=None,
        )
        self.db.save_token(
            token=new_refresh,
            token_type="refresh",
            client_id=client.client_id,
            scopes_json=scopes_json,
            expires_at=now + REFRESH_TOKEN_TTL,
            resource=None,
        )

        scope_str = " ".join(scopes) if scopes else None
        return OAuthToken(
            access_token=new_access,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_TTL,
            scope=scope_str,
            refresh_token=new_refresh,
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        row = self.db.get_token(token)
        if row is None or row["token_type"] != "access":
            return None
        if row["expires_at"] and row["expires_at"] < time.time():
            return None
        return AccessToken(
            token=row["token"],
            client_id=row["client_id"],
            scopes=json.loads(row["scopes"]),
            expires_at=int(row["expires_at"]) if row["expires_at"] else None,
            resource=row["resource"],
        )

    async def revoke_token(
        self, token: AccessToken | RefreshToken
    ) -> None:
        self.db.delete_token(token.token)

    # -- Utility methods (used by /login handler) --

    def verify_password(self, password: str) -> bool:
        return hmac.compare_digest(
            self._password.encode("utf-8"),
            password.encode("utf-8"),
        )

    def create_auth_code_from_pending(self, request_id: str) -> str | None:
        """Load pending request, generate auth code, return redirect URL. Returns None if expired/missing."""
        pending = self.db.get_pending_request(request_id)
        if pending is None:
            return None
        if pending["expires_at"] < time.time():
            self.db.delete_pending_request(request_id)
            return None

        params = AuthorizationParams.model_validate_json(pending["params_json"])
        code = secrets.token_hex(32)

        self.db.save_auth_code(
            code=code,
            client_id=pending["client_id"],
            scopes_json=json.dumps(params.scopes or []),
            expires_at=time.time() + AUTH_CODE_TTL,
            code_challenge=params.code_challenge,
            redirect_uri=str(params.redirect_uri),
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,
        )
        self.db.delete_pending_request(request_id)

        return construct_redirect_uri(
            str(params.redirect_uri),
            code=code,
            state=params.state,
        )

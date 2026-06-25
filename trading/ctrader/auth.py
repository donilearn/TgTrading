import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://openapi.ctrader.com/apps/token"


@dataclass
class CTraderTokens:
    access_token: str
    refresh_token: str
    expires_in: int | None = None


class CTraderAuthService:
    """OAuth 2.0 — access token yangilash (HTTP)."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str = "http://localhost:8080",
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri

    async def refresh(self, refresh_token: str) -> CTraderTokens:
        params = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(_TOKEN_URL, params=params)
            response.raise_for_status()
            data = response.json()

        error = data.get("errorCode") or data.get("error")
        if error:
            raise RuntimeError(f"cTrader token refresh failed: {error}")

        access = data.get("accessToken") or data.get("access_token")
        refresh = data.get("refreshToken") or data.get("refresh_token")
        if not access or not refresh:
            raise RuntimeError("cTrader token refresh: missing tokens in response")

        logger.info("cTrader access token refreshed")
        return CTraderTokens(
            access_token=access,
            refresh_token=refresh,
            expires_in=data.get("expiresIn") or data.get("expires_in"),
        )

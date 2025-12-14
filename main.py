import os
import time
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

APP_NAME = "zl6-apitest-api"

ZL6_BASE_URL = os.getenv("ZL6_BASE_URL", "").rstrip("/")
ZL6_EMAIL = os.getenv("ZL6_EMAIL", "")
ZL6_PASSWORD = os.getenv("ZL6_PASSWORD", "")

ZL6_LOGIN_PATH = os.getenv("ZL6_LOGIN_PATH", "/auth/login")
ZL6_STATIONS_PATH = os.getenv("ZL6_STATIONS_PATH", "/stations")
ZL6_LATEST_PATH = os.getenv("ZL6_LATEST_PATH", "/measurements/latest")

_token: Optional[str] = None
_token_expire_at: float = 0.0

app = FastAPI(title=APP_NAME)

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN] if FRONTEND_ORIGIN != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _require_env():
    if not ZL6_BASE_URL:
        raise RuntimeError("ZL6_BASE_URL is missing")
    if not ZL6_EMAIL or not ZL6_PASSWORD:
        raise RuntimeError("ZL6_EMAIL / ZL6_PASSWORD is missing")

async def _login_and_get_token(client: httpx.AsyncClient) -> Dict[str, Any]:
    url = f"{ZL6_BASE_URL}{ZL6_LOGIN_PATH}"
    payload = {"email": ZL6_EMAIL, "password": ZL6_PASSWORD}

    r = await client.post(url, json=payload, timeout=30)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Login failed: {r.status_code} {r.text}")

    data = r.json()
    token = data.get("access_token") or data.get("token") or data.get("jwt")
    if not token:
        raise HTTPException(status_code=502, detail="No token in login response")

    expires_in = data.get("expires_in")
    exp = data.get("exp")
    return {"token": token, "expires_in": expires_in, "exp": exp}

async def get_token() -> str:
    global _token, _token_expire_at

    _require_env()
    now = time.time()

    if _token and now < (_token_expire_at - 30):
        return _token

    async with httpx.AsyncClient() as client:
        info = await _login_and_get_token(client)
        _token = info["token"]

        if info.get("exp"):
            _token_expire_at = float(info["exp"])
        elif info.get("expires_in"):
            _token_expire_at = now + float(info["expires_in"])
        else:
            _token_expire_at = now + 50 * 60

        return _token

async def zl6_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    token = await get_token()
    url = f"{ZL6_BASE_URL}{path}"

    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}"}
        r = await client.get(url, params=params, headers=headers, timeout=30)

        if r.status_code == 401:
            global _token, _token_expire_at
            _token = None
            _token_expire_at = 0.0
            token = await get_token()
            headers = {"Authorization": f"Bearer {token}"}
            r = await client.get(url, params=params, headers=headers, timeout=30)

        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"ZL6 GET failed: {r.status_code}")

        return r.json()

@app.get("/health")
async def health():
    return {"ok": True, "name": APP_NAME}

@app.get("/api/stations")
async def stations():
    return await zl6_get(ZL6_STATIONS_PATH)

@app.get("/api/latest")
async def latest(station_id: str):
    return await zl6_get(ZL6_LATEST_PATH, params={"station_id": station_id})

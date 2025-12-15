import os
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

APP_NAME = "zl6-apitest-api"

# base는 도메인만 (문서 예시도 server="https://zentracloud.com" 형태) :contentReference[oaicite:2]{index=2}
ZL6_BASE_URL = os.getenv("ZL6_BASE_URL", "").rstrip("/")

# Copy token 값(접두사 token 포함) :contentReference[oaicite:3]{index=3}
ZENTRA_TOKEN_ID = os.getenv("ZENTRA_TOKEN_ID", "").strip()

# v4 엔드포인트는 /api/v4/... :contentReference[oaicite:4]{index=4}
ZL6_DEVICES_PATH = os.getenv("ZL6_DEVICES_PATH", "/api/v4/get_devices/")
ZL6_READINGS_PATH = os.getenv("ZL6_READINGS_PATH", "/api/v4/get_readings/")

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
    if not ZENTRA_TOKEN_ID:
        raise RuntimeError("ZENTRA_TOKEN_ID is missing")

def _auth_headers() -> Dict[str, str]:
    # 문서 예시: headers={"Authorization": "Token <Your Token>"} :contentReference[oaicite:5]{index=5}
    tok = ZENTRA_TOKEN_ID
    token_header = tok if tok.lower().startswith("token") else f"Token {tok}"
    # Copy token은 token... 형태라서 아래에서 "Token token..."이 되도록 통일
    if token_header.lower().startswith("token ") is False:
        token_header = f"Token {tok}"
    return {"Authorization": token_header, "Accept": "application/json"}

async def zl6_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    _require_env()
    url = f"{ZL6_BASE_URL}{path}"
    headers = _auth_headers()

    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        r = await client.get(url, params=params, headers=headers)

    if 300 <= r.status_code < 400:
        loc = r.headers.get("location", "")
        raise HTTPException(status_code=502, detail=f"ZL6 redirected: {r.status_code}, location={loc}")

    if r.status_code >= 400:
        snippet = (r.text or "")[:500]
        raise HTTPException(status_code=502, detail=f"ZL6 GET failed: {r.status_code} {snippet}")

    ctype = (r.headers.get("content-type") or "").lower()
    if "application/json" not in ctype:
        snippet = (r.text or "")[:500]
        raise HTTPException(status_code=502, detail=f"ZL6 non-JSON response: {r.status_code}, content-type={ctype}, body={snippet}")

    return r.json()

@app.get("/health")
async def health():
    return {"ok": True, "name": APP_NAME}

@app.get("/api/stations")
async def stations():
    return await zl6_get(ZL6_DEVICES_PATH)

@app.get("/api/latest")
async def latest(device_sn: str):
    params = {
        "device_sn": device_sn,
        "per_page": 1,
        "page_num": 1,
        "sort_by": "desc",
        "output_format": "json",
    }
    return await zl6_get(ZL6_READINGS_PATH, params=params)

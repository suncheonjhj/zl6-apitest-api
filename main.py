import os
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

APP_NAME = "zl6-apitest-api"

# ===============================
# Render 환경변수
# ===============================
# US: https://zentracloud.com/api/v4
# EU: https://zentracloud.eu/api/v4
ZL6_BASE_URL = os.getenv("ZL6_BASE_URL", "").rstrip("/")

# "2 토큰" (ID + VALUE)
ZENTRA_TOKEN_ID = os.getenv("ZENTRA_TOKEN_ID", "").strip()
ZENTRA_TOKEN_VALUE = os.getenv("ZENTRA_TOKEN_VALUE", "").strip()

# 엔드포인트 (기본값)
ZL6_DEVICES_PATH = os.getenv("ZL6_DEVICES_PATH", "/get_devices/")
ZL6_READINGS_PATH = os.getenv("ZL6_READINGS_PATH", "/get_readings/")

app = FastAPI(title=APP_NAME)

# ===============================
# CORS
# ===============================
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
    if not ZENTRA_TOKEN_ID or not ZENTRA_TOKEN_VALUE:
        raise RuntimeError("ZENTRA_TOKEN_ID / ZENTRA_TOKEN_VALUE is missing")

async def zl6_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """
    ZENTRA Cloud API 호출
    - redirect를 따라가지 않음(로그인 페이지로 튀는 문제를 잡기 위해)
    - 인증: Basic Auth (username=TOKEN_ID, password=TOKEN_VALUE)
    """
    _require_env()
    url = f"{ZL6_BASE_URL}{path}"

    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        r = await client.get(
            url,
            params=params,
            auth=httpx.BasicAuth(ZENTRA_TOKEN_ID, ZENTRA_TOKEN_VALUE),
        )

    # 리다이렉트면(보통 로그인 페이지로 튐) location을 보여주기
    if 300 <= r.status_code < 400:
        loc = r.headers.get("location", "")
        raise HTTPException(
            status_code=502,
            detail=f"ZL6 redirected: {r.status_code}, location={loc}"
        )

    # HTTP 에러면 바디 앞부분을 보여주기
    if r.status_code >= 400:
        snippet = (r.text or "")[:500]
        raise HTTPException(
            status_code=502,
            detail=f"ZL6 GET failed: {r.status_code} {snippet}"
        )

    # JSON인지 확인
    ctype = (r.headers.get("content-type") or "").lower()
    if "application/json" not in ctype:
        snippet = (r.text or "")[:500]
        raise HTTPException(
            status_code=502,
            detail=f"ZL6 non-JSON response: {r.status_code}, content-type={ctype}, body={snippet}"
        )

    return r.json()

# ===============================
# routes
# ===============================
@app.get("/health")
async def health():
    return {"ok": True, "name": APP_NAME}

@app.get("/api/stations")
async def stations():
    # 실제로는 device 목록
    return await zl6_get(ZL6_DEVICES_PATH)

@app.get("/api/latest")
async def latest(device_sn: str):
    params = {
        "device_sn": device_sn,
        "per_page": 1,
        "page_num": 1,
        "sort_by": "descending",
        "output_format": "json",
    }
    return await zl6_get(ZL6_READINGS_PATH, params=params)

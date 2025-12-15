import os
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

APP_NAME = "zl6-apitest-api"

# ===============================
# 환경변수 (Render에서 설정)
# ===============================
# 예: https://zentracloud.com/api/v4
ZL6_BASE_URL = os.getenv("ZL6_BASE_URL", "").rstrip("/")

# ZENTRA Cloud API Token
ZENTRA_TOKEN_ID = os.getenv("ZENTRA_TOKEN_ID", "")
ZENTRA_TOKEN_VALUE = os.getenv("ZENTRA_TOKEN_VALUE", "")

# ZENTRA Cloud API 경로 (기본값)
ZL6_STATIONS_PATH = os.getenv("ZL6_STATIONS_PATH", "/stations")
ZL6_LATEST_PATH = os.getenv("ZL6_LATEST_PATH", "/measurements/latest")

app = FastAPI(title=APP_NAME)

# ===============================
# CORS 설정
# ===============================
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN] if FRONTEND_ORIGIN != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===============================
# 내부 헬퍼
# ===============================
def _require_env():
    if not ZL6_BASE_URL:
        raise RuntimeError("ZL6_BASE_URL is missing")
    if not ZENTRA_TOKEN_ID or not ZENTRA_TOKEN_VALUE:
        raise RuntimeError("ZENTRA_TOKEN_ID / ZENTRA_TOKEN_VALUE is missing")

async def zl6_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """
    ZENTRA Cloud API 호출
    인증 방식: HTTP Basic Auth
    username = TokenID:TokenValue
    password = 빈 문자열
    """
    _require_env()
    url = f"{ZL6_BASE_URL}{path}"

    # ZENTRA Cloud 권장 인증 방식
    basic_user = f"{ZENTRA_TOKEN_ID}:{ZENTRA_TOKEN_VALUE}"

    async with httpx.AsyncClient() as client:
        r = await client.get(
            url,
            params=params,
            auth=httpx.BasicAuth(basic_user, ""),
            timeout=30
        )

        if r.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"ZL6 GET failed: {r.status_code} {r.text}"
            )

        return r.json()

# ===============================
# API 엔드포인트
# ===============================
@app.get("/health")
async def health():
    return {"ok": True, "name": APP_NAME}

@app.get("/api/stations")
async def stations():
    """
    스테이션 목록
    """
    return await zl6_get(ZL6_STATIONS_PATH)

@app.get("/api/latest")
async def latest(station_id: str):
    """
    스테이션 최신 데이터
    """
    return await zl6_get(
        ZL6_LATEST_PATH,
        params={"station_id": station_id}
    )

import os
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

APP_NAME = "zl6-apitest-api"

# ===============================
# Render 환경변수
# ===============================
# 예: https://zentracloud.com/api/v4
ZL6_BASE_URL = os.getenv("ZL6_BASE_URL", "").rstrip("/")

# ZENTRA Cloud "token id" (Copy token으로 복사하면 token 접두사 포함)
ZENTRA_TOKEN_ID = os.getenv("ZENTRA_TOKEN_ID", "").strip()

# 엔드포인트 경로(기본값은 문서 예시 기반)
# 장치 목록(=우리가 화면에서 'stations'처럼 보여줄 것)
ZL6_DEVICES_PATH = os.getenv("ZL6_DEVICES_PATH", "/get_devices/")

# 최신값(1시간 간격 데이터에서 최신 1개만 가져오게 per_page=1)
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

# ===============================
# helpers
# ===============================
def _require_env():
    if not ZL6_BASE_URL:
        raise RuntimeError("ZL6_BASE_URL is missing")
    if not ZENTRA_TOKEN_ID:
        raise RuntimeError("ZENTRA_TOKEN_ID is missing")

def _auth_header() -> Dict[str, str]:
    """
    ZENTRA Cloud 문서 예시 방식:
    Authorization: Token <token-id>
    token-id는 'token' 접두사가 포함된 형태가 권장됨.
    사용자가 Token 접두사를 안 붙였으면 자동으로 붙여줌.
    """
    tok = ZENTRA_TOKEN_ID
    # 문서 코드 스니펫처럼 "Token " 접두사 강제
    if not tok.lower().startswith("token"):
        tok = f"Token {tok}"
    elif not tok.startswith("Token "):
        # token으로 시작하지만 대소문자/형식이 애매하면 표준형으로
        tok = f"Token {tok.split()[-1]}"
    return {"Authorization": tok}

async def zl6_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    _require_env()
    url = f"{ZL6_BASE_URL}{path}"
    headers = _auth_header()

    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        r = await client.get(url, params=params, headers=headers)

    # HTTP 에러면 그대로 502로 올려서 프론트에서 보이게
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

    # JSON 파싱
    try:
        return r.json()
    except Exception:
        snippet = (r.text or "")[:500]
        raise HTTPException(
            status_code=502,
            detail=f"ZL6 JSON parse failed: {snippet}"
        )

# ===============================
# routes
# ===============================
@app.get("/health")
async def health():
    return {"ok": True, "name": APP_NAME}

@app.get("/api/stations")
async def stations():
    """
    프론트에서 'stations'로 쓰지만,
    실제로는 ZENTRA의 device 목록을 반환.
    """
    return await zl6_get(ZL6_DEVICES_PATH)

@app.get("/api/latest")
async def latest(device_sn: str):
    """
    최신 1개 readings.
    프론트에서 station_id 대신 device_sn(장치 시리얼)을 사용.
    """
    params = {
        "device_sn": device_sn,
        "per_page": 1,
        "page_num": 1,
        "sort_by": "descending",
        "output_format": "json",
    }
    return await zl6_get(ZL6_READINGS_PATH, params=params)

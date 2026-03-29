import requests
import streamlit as st
from datetime import datetime, timedelta

BASE_URL = "https://openapi.koreainvestment.com:9443"

# ────────────────────────────────────────────
# Access Token 자동 발급 및 캐싱
# ────────────────────────────────────────────
def get_access_token() -> str:
    """
    Access Token을 발급받아 st.session_state에 캐싱.
    만료 시 자동 재발급.
    """
    now = datetime.now()

    # 이미 유효한 토큰이 있으면 재사용
    if (
        "kis_token" in st.session_state
        and "kis_token_exp" in st.session_state
        and st.session_state["kis_token_exp"] > now
    ):
        return st.session_state["kis_token"]

    # 신규 발급
    url = f"{BASE_URL}/oauth2/tokenP"
    body = {
        "grant_type": "client_credentials",
        "appkey": st.secrets["KIS_APP_KEY"],
        "appsecret": st.secrets["KIS_APP_SECRET"],
    }
    r = requests.post(url, json=body)
    r.raise_for_status()
    data = r.json()

    token = data["access_token"]
    # 만료 시각 (유효기간 24시간, 여유 있게 23시간으로 설정)
    expires_at = now + timedelta(hours=23)

    st.session_state["kis_token"] = token
    st.session_state["kis_token_exp"] = expires_at

    return token

# ────────────────────────────────────────────
# 공통 헤더
# ────────────────────────────────────────────
def get_headers(tr_id: str) -> dict:
    return {
        "content-type": "application/json",
        "authorization": f"Bearer {get_access_token()}",
        "appkey": KIS_APP_KEY,
        "appsecret": KIS_APP_SECRET,
        "tr_id": tr_id,
        "custtype": "P",
    }

# ── 거래량 순위 ──────────────────────────────────────────────
def get_volume_rank(market="0000") -> list[dict]:
    """거래량 순위 (tr_id: FHPST01710000)"""
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/volume-rank"
    params = {
        "FID_COND_MRK_DIV_CODE": "V",
        "FID_COND_SCR_DIV_CODE": "20171",
        "FID_INPUT_ISCD": market,      # 0000: 전체, 0001: 코스피, 1001: 코스닥
        "FID_DIV_CLS_CODE": "0",
        "FID_BLNG_CLS_CODE": "0",
        "FID_TRGT_CLS_CODE": "111111111",
        "FID_TRGT_EXLS_CLS_CODE": "000000",
        "FID_INPUT_PRICE_1": "",
        "FID_INPUT_PRICE_2": "",
        "FID_VOL_CNT": "",
        "FID_INPUT_DATE_1": "",
    }
    r = requests.get(url, headers=get_headers("FHPST01710000"), params=params)
    return r.json().get("output", [])

# ── 거래대금 순위 ─────────────────────────────────────────────
def get_amount_rank(market="0000") -> list[dict]:
    """거래대금 순위 — 거래량순위 API에서 acml_tr_pbmn 기준으로 정렬"""
    data = get_volume_rank(market)
    return sorted(data, key=lambda x: int(x.get("acml_tr_pbmn", 0)), reverse=True)

# ── 등락률 순위 ──────────────────────────────────────────────
def get_fluctuation_rank(market="J") -> list[dict]:
    """등락률 순위 (tr_id: FHPST01740000)"""
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/fluc-rank"
    params = {
        "FID_COND_MRK_DIV_CODE": market,   # J: 코스피, Q: 코스닥
        "FID_COND_SCR_DIV_CODE": "20174",
        "FID_INPUT_ISCD": "0000",
        "FID_RANK_SORT_CLS_CODE": "0",     # 0: 상승률, 1: 하락률
        "FID_INPUT_CNT_1": "0",
        "FID_PRC_CLS_CODE": "0",
        "FID_INPUT_PRICE_1": "",
        "FID_INPUT_PRICE_2": "",
        "FID_VOL_CNT": "",
        "FID_TRGT_CLS_CODE": "0",
        "FID_TRGT_EXLS_CLS_CODE": "0",
        "FID_DIV_CLS_CODE": "0",
        "FID_RST_DIV_CODE": "0",
    }
    r = requests.get(url, headers=get_headers("FHPST01740000"), params=params)
    return r.json().get("output", [])

# ── 일봉 차트 데이터 ─────────────────────────────────────────
def get_daily_chart(stk_code: str, start: str, end: str) -> list[dict]:
    """
    일봉 OHLCV
    start/end: 'YYYYMMDD'
    """
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
    params = {
        "FID_COND_MRK_DIV_CODE": "J",
        "FID_INPUT_ISCD": stk_code,
        "FID_INPUT_DATE_1": start,
        "FID_INPUT_DATE_2": end,
        "FID_PERIOD_DIV_CODE": "D",
        "FID_ORG_ADJ_PRC": "0",
    }
    r = requests.get(url, headers=get_headers("FHKST03010100"), params=params)
    return r.json().get("output2", [])

# ── 투자자별 매매 동향 ────────────────────────────────────────
def get_investor_trend(stk_code: str, start: str, end: str) -> list[dict]:
    """
    기관/외국인/개인/프로그램 일별 매매 동향
    tr_id: FHKST03010300 (종목별일별매수매도체결량)
    """
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
    # 실제 투자자 동향 API
    url = f"{BASE_URL}/uapi/domestic-stock/v1/trading/inquire-investor"
    params = {
        "FIDU_ISCD": stk_code,
        "FID_INPUT_DATE_1": start,
        "FID_INPUT_DATE_2": end,
        "FID_PERIOD_DIV_CODE": "D",
    }
    r = requests.get(url, headers=get_headers("FHKST03010300"), params=params)
    return r.json().get("output", [])

# ── 기관·외국인 추정 집계 (당일) ─────────────────────────────
def get_foreign_institution_estimate(stk_code: str) -> dict:
    """종목별 외인기관 추정가집계 (tr_id: FHKST03010200)"""
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/foreign-institution-total"
    params = {
        "FID_COND_MRK_DIV_CODE": "J",
        "FID_INPUT_ISCD": stk_code,
        "FID_INPUT_DATE_1": "",
        "FID_INPUT_DATE_2": "",
        "FID_PERIOD_DIV_CODE": "D",
    }
    r = requests.get(url, headers=get_headers("FHKST03010200"), params=params)
    return r.json().get("output", [])

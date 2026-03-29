import requests
import streamlit as st
from datetime import datetime, timedelta

BASE_URL = "https://openapi.koreainvestment.com:9443"


def get_access_token() -> str:
    now = datetime.now()
    if (
        "kis_token" in st.session_state
        and "kis_token_exp" in st.session_state
        and st.session_state["kis_token_exp"] > now
    ):
        return st.session_state["kis_token"]

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
    st.session_state["kis_token"] = token
    st.session_state["kis_token_exp"] = now + timedelta(hours=23)
    return token


def get_headers(tr_id: str) -> dict:
    return {
        "content-type": "application/json",
        "authorization": f"Bearer {get_access_token()}",
        "appkey": st.secrets["KIS_APP_KEY"],
        "appsecret": st.secrets["KIS_APP_SECRET"],
        "tr_id": tr_id,
        "custtype": "P",
    }


def get_daily_chart(stk_code: str, start: str, end: str) -> list:
    """일봉 OHLCV. start/end: YYYYMMDD"""
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


def get_investor_trend(stk_code: str, start: str, end: str) -> list:
    """기관/외국인/개인/프로그램 일별 매매동향. start/end: YYYYMMDD"""
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/foreign-institution-total"
    params = {
        "FID_COND_MRK_DIV_CODE": "J",
        "FID_INPUT_ISCD": stk_code,
        "FID_INPUT_DATE_1": start,
        "FID_INPUT_DATE_2": end,
        "FID_PERIOD_DIV_CODE": "D",
    }
    r = requests.get(url, headers=get_headers("FHKST03010200"), params=params)
    return r.json().get("output", [])

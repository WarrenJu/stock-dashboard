import streamlit as st
import requests
import pandas as pd
import time

# 스트림릿 화면 설정
st.set_page_config(page_title="2026 실시간 주식 순위", layout="wide")
st.title("📊 실시간 거래대금 상위 종목 (2026)")

# 한국투자증권 API 정보 (Streamlit Secrets에서 불러옴)
APP_KEY = st.secrets["APP_KEY"]
APP_SECRET = st.secrets["APP_SECRET"]
URL_BASE = "https://openapi.koreainvestment.com:9443"

def get_access_token():
    res = requests.post(f"{URL_BASE}/oauth2/tokenP", 
        json={"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET})
    return res.json()['access_token']

def get_stock_data(token, code):
    headers = {"authorization": f"Bearer {token}", "appkey": APP_KEY, "appsecret": APP_SECRET, "tr_id": "FHKST01010100"}
    res = requests.get(f"{URL_BASE}/uapi/domestic-stock/v1/quotations/inquire-price", 
                       headers=headers, params={"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code})
    return res.json()['output']

# 화면 갱신을 위한 루프
placeholder = st.empty()
token = get_access_token()

target_stocks = {"000660": "SK하이닉스", "005930": "삼성전자", "005380": "현대차", "373220": "LG엔솔"}

while True:
    with placeholder.container():
        results = []
        for code, name in target_stocks.items():
            data = get_stock_data(token, code)
            results.append({
                "종목명": name,
                "현재가": f"{int(data['stck_prpr']):,}원",
                "등락률": f"{data['prdy_ctrt']}%",
                "거래대금(억)": f"{int(float(data['acml_tr_pbmn']) / 100000000):,}억"
            })
        st.table(pd.DataFrame(results))
        st.write(f"최근 업데이트: {time.strftime('%H:%M:%S')}")
        time.sleep(10) # 10초마다 갱신

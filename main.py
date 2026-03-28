import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# 1. 페이지 설정 및 스타일
st.set_page_config(page_title="2026 주식 분석 터미널", layout="wide")
st.title("📈 종목별 실시간 순위 및 상세 분석")

# 2. API 설정 (Secrets 활용)
APP_KEY = st.secrets["APP_KEY"]
APP_SECRET = st.secrets["APP_SECRET"]
URL_BASE = "https://openapi.koreainvestment.com:9443"

@st.cache_data(ttl=3600) # 토큰은 1시간 동안 재사용
def get_access_token():
    res = requests.post(f"{URL_BASE}/oauth2/tokenP", 
        json={"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET})
    return res.json()['access_token']

def get_stock_info(token, code):
    headers = {"authorization": f"Bearer {token}", "appkey": APP_KEY, "appsecret": APP_SECRET, "tr_id": "FHKST01010100"}
    res = requests.get(f"{URL_BASE}/uapi/domestic-stock/v1/quotations/inquire-price", 
                       headers=headers, params={"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code})
    return res.json()['output']

def get_investor_data(token, code):
    # 기관/외국인 매매내역 (최근 수급)
    headers = {"authorization": f"Bearer {token}", "appkey": APP_KEY, "appsecret": APP_SECRET, "tr_id": "FHKST01010900"}
    res = requests.get(f"{URL_BASE}/uapi/domestic-stock/v1/quotations/inquire-investor", 
                       headers=headers, params={"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code})
    return res.json()['output']

# --- 사이드바: 필터 설정 ---
st.sidebar.header("🔍 필터 설정")
selected_date = st.sidebar.date_input("조회 날짜", datetime.now())
sort_standard = st.sidebar.selectbox("정렬 기준", ["거래대금", "거래량", "변동률"])

# --- 메인 로직 ---
token = get_access_token()
target_stocks = {"000660": "SK하이닉스", "005930": "삼성전자", "005380": "현대차", 
                 "373220": "LG엔솔", "207940": "삼바", "035420": "NAVER"}

# 데이터 수집 및 정렬
raw_data = []
for code, name in target_stocks.items():
    d = get_stock_info(token, code)
    raw_data.append({
        "코드": code, "종목명": name,
        "현재가": int(d['stck_prpr']),
        "변동률": float(d['prdy_ctrt']),
        "거래량": int(d['acml_vol']),
        "거래대금": int(float(d['acml_tr_pbmn']) / 100000000) # 억 단위
    })

df = pd.DataFrame(raw_data)

# 기준에 따른 정렬
sort_map = {"거래대금": "거래대금", "거래량": "거래량", "변동률": "변동률"}
df = df.sort_values(by=sort_map[sort_standard], ascending=False).reset_index(drop=True)

# 순위 표 출력
st.subheader(f"🏆 {sort_standard} 순위 (기준일: {selected_date})")
# 표에서 종목 선택 가능하게 만들기
selected_row = st.selectbox("상세 정보를 보려면 종목을 선택하세요", df['종목명'].tolist())

# 선택된 종목의 데이터 추출
selected_stock_code = df[df['종목명'] == selected_row]['코드'].values[0]
st.table(df)

st.divider()

# --- 종목 상세 섹션 ---
if selected_row:
    st.subheader(f"📑 {selected_row} ({selected_stock_code}) 상세 분석")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write("📊 **간이 캔들 차트 (현재가 기준)**")
        # 실제 차트 API 연동 전, 시각화 예시
        fig = go.Figure(data=[go.Indicator(
            mode = "number+delta",
            value = df[df['종목명'] == selected_row]['현재가'].values[0],
            delta = {'reference': 0, 'relative': False},
            title = {'text': "현재가(원)"}
        )])
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.write("👥 **수급 현황 (단위: 주)**")
        investor_data = get_investor_data(token, selected_stock_code)
        
        # 수급 데이터 표 구성
        sugup_df = pd.DataFrame({
            "구분": ["외국인", "기관", "개인", "프로그램"],
            "순매수량": [
                f"{int(investor_data[0]['frgn_ntby_qty']):,} ",
                f"{int(investor_data[0]['orgn_ntby_qty']):,} ",
                f"{int(investor_data[0]['prive_ntby_qty']):,} ",
                f"{int(investor_data[0]['prgm_ntby_qty']):,} "
            ]
        })
        st.dataframe(sugup_df, hide_index=True)

st.caption("※ 실시간 데이터는 한국투자증권 API 제공 한도 내에서 갱신됩니다.")

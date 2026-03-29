import streamlit as st

# ────────────────────────────────────────────
# 전역 페이지 설정 (app.py에서 한 번만 선언)
# ────────────────────────────────────────────
st.set_page_config(
    page_title="주식 분석 대시보드",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ────────────────────────────────────────────
# 사이드바 공통 UI
# ────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📈 주식 대시보드")
    st.caption("한국투자증권 KIS API")
    st.divider()

# ────────────────────────────────────────────
# 페이지 등록 (st.Page + st.navigation)
# ────────────────────────────────────────────
pg = st.navigation(
    {
        "📊 시장 분석": [
            st.Page(
                "pages/ranking.py",
                title="순위 분석",
                icon=":material/leaderboard:",
                default=True,
            ),
        ],
        # 이후 추가할 페이지들
        # "🔍 종목 분석": [
        #     st.Page("pages/stock_detail.py", title="종목 상세", icon=":material/candlestick_chart:"),
        # ],
        # "💼 포트폴리오": [
        #     st.Page("pages/portfolio.py", title="내 포트폴리오", icon=":material/pie_chart:"),
        # ],
    },
    position="sidebar",
    expanded=True,
)

pg.run()

import streamlit as st

st.set_page_config(
    page_title="주식 분석 대시보드",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

with st.sidebar:
    st.markdown("## 📈 주식 대시보드")
    st.caption("한국투자증권 KIS API")
    st.divider()

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
        # 추후 페이지 추가 예시
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

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from api.kis_api import (
    get_volume_rank,
    get_amount_rank,
    get_fluctuation_rank,
    get_daily_chart,
    get_foreign_institution_estimate,
)

st.set_page_config(page_title="순위 분석", layout="wide")
st.title("📊 주식 순위 분석")

# ────────────────────────────────────────────
# 상단 컨트롤
# ────────────────────────────────────────────
col1, col2, col3 = st.columns([2, 2, 2])

with col1:
    selected_date = st.date_input(
        "날짜 선택",
        value=datetime.today(),
        max_value=datetime.today(),
    )

with col2:
    market = st.selectbox(
        "시장",
        options=["전체", "코스피", "코스닥"],
        index=0,
    )
    market_code = {"전체": "0000", "코스피": "0001", "코스닥": "1001"}[market]
    market_code_fluc = {"전체": "J", "코스피": "J", "코스닥": "Q"}[market]

with col3:
    criteria = st.selectbox(
        "기준",
        options=["거래대금", "거래량", "변동률"],
        index=0,
    )

# ────────────────────────────────────────────
# 데이터 로드
# ────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_rank(criteria: str, market_code: str, market_code_fluc: str):
    try:
        if criteria == "거래대금":
            raw = get_amount_rank(market_code)
        elif criteria == "거래량":
            raw = get_volume_rank(market_code)
        else:
            raw = get_fluctuation_rank(market_code_fluc)
    except Exception as e:
        st.error(f"API 호출 오류: {e}")
        return pd.DataFrame()

    # ── API 응답 자체가 비어있을 때
    if not raw:
        st.warning("API 응답이 비어있습니다. 응답 원문을 확인하세요.")
        return pd.DataFrame()

    # ── 실제 응답 필드명 확인용 (처음 한 번만 확인 후 제거 가능)
    st.expander("🔍 API 응답 원문 (디버그)").write(raw[0] if raw else "없음")

    rows = []
    for i, d in enumerate(raw[:50], 1):
        if criteria == "거래대금":
            rows.append({
                "순위": i,
                "종목코드": d.get("mksc_shrn_iscd", ""),
                "종목명": d.get("hts_kor_isnm", ""),
                "현재가": f"{int(d.get('stck_prpr', 0) or 0):,}",
                "전일대비(%)": d.get("prdy_ctrt", ""),
                "거래대금(백만)": f"{int(d.get('acml_tr_pbmn', 0) or 0) // 1_000_000:,}",
                "거래량": f"{int(d.get('acml_vol', 0) or 0):,}",
            })
        elif criteria == "거래량":
            rows.append({
                "순위": i,
                "종목코드": d.get("mksc_shrn_iscd", ""),
                "종목명": d.get("hts_kor_isnm", ""),
                "현재가": f"{int(d.get('stck_prpr', 0) or 0):,}",
                "전일대비(%)": d.get("prdy_ctrt", ""),
                "거래량": f"{int(d.get('acml_vol', 0) or 0):,}",
                "거래량증가율(%)": d.get("vol_inrt", ""),
            })
        else:
            rows.append({
                "순위": i,
                "종목코드": d.get("mksc_shrn_iscd", ""),
                "종목명": d.get("hts_kor_isnm", ""),
                "현재가": f"{int(d.get('stck_prpr', 0) or 0):,}",
                "변동률(%)": d.get("prdy_ctrt", ""),
                "거래량": f"{int(d.get('acml_vol', 0) or 0):,}",
                "거래대금(백만)": f"{int(d.get('acml_tr_pbmn', 0) or 0) // 1_000_000:,}",
            })

    return pd.DataFrame(rows)

df = load_rank(criteria, market_code, market_code_fluc)

# ── 빈 df 방어
if df.empty:
    st.error("데이터를 불러오지 못했습니다. 위 디버그 메시지를 확인하세요.")
    st.stop()  # 이하 코드 실행 중단

# ────────────────────────────────────────────
# 순위 테이블
# ────────────────────────────────────────────
st.subheader(f"🏆 {criteria} 상위 50 종목")

# 변동률 색상 강조 함수
def highlight_change(val):
    try:
        v = float(str(val).replace(",", ""))
        if v > 0:
            return "color: #FF4B4B; font-weight: bold"
        elif v < 0:
            return "color: #1E90FF; font-weight: bold"
    except:
        pass
    return ""

change_col = "전일대비(%)" if "전일대비(%)" in df.columns else "변동률(%)"

styled_df = df.style.applymap(
    highlight_change,
    subset=[change_col]
)

# 클릭 선택을 위한 selectbox (표 위)
selected_name = st.selectbox(
    "📌 종목 선택 (테이블 클릭 또는 직접 선택)",
    options=df["종목명"].tolist(),
    index=None,
    placeholder="종목을 선택하면 차트가 표시됩니다.",
)

st.dataframe(
    styled_df,
    use_container_width=True,
    hide_index=True,
    height=520,
)

# ────────────────────────────────────────────
# 종목 상세 — 차트 + 매매 동향
# ────────────────────────────────────────────
if selected_name:
    row = df[df["종목명"] == selected_name].iloc[0]
    stk_code = row["종목코드"]

    st.divider()
    st.subheader(f"📈 {selected_name} ({stk_code})")

    # 차트 기간 선택
    period_map = {"1개월": 30, "3개월": 90, "6개월": 180, "1년": 365}
    period = st.radio("차트 기간", list(period_map.keys()), horizontal=True, index=1)
    days = period_map[period]
    end_dt = selected_date
    start_dt = end_dt - timedelta(days=days)

    chart_data = get_daily_chart(
        stk_code,
        start_dt.strftime("%Y%m%d"),
        end_dt.strftime("%Y%m%d"),
    )

    if chart_data:
        chart_df = pd.DataFrame(chart_data)
        chart_df["stck_bsop_date"] = pd.to_datetime(chart_df["stck_bsop_date"])
        for col in ["stck_oprc", "stck_hgpr", "stck_lwpr", "stck_clpr", "acml_vol"]:
            chart_df[col] = pd.to_numeric(chart_df[col], errors="coerce")

        # ── 캔들스틱 차트
        fig = go.Figure()

        fig.add_trace(go.Candlestick(
            x=chart_df["stck_bsop_date"],
            open=chart_df["stck_oprc"],
            high=chart_df["stck_hgpr"],
            low=chart_df["stck_lwpr"],
            close=chart_df["stck_clpr"],
            name="주가",
            increasing_line_color="#FF4B4B",
            decreasing_line_color="#1E90FF",
        ))

        # ── 거래량 바 (subplot 없이 y축 분리)
        fig.add_trace(go.Bar(
            x=chart_df["stck_bsop_date"],
            y=chart_df["acml_vol"],
            name="거래량",
            yaxis="y2",
            marker_color="rgba(128,128,128,0.3)",
        ))

        fig.update_layout(
            height=480,
            xaxis_rangeslider_visible=False,
            yaxis=dict(title="주가 (원)", side="left"),
            yaxis2=dict(
                title="거래량",
                overlaying="y",
                side="right",
                showgrid=False,
            ),
            legend=dict(orientation="h", y=1.02),
            margin=dict(l=0, r=0, t=30, b=0),
            plot_bgcolor="#0e1117",
            paper_bgcolor="#0e1117",
            font_color="#fafafa",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("차트 데이터를 불러올 수 없습니다.")

    # ────────────────────────────────────────
    # 기관·외국인·개인·프로그램 매매 동향
    # ────────────────────────────────────────
    st.subheader("💼 투자자별 매매 동향")

    investor_data = get_foreign_institution_estimate(stk_code)

    if investor_data:
        inv_df = pd.DataFrame(investor_data)

        # 컬럼 매핑 (KIS 응답 필드 → 표시 이름)
        col_map = {
            "stck_bsop_date": "날짜",
            "frgn_ntby_qty": "외국인 순매수",
            "orgn_ntby_qty": "기관 순매수",
            "indv_ntby_qty": "개인 순매수",
            "pgtr_ntby_qty": "프로그램 순매수",
            "frgn_ntby_tr_pbmn": "외국인 순매수금액",
            "orgn_ntby_tr_pbmn": "기관 순매수금액",
            "indv_ntby_tr_pbmn": "개인 순매수금액",
            "pgtr_ntby_tr_pbmn": "프로그램 순매수금액",
        }
        inv_df = inv_df.rename(columns={k: v for k, v in col_map.items() if k in inv_df.columns})

        # 순매수 수치 색상 강조
        numeric_cols = [c for c in inv_df.columns if "순매수" in c]
        for c in numeric_cols:
            inv_df[c] = pd.to_numeric(inv_df[c], errors="coerce")

        styled_inv = inv_df.style.applymap(
            lambda v: "color: #FF4B4B" if isinstance(v, (int, float)) and v > 0
            else ("color: #1E90FF" if isinstance(v, (int, float)) and v < 0 else ""),
            subset=numeric_cols,
        )

        st.dataframe(styled_inv, use_container_width=True, hide_index=True)

        # ── 순매수 추이 차트 (기관/외국인/개인)
        if "날짜" in inv_df.columns:
            inv_df["날짜"] = pd.to_datetime(inv_df["날짜"])
            fig2 = go.Figure()
            color_map = {
                "외국인 순매수": "#FF4B4B",
                "기관 순매수": "#00C49F",
                "개인 순매수": "#FFBB28",
                "프로그램 순매수": "#A259FF",
            }
            for col_name, color in color_map.items():
                if col_name in inv_df.columns:
                    fig2.add_trace(go.Bar(
                        x=inv_df["날짜"],
                        y=inv_df[col_name],
                        name=col_name,
                        marker_color=color,
                    ))
            fig2.update_layout(
                barmode="group",
                height=380,
                title="기관·외국인·개인·프로그램 순매수 추이",
                plot_bgcolor="#0e1117",
                paper_bgcolor="#0e1117",
                font_color="#fafafa",
                margin=dict(l=0, r=0, t=40, b=0),
            )
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("투자자 매매 동향 데이터가 없습니다.")

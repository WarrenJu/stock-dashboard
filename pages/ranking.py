import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import FinanceDataReader as fdr
from datetime import datetime, timedelta
from api.kis_api import get_daily_chart, get_investor_trend

st.title("📊 주식 순위 분석")

# ────────────────────────────────────────────
# 컨트롤 패널
# ────────────────────────────────────────────
col1, col2, col3 = st.columns([2, 2, 2])

with col1:
    selected_date = st.date_input(
        "날짜 선택",
        value=datetime.today() - timedelta(days=1),
        max_value=datetime.today(),
    )

with col2:
    market = st.selectbox("시장", ["전체", "코스피", "코스닥"])

with col3:
    criteria = st.selectbox("기준", ["거래대금", "거래량", "변동률"])

date_str = selected_date.strftime("%Y%m%d")

# 주말 감지
if selected_date.weekday() >= 5:
    st.warning("⚠️ 주말은 휴장입니다. 평일을 선택해주세요.")
    st.stop()

# ────────────────────────────────────────────
# 데이터 로드 (FinanceDataReader)
# ────────────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner="📡 순위 데이터 불러오는 중...")
def load_rank(criteria: str, market: str, date_str: str) -> pd.DataFrame:
    try:
        markets = []
        if market in ["전체", "코스피"]:
            markets.append(("KOSPI", fdr.StockListing("KOSPI")))
        if market in ["전체", "코스닥"]:
            markets.append(("KOSDAQ", fdr.StockListing("KOSDAQ")))

        dfs = []
        for mkt_name, listing in markets:
            code_col = "Code" if "Code" in listing.columns else listing.columns[0]
            name_col = "Name" if "Name" in listing.columns else listing.columns[1]
            tickers = listing[code_col].dropna().astype(str).tolist()

            # KRX 전종목 일괄 조회 시도
            try:
                df_ohlcv = fdr.DataReader(f"KRX/{mkt_name}", date_str, date_str)
            except Exception:
                df_ohlcv = pd.DataFrame()

            # 실패 시 개별 종목 fallback (상위 300개)
            if df_ohlcv is None or df_ohlcv.empty:
                rows = []
                for ticker in tickers[:300]:
                    try:
                        df_t = fdr.DataReader(ticker, date_str, date_str)
                        if df_t.empty or df_t["Close"].iloc[0] == 0:
                            continue
                        name = listing[listing[code_col] == ticker][name_col].values
                        rows.append({
                            "종목코드": ticker,
                            "종목명": name[0] if len(name) > 0 else ticker,
                            "시장": mkt_name,
                            "종가": int(df_t["Close"].iloc[0]),
                            "등락률": float(df_t["Change"].iloc[0]) * 100,
                            "거래량": int(df_t["Volume"].iloc[0]),
                            "거래대금": int(df_t["Close"].iloc[0]) * int(df_t["Volume"].iloc[0]),
                        })
                    except Exception:
                        continue
                if rows:
                    dfs.append(pd.DataFrame(rows))
            else:
                # 일괄 조회 성공 시 컬럼 표준화
                df_ohlcv = df_ohlcv.reset_index()
                df_ohlcv["시장"] = mkt_name
                ticker_col = [
                    c for c in df_ohlcv.columns
                    if any(k in c.lower() for k in ["symbol", "ticker", "code"])
                ]
                if ticker_col:
                    df_ohlcv = df_ohlcv.rename(columns={ticker_col[0]: "종목코드"})
                    name_map = dict(zip(listing[code_col], listing[name_col]))
                    df_ohlcv["종목명"] = df_ohlcv["종목코드"].map(name_map).fillna(df_ohlcv["종목코드"])
                dfs.append(df_ohlcv)

        if not dfs:
            return pd.DataFrame()

        df = pd.concat(dfs, ignore_index=True)

        # 컬럼명 표준화
        rename_map = {
            "Close": "종가", "close": "종가",
            "Change": "등락률", "change": "등락률",
            "Volume": "거래량", "volume": "거래량",
        }
        df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)

        # 거래대금 없으면 계산
        if "거래대금" not in df.columns:
            df["거래대금"] = df["종가"] * df["거래량"]

        # 0원 종목 제거
        df = df[df["종가"] > 0].copy()
        if df.empty:
            return pd.DataFrame()

        # 등락률 스케일 보정 (0~1 범위이면 *100)
        if df["등락률"].abs().max() < 2:
            df["등락률"] = df["등락률"] * 100

        # 정렬
        sort_map = {"거래대금": "거래대금", "거래량": "거래량", "변동률": "등락률"}
        df = df.sort_values(sort_map[criteria], ascending=False).head(50).reset_index(drop=True)
        df.index += 1
        df.index.name = "순위"

        need_cols = ["종목코드", "종목명", "시장", "종가", "등락률", "거래량", "거래대금"]
        return df[[c for c in need_cols if c in df.columns]]

    except Exception as e:
        st.error(f"데이터 로드 오류: {e}")
        return pd.DataFrame()


df_raw = load_rank(criteria, market, date_str)

if df_raw.empty:
    st.warning("⚠️ 해당 날짜 데이터가 없습니다. 공휴일이거나 아직 데이터가 없을 수 있습니다.")
    st.stop()

# ────────────────────────────────────────────
# 표시용 포맷 적용
# ────────────────────────────────────────────
df_display = df_raw.copy()
if "종가" in df_display.columns:
    df_display["종가"] = df_display["종가"].apply(lambda x: f"{int(x):,}")
if "거래량" in df_display.columns:
    df_display["거래량"] = df_display["거래량"].apply(lambda x: f"{int(x):,}")
if "거래대금" in df_display.columns:
    df_display["거래대금"] = df_display["거래대금"].apply(lambda x: f"{int(x) // 1_000_000:,} 백만")
if "등락률" in df_display.columns:
    df_display["등락률"] = df_display["등락률"].apply(lambda x: f"{float(x):+.2f}%")

# ────────────────────────────────────────────
# 순위 테이블
# ────────────────────────────────────────────
st.subheader(f"🏆 {criteria} 상위 50 — {selected_date.strftime('%Y.%m.%d')}")

def highlight_change(val):
    try:
        v = float(str(val).replace("%", "").replace("+", ""))
        if v > 0:
            return "color: #FF4B4B; font-weight: bold"
        elif v < 0:
            return "color: #1E90FF; font-weight: bold"
    except Exception:
        pass
    return ""

styled_df = (
    df_display.style.map(highlight_change, subset=["등락률"])
    if "등락률" in df_display.columns
    else df_display.style
)

selected_name = st.selectbox(
    "📌 종목 선택 (선택하면 차트가 표시됩니다)",
    options=df_raw["종목명"].tolist() if "종목명" in df_raw.columns else [],
    index=None,
    placeholder="종목을 선택하세요...",
)

st.dataframe(styled_df, use_container_width=True, hide_index=False, height=520)

# ────────────────────────────────────────────
# 종목 상세 — 캔들차트 + 매매동향
# ────────────────────────────────────────────
if selected_name and "종목명" in df_raw.columns and "종목코드" in df_raw.columns:
    row = df_raw[df_raw["종목명"] == selected_name].iloc[0]
    stk_code = str(row["종목코드"])

    st.divider()
    st.subheader(f"📈 {selected_name}  ({stk_code})")

    period_map = {"1개월": 30, "3개월": 90, "6개월": 180, "1년": 365}
    period = st.radio("차트 기간", list(period_map.keys()), horizontal=True, index=1)
    days = period_map[period]
    end_dt = selected_date
    start_dt = end_dt - timedelta(days=days)

    # ── 캔들스틱 차트 (KIS API)
    chart_data = get_daily_chart(
        stk_code,
        start_dt.strftime("%Y%m%d"),
        end_dt.strftime("%Y%m%d"),
    )

    if chart_data:
        c_df = pd.DataFrame(chart_data)
        c_df["stck_bsop_date"] = pd.to_datetime(c_df["stck_bsop_date"])
        for col in ["stck_oprc", "stck_hgpr", "stck_lwpr", "stck_clpr", "acml_vol"]:
            c_df[col] = pd.to_numeric(c_df[col], errors="coerce")

        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=c_df["stck_bsop_date"],
            open=c_df["stck_oprc"],
            high=c_df["stck_hgpr"],
            low=c_df["stck_lwpr"],
            close=c_df["stck_clpr"],
            name="주가",
            increasing_line_color="#FF4B4B",
            decreasing_line_color="#1E90FF",
        ))
        fig.add_trace(go.Bar(
            x=c_df["stck_bsop_date"],
            y=c_df["acml_vol"],
            name="거래량",
            yaxis="y2",
            marker_color="rgba(128,128,128,0.3)",
        ))
        fig.update_layout(
            height=480,
            xaxis_rangeslider_visible=False,
            yaxis=dict(title="주가 (원)", side="left"),
            yaxis2=dict(title="거래량", overlaying="y", side="right", showgrid=False),
            legend=dict(orientation="h", y=1.02),
            margin=dict(l=0, r=0, t=30, b=0),
            plot_bgcolor="#0e1117",
            paper_bgcolor="#0e1117",
            font_color="#fafafa",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("차트 데이터를 불러올 수 없습니다.")

    # ── 투자자별 매매 동향 (KIS API)
    st.subheader("💼 투자자별 매매 동향")

    investor_data = get_investor_trend(
        stk_code,
        start_dt.strftime("%Y%m%d"),
        end_dt.strftime("%Y%m%d"),
    )

    if investor_data:
        inv_df = pd.DataFrame(investor_data)
        col_map = {
            "stck_bsop_date": "날짜",
            "frgn_ntby_qty": "외국인",
            "orgn_ntby_qty": "기관",
            "indv_ntby_qty": "개인",
            "pgtr_ntby_qty": "프로그램",
            "frgn_ntby_tr_pbmn": "외국인(금액)",
            "orgn_ntby_tr_pbmn": "기관(금액)",
            "indv_ntby_tr_pbmn": "개인(금액)",
            "pgtr_ntby_tr_pbmn": "프로그램(금액)",
        }
        inv_df = inv_df.rename(columns={k: v for k, v in col_map.items() if k in inv_df.columns})

        numeric_cols = [c for c in ["외국인", "기관", "개인", "프로그램"] if c in inv_df.columns]
        for c in numeric_cols:
            inv_df[c] = pd.to_numeric(inv_df[c], errors="coerce")

        def color_val(v):
            if isinstance(v, (int, float)):
                if v > 0: return "color: #FF4B4B"
                if v < 0: return "color: #1E90FF"
            return ""

        st.dataframe(
            inv_df.style.map(color_val, subset=numeric_cols),
            use_container_width=True,
            hide_index=True,
        )

        # 순매수 추이 막대 차트
        if "날짜" in inv_df.columns and numeric_cols:
            inv_df["날짜"] = pd.to_datetime(inv_df["날짜"])
            color_map = {
                "외국인": "#FF4B4B",
                "기관": "#00C49F",
                "개인": "#FFBB28",
                "프로그램": "#A259FF",
            }
            fig2 = go.Figure()
            for cn, color in color_map.items():
                if cn in inv_df.columns:
                    fig2.add_trace(go.Bar(
                        x=inv_df["날짜"], y=inv_df[cn],
                        name=cn, marker_color=color,
                    ))
            fig2.update_layout(
                barmode="group",
                height=360,
                title="기관·외국인·개인·프로그램 순매수 추이",
                plot_bgcolor="#0e1117",
                paper_bgcolor="#0e1117",
                font_color="#fafafa",
                margin=dict(l=0, r=0, t=40, b=0),
            )
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("투자자 매매 동향 데이터가 없습니다.")    market: '코스피' | '코스닥' | '전체'
    """
    if 1:
        markets = []
        if market == "전체":
            markets = ["KOSPI", "KOSDAQ"]
        elif market == "코스피":
            markets = ["KOSPI"]
        else:
            markets = ["KOSDAQ"]

        dfs = []
        for mkt in markets:
            df_mkt = pykrx_stock.get_market_ohlcv_by_ticker(date_str, market=mkt)
            df_mkt["시장"] = mkt
            df_mkt["종목코드"] = df_mkt.index
            df_mkt["종목명"] = [
                pykrx_stock.get_market_ticker_name(t) for t in df_mkt.index
            ]
            dfs.append(df_mkt)

        df = pd.concat(dfs).reset_index(drop=True)

        # 빈 데이터 (휴장일 등)
        if df.empty:
            return pd.DataFrame()

        # 기준별 정렬
        if criteria == "거래대금":
            df = df.sort_values("거래대금", ascending=False)
            show_cols = ["종목코드", "종목명", "시장", "종가", "등락률", "거래대금", "거래량"]
        elif criteria == "거래량":
            df = df.sort_values("거래량", ascending=False)
            show_cols = ["종목코드", "종목명", "시장", "종가", "등락률", "거래량", "거래대금"]
        else:  # 변동률
            df = df.sort_values("등락률", ascending=False)
            show_cols = ["종목코드", "종목명", "시장", "종가", "등락률", "거래량", "거래대금"]

        df = df[show_cols].head(50).reset_index(drop=True)
        df.index += 1
        df.index.name = "순위"

        # 포맷
        df["종가"] = df["종가"].apply(lambda x: f"{int(x):,}")
        df["거래량"] = df["거래량"].apply(lambda x: f"{int(x):,}")
        df["거래대금"] = df["거래대금"].apply(lambda x: f"{int(x) // 1_000_000:,} 백만")
        df["등락률"] = df["등락률"].apply(lambda x: f"{x:.2f}%")

        return df

selected_date = st.date_input(
    "날짜 선택",
    value=datetime.today() - timedelta(days=1),  # 기본값: 어제
    max_value=datetime.today(),
)

# 주말 감지
if selected_date.weekday() >= 5:
    st.warning("⚠️ 주말은 휴장입니다. 가장 가까운 평일을 선택해주세요.")
    st.stop()

date_str = selected_date.strftime("%Y%m%d")
df = load_rank(criteria, market, date_str)

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

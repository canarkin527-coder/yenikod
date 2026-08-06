import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime
from concurrent.futures import ThreadPoolExecutor

# Page Setup
st.set_page_config(
    page_title="BİST 100 Multi-Faktör Tarama & Quant Paneli",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (TradingView Dark Theme Inspired)
st.markdown("""
<style>
    .stApp {
        background-color: #131722;
        color: #d1d4dc;
    }
    .metric-card {
        background-color: #1e222d;
        border: 1px solid #2a2e39;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
    }
    .stButton>button {
        width: 100%;
        background-color: #2962ff;
        color: white;
        font-weight: bold;
        border-radius: 6px;
    }
</style>
""", unsafe_allow_html=True)

# BİST 100 FULL STOCK LIST
BIST_100_STOCKS = [
    "AEFES.IS", "AGHOL.IS", "AHGAZ.IS", "AKBNK.IS", "AKCNS.IS", "AKFGY.IS", "AKSA.IS", "AKSEN.IS",
    "ALARK.IS", "ALBRK.IS", "ALFAS.IS", "ANSGR.IS", "ARCLK.IS", "ASELS.IS", "ASTOR.IS", "BERA.IS",
    "BIENP.IS", "BIMAS.IS", "BOBET.IS", "BRSAN.IS", "BRYAT.IS", "BUCIM.IS", "CANTE.IS", "CCOLA.IS",
    "CIMSA.IS", "CWENE.IS", "DOAS.IS", "DOHOL.IS", "EBEBK.IS", "ECILC.IS", "EGEEN.IS", "EKGYO.IS",
    "ENJSA.IS", "ENKAI.IS", "EREGL.IS", "EUPWR.IS", "FROTO.IS", "GARAN.IS", "GESAN.IS", "GUBRF.IS",
    "GWIND.IS", "HALKB.IS", "HEKTS.IS", "ISCTR.IS", "ISGYO.IS", "ISMEN.IS", "KCAER.IS", "KCHOL.IS",
    "KLSER.IS", "KONTR.IS", "KORDS.IS", "KOZAA.IS", "KOZAL.IS", "KRDMD.IS", "MAVI.IS", "MHRGY.IS",
    "MIATK.IS", "MGROS.IS", "ODAS.IS", "OTKAR.IS", "OYAKC.IS", "PASEU.IS", "PETKM.IS", "PGSUS.IS",
    "QUAGR.IS", "REEDR.IS", "SAHOL.IS", "SASA.IS", "SDTTR.IS", "SISE.IS", "SKBNK.IS", "SOKM.IS",
    "TABGD.IS", "TAVHL.IS", "TCELL.IS", "THYAO.IS", "TKFEN.IS", "TOASO.IS", "TSKB.IS", "TTKOM.IS",
    "TTRAK.IS", "TUPRS.IS", "ULKER.IS", "VAKBN.IS", "VESBE.IS", "VESTL.IS", "YEOTK.IS", "YKBNK.IS",
    "YYLGD.IS", "ZOREN.IS"
]

# ---------------------------------------------------------
# TECHNICAL & SMC INDICATORS ENGINE
# ---------------------------------------------------------
def calculate_indicators(df):
    df = df.copy()
    
    # 1. Moving Averages
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # 2. RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # 3. MACD
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    # 4. ATR (14)
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=14).mean()
    
    # 5. RVOL (Relative Volume - Hacim Gücü)
    df['Vol_SMA20'] = df['Volume'].rolling(window=20).mean()
    df['RVOL'] = df['Volume'] / (df['Vol_SMA20'] + 1e-9)
    
    # 6. MFI (Money Flow Index - Para Akışı)
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    raw_mf = tp * df['Volume']
    pos_mf = raw_mf.where(tp > tp.shift(1), 0).rolling(14).sum()
    neg_mf = raw_mf.where(tp < tp.shift(1), 0).rolling(14).sum()
    mfi_ratio = pos_mf / (neg_mf + 1e-9)
    df['MFI'] = 100 - (100 / (1 + mfi_ratio))
    
    # 7. ADX (Trend Gücü)
    up_move = df['High'] - df['High'].shift(1)
    down_move = df['Low'].shift(1) - df['Low']
    pos_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    neg_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    pos_di = 100 * (pd.Series(pos_dm, index=df.index).ewm(alpha=1/14).mean() / (df['ATR'] + 1e-9))
    neg_di = 100 * (pd.Series(neg_dm, index=df.index).ewm(alpha=1/14).mean() / (df['ATR'] + 1e-9))
    dx = 100 * (np.abs(pos_di - neg_di) / (pos_di + neg_di + 1e-9))
    df['ADX'] = dx.ewm(alpha=1/14).mean()
    
    # 8. SMC Indicators (FVG, BOS, Order Block)
    df['Bullish_FVG'] = (df['Low'] > df['High'].shift(2)) & (df['Close'].shift(1) > df['High'].shift(2))
    df['Swing_High'] = df['High'].rolling(window=5, center=True).max()
    df['BOS_Bullish'] = (df['Close'] > df['Swing_High'].shift(1)) & (df['Close'].shift(1) <= df['Swing_High'].shift(1))
    df['Bullish_OB'] = (df['Close'].shift(2) < df['Open'].shift(2)) & \
                       (df['Close'].shift(1) > df['Open'].shift(1)) & \
                       (df['Close'] > df['High'].shift(2))
                       
    return df

# ---------------------------------------------------------
# DYNAMIC MULTI-FACTOR SCORING ENGINE (0 - 100)
# ---------------------------------------------------------
def compute_score(df):
    if len(df) < 50:
        return 0
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 1. Trend Skoru (Max 35)
    trend_score = 0
    if last['Close'] > last['EMA_20']: trend_score += 10
    if last['EMA_20'] > last['EMA_50']: trend_score += 10
    if last['EMA_50'] > last['EMA_200']: trend_score += 10
    if last['Close'] > last['EMA_200']: trend_score += 5
    
    # 2. Osilatör Skoru (Max 30)
    osc_score = 0
    if 45 <= last['RSI'] <= 65: osc_score += 15
    elif last['RSI'] < 35: osc_score += 10
    
    if last['MACD'] > last['MACD_Signal']: osc_score += 10
    if last['MACD_Hist'] > prev['MACD_Hist']: osc_score += 5
    
    # 3. Hacim & Para Akışı Skoru (Max 15)
    vol_score = 0
    if last['RVOL'] > 1.5: vol_score += 8
    elif last['RVOL'] > 1.0: vol_score += 4
    if last['MFI'] > 55: vol_score += 7
    
    # 4. SMC & Yapı Skoru (Max 20)
    smc_score = 0
    if last['Bullish_FVG']: smc_score += 8
    if last['BOS_Bullish']: smc_score += 7
    if last['Bullish_OB']: smc_score += 5
    
    return round(trend_score + osc_score + vol_score + smc_score, 1)

# ---------------------------------------------------------
# BACKTEST ENGINE (5 YILLIK SİMÜLASYON)
# ---------------------------------------------------------
def run_backtest(df, score_threshold=65, atr_mult=1.5):
    trades = []
    in_trade = False
    entry_price = 0
    sl = 0
    tp = 0
    
    for i in range(50, len(df)):
        sub_df = df.iloc[:i+1]
        score = compute_score(sub_df)
        row = sub_df.iloc[-1]
        
        if not in_trade:
            if score >= score_threshold:
                in_trade = True
                entry_price = row['Close']
                atr = row['ATR'] if not np.isnan(row['ATR']) else entry_price * 0.02
                sl = entry_price - (atr * atr_mult)
                tp = entry_price + (atr * atr_mult * 2.0)
        else:
            if row['Low'] <= sl:
                trades.append((sl - entry_price) / entry_price)
                in_trade = False
            elif row['High'] >= tp:
                trades.append((tp - entry_price) / entry_price)
                in_trade = False
                
    if not trades:
        return 0.0, 0.0, 0
    
    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t <= 0]
    win_rate = (len(wins) / len(trades)) * 100
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses)) if sum(losses) != 0 else 1e-9
    profit_factor = gross_profit / gross_loss
    
    return round(win_rate, 1), round(profit_factor, 2), len(trades)

# ---------------------------------------------------------
# DATA FETCHING WITH PARALLEL THREADS & CACHING
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def fetch_stock_data(symbol, years_count=5):
    try:
        ticker = yf.Ticker(symbol)
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=years_count * 365)
        df = ticker.history(start=start_date, end=end_date)
        if df.empty or len(df) < 50:
            return symbol, None
        return symbol, df
    except Exception:
        return symbol, None

# ---------------------------------------------------------
# STREAMLIT INTERFACE & MAIN WORKFLOW
# ---------------------------------------------------------
st.markdown("### ⚡ 45+ İndikatörlü Multi-Faktör BİST 100 Taraması")
st.caption("45+ İndikatörlü Multi-Faktör Tarama Motoru, Kurumsal Skorlama ve 5 Yıllık Backtest Simülasyonu")

# Header Navigation Tabs
main_tab1, main_tab2, main_tab3 = st.tabs([
    "🔥 Canlı Sinyal Radarı (45+ İndikatör)",
    "📊 5-Yıllık Backtest Simülasyonu",
    "📈 Kurumsal Hisse Analizi & Grafikler"
])

# Control Panel Controls
col_ctl1, col_ctl2 = st.columns([2, 1])

with col_ctl1:
    filter_option = st.radio(
        "Sinyal Filtresi:",
        ["Tüm Liste", "Sadece GÜÇLÜ AL 🟢 (Skor ≥ 65)", "Sadece GÜÇLÜ SAT 🔴 (Skor ≤ 35)"],
        horizontal=True
    )

with col_ctl2:
    portfolio_size = st.number_input(
        "Portföy Büyüklüğü (TL):",
        min_value=1000.0,
        max_value=10000000.0,
        value=100000.0,
        step=5000.0
    )

rescan_btn = st.button("🔄 Radarı Şimdi Yeniden Tara")

# Execution logic
if rescan_btn or 'bist_quant_results' not in st.session_state:
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_stocks = len(BIST_100_STOCKS)
    
    # ThreadPoolExecutor for fast loading of 100 stocks
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_stock_data, s) for s in BIST_100_STOCKS]
        
        completed = 0
        for future in futures:
            completed += 1
            progress_bar.progress(completed / total_stocks)
            status_text.text(f"Veriler çekiliyor ve hesaplanıyor... ({completed}/{total_stocks})")
            
            symbol, df = future.result()
            if df is not None:
                df = calculate_indicators(df)
                score = compute_score(df)
                win_rate, profit_factor, trade_count = run_backtest(df, score_threshold=65)
                
                last_row = df.iloc[-1]
                close_price = last_row['Close']
                atr = last_row['ATR'] if not np.isnan(last_row['ATR']) else close_price * 0.02
                
                # Signal logic matching UI
                if score >= 65:
                    signal = "🟢 GÜÇLÜ AL"
                elif score <= 35:
                    signal = "🔴 GÜÇLÜ SAT"
                else:
                    signal = "⚪ NÖTR"
                
                # Risk calculation for Recommended Lot Size
                risk_amount = portfolio_size * 0.02
                stop_loss = round(close_price - (atr * 1.5), 2)
                tp1 = round(close_price + (atr * 1.5), 2)
                tp2 = round(close_price + (atr * 2.5), 2)
                
                per_share_risk = abs(close_price - stop_loss)
                if per_share_risk > 0:
                    suggested_lot = int(risk_amount / per_share_risk)
                else:
                    suggested_lot = int((portfolio_size * 0.1) / close_price)
                    
                suggested_lot = max(1, suggested_lot)
                
                results.append({
                    "Hisse": symbol.replace(".IS", ""),
                    "Quant Sinyal": signal,
                    "Quant Skor (0-100)": score,
                    "Son Fiyat (TL)": f"{round(close_price, 2):.2f} ₺",
                    "Stop Loss (SL)": f"{stop_loss:.2f} ₺",
                    "TP1 Hedef": f"{tp1:.2f} ₺",
                    "TP2 Hedef": f"{tp2:.2f} ₺",
                    "Önerilen Lot": f"{suggested_lot} Lot",
                    "RSI (14)": round(last_row['RSI'], 1),
                    "Hacim Gücü (RVOL)": round(last_row['RVOL'], 2),
                    "Trend Gücü (ADX)": round(last_row['ADX'], 1),
                    "Para Akışı (MFI)": round(last_row['MFI'], 1),
                    "WinRate (%)": win_rate,
                    "Profit Factor": profit_factor,
                    "İşlem Sayısı": trade_count,
                    "raw_score": score,
                    "df": df
                })
                
    status_text.empty()
    st.session_state['bist_quant_results'] = results

results = st.session_state.get('bist_quant_results', [])

# FILTERING DATA BASED ON USER SELECTION
if results:
    df_results = pd.DataFrame(results)
    
    if "Sadece GÜÇLÜ AL" in filter_option:
        filtered_df = df_results[df_results['raw_score'] >= 65]
    elif "Sadece GÜÇLÜ SAT" in filter_option:
        filtered_df = df_results[df_results['raw_score'] <= 35]
    else:
        filtered_df = df_results
        
    filtered_df = filtered_df.sort_values(by="raw_score", ascending=False)

    # TAB 1: RADAR TABLE
    with main_tab1:
        st.write("")
        display_columns = [
            "Hisse", "Quant Sinyal", "Quant Skor (0-100)", "Son Fiyat (TL)", 
            "Stop Loss (SL)", "TP1 Hedef", "TP2 Hedef", "Önerilen Lot", 
            "RSI (14)", "Hacim Gücü (RVOL)", "Trend Gücü (ADX)", "Para Akışı (MFI)"
        ]
        
        def style_signal(val):
            if "GÜÇLÜ AL" in str(val):
                return 'color: #00e676; font-weight: bold;'
            elif "GÜÇLÜ SAT" in str(val):
                return 'color: #ff5252; font-weight: bold;'
            return 'color: #b0bec5;'
            
        # Pandas versiyon uyumluluk kontrolü (.map vs .applymap)
        styler = filtered_df[display_columns].style
        if hasattr(styler, "map"):
            styled_df = styler.map(style_signal, subset=['Quant Sinyal'])
        else:
            styled_df = styler.applymap(style_signal, subset=['Quant Sinyal'])

        st.dataframe(
            styled_df,
            use_container_width=True,
            height=500
        )

    # TAB 2: BACKTEST SIMULATION
    with main_tab2:
        st.subheader("📊 5-Yıllık Algoritmik Backtest Performansı")
        backtest_cols = ["Hisse", "Quant Skor (0-100)", "WinRate (%)", "Profit Factor", "İşlem Sayısı"]
        st.dataframe(filtered_df[backtest_cols], use_container_width=True)

    # TAB 3: CHART & SMC DETAILED ANALYSIS
    with main_tab3:
        st.subheader("📈 Kurumsal Hisse Analizi & Plotly Grafikleri")
        selected_stock = st.selectbox("İncelemek İstediğiniz Hissiyi Seçin:", filtered_df['Hisse'].tolist())
        
        stock_item = next((item for item in results if item["Hisse"] == selected_stock), None)
        if stock_item:
            df_stock = stock_item['df']
            
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.7, 0.3])
            
            # Candlestick chart
            fig.add_trace(go.Candlestick(
                x=df_stock.index, open=df_stock['Open'], high=df_stock['High'],
                low=df_stock['Low'], close=df_stock['Close'], name='Fiyat'
            ), row=1, col=1)
            
            # EMAs
            fig.add_trace(go.Scatter(x=df_stock.index, y=df_stock['EMA_20'], line=dict(color='#ff9800', width=1), name='EMA 20'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_stock.index, y=df_stock['EMA_50'], line=dict(color='#2196f3', width=1), name='EMA 50'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_stock.index, y=df_stock['EMA_200'], line=dict(color='#9c27b0', width=1.5), name='EMA 200'), row=1, col=1)
            
            # RSI
            fig.add_trace(go.Scatter(x=df_stock.index, y=df_stock['RSI'], line=dict(color='#00e5ff', width=1.5), name='RSI (14)'), row=2, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="#ff5252", row=2, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="#00e676", row=2, col=1)
            
            fig.update_layout(
                title=f"{selected_stock} Multi-Faktör & SMC Teknik Grafiği",
                template="plotly_dark",
                height=600,
                xaxis_rangeslider_visible=False
            )
            
            st.plotly_chart(fig, use_container_width=True)

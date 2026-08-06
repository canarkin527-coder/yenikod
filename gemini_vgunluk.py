import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings

# Konsol uyarılarını gizle
warnings.filterwarnings('ignore')

# ---------------------------------------------------------
# 1. STREAMLIT SAYFA AYARI
# ---------------------------------------------------------
st.set_page_config(
    page_title="BİST 100 Institutional Quant & SMC Engine",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Dark Theme
st.markdown("""
<style>
    .stApp {
        background-color: #131722;
        color: #d1d4dc;
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

# BİST 100 HİSSE LİSTESİ
BIST_100_STOCKS = [
    "AEFES.IS", "AGHOL.IS", "AHGAZ.IS", "AKBNK.IS", "AKCNS.IS", "AKFGY.IS", "AKSA.IS", "AKSEN.IS",
    "ALARK.IS", "ALBRK.IS", "ALFAS.IS", "ANSGR.IS", "ARCLK.IS", "ASELS.IS", "ASTOR.IS", "BERA.IS",
    "BIMAS.IS", "BOBET.IS", "BRSAN.IS", "BRYAT.IS", "BUCIM.IS", "CANTE.IS", "CCOLA.IS", "CIMSA.IS",
    "CWENE.IS", "DOAS.IS", "DOHOL.IS", "EBEBK.IS", "ECILC.IS", "EGEEN.IS", "EKGYO.IS", "ENJSA.IS",
    "ENKAI.IS", "EREGL.IS", "EUPWR.IS", "FROTO.IS", "GARAN.IS", "GESAN.IS", "GUBRF.IS", "GWIND.IS",
    "HALKB.IS", "HEKTS.IS", "ISCTR.IS", "ISGYO.IS", "ISMEN.IS", "KCAER.IS", "KCHOL.IS", "KLSER.IS",
    "KONTR.IS", "KORDS.IS", "KOZAL.IS", "KRDMD.IS", "MAVI.IS", "MHRGY.IS", "MIATK.IS", "MGROS.IS",
    "ODAS.IS", "OTKAR.IS", "OYAKC.IS", "PASEU.IS", "PETKM.IS", "PGSUS.IS", "QUAGR.IS", "REEDR.IS",
    "SAHOL.IS", "SASA.IS", "SDTTR.IS", "SISE.IS", "SKBNK.IS", "SOKM.IS", "TABGD.IS", "TAVHL.IS",
    "TCELL.IS", "THYAO.IS", "TKFEN.IS", "TOASO.IS", "TSKB.IS", "TTKOM.IS", "TTRAK.IS", "TUPRS.IS",
    "ULKER.IS", "VAKBN.IS", "VESBE.IS", "VESTL.IS", "YEOTK.IS", "YKBNK.IS", "YYLGD.IS", "ZOREN.IS"
]

# ---------------------------------------------------------
# 2. İNDİKATÖR VE SMC HESAPLAMA MOTORU
# ---------------------------------------------------------
def calculate_wilder_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-12)
    return 100.0 - (100.0 / (1.0 + rs))

def calculate_wilder_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift(1))
    low_close = np.abs(df['Low'] - df['Close'].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()

def calculate_indicators(df):
    df = df.copy()
    
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    df['RSI'] = calculate_wilder_rsi(df['Close'], 14)
    df['ATR'] = calculate_wilder_atr(df, 14)
    
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    df['Vol_SMA20'] = df['Volume'].rolling(20).mean()
    df['RVOL'] = df['Volume'] / (df['Vol_SMA20'] + 1e-9)
    df['VWAP'] = (df['Volume'] * (df['High'] + df['Low'] + df['Close']) / 3).cumsum() / (df['Volume'].cumsum() + 1e-9)
    
    df['Bullish_FVG'] = (df['Low'] > df['High'].shift(2)) & ((df['Low'] - df['High'].shift(2)) > (df['ATR'] * 0.15))
    df['Swing_High'] = df['High'].rolling(window=5, center=True).max()
    df['BOS_Bullish'] = (df['Close'] > df['Swing_High'].shift(1)) & (df['Close'].shift(1) <= df['Swing_High'].shift(1))
    
    displacement = (df['Close'] - df['Open']).abs() > (df['ATR'] * 1.1)
    df['Bullish_OB'] = (df['Close'].shift(1) < df['Open'].shift(1)) & displacement & (df['Close'] > df['High'].shift(1))
    
    return df

# ---------------------------------------------------------
# 3. SKORLAMA MOTORU
# ---------------------------------------------------------
def compute_score(df):
    if len(df) < 50:
        return 0.0
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    score = 0
    if last['Close'] > last['EMA_200']: score += 15
    if last['Close'] > last['EMA_20']: score += 10
    if last['EMA_20'] > last['EMA_50']: score += 10
    
    if 45 <= last['RSI'] <= 65: score += 15
    elif last['RSI'] < 35: score += 10
    if last['MACD'] > last['MACD_Signal']: score += 10
    if last['MACD_Hist'] > prev['MACD_Hist']: score += 5
    
    if last['RVOL'] > 1.5: score += 10
    elif last['RVOL'] > 1.0: score += 5
    if last['Close'] > last['VWAP']: score += 5
    
    if last['Bullish_FVG']: score += 10
    if last['BOS_Bullish']: score += 5
    if last['Bullish_OB']: score += 5
    
    return float(round(score, 1))

# ---------------------------------------------------------
# 4. BACKTEST MOTORU
# ---------------------------------------------------------
def run_backtest(df, score_threshold=65):
    trades = []
    in_trade = False
    entry_price = 0.0
    sl = 0.0
    tp = 0.0
    
    for i in range(50, len(df) - 1):
        sub_df = df.iloc[:i+1]
        score = compute_score(sub_df)
        next_open = df.iloc[i+1]['Open']
        
        if not in_trade:
            if score >= score_threshold:
                in_trade = True
                entry_price = next_open
                atr = sub_df.iloc[-1]['ATR']
                if np.isnan(atr) or atr == 0:
                    atr = entry_price * 0.02
                sl = entry_price - (atr * 1.5)
                tp = entry_price + (atr * 3.0)
        else:
            next_low = df.iloc[i+1]['Low']
            next_high = df.iloc[i+1]['High']
            
            if next_low <= sl:
                trades.append((sl - entry_price) / entry_price)
                in_trade = False
            elif next_high >= tp:
                trades.append((tp - entry_price) / entry_price)
                in_trade = False
                
    if not trades:
        return 0.0, 0.0, 0
    
    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t <= 0]
    win_rate = (len(wins) / len(trades)) * 100.0
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses)) if sum(losses) != 0 else 1e-9
    profit_factor = gross_profit / gross_loss
    
    return round(win_rate, 1), round(profit_factor, 2), len(trades)

# ---------------------------------------------------------
# 5. GÜVENLİ VE THREAD-FREE VERİ ÇEKME
# ---------------------------------------------------------
@st.cache_data(ttl=1800)
def fetch_all_stocks_data(symbols):
    try:
        # threads=False ile ScriptRunContext uyarısı tamamen engellenir
        data = yf.download(symbols, period="2y", group_by='ticker', auto_adjust=True, progress=False, threads=False)
        return data
    except Exception:
        return None

# ---------------------------------------------------------
# 6. ARAYÜZ
# ---------------------------------------------------------
st.title("⚡ BİST 100 Multi-Faktör Tarama & Quant Paneli")
st.caption("v33 Ultimate Motoru: Wilder Göstergeleri, SMC Yapıları ve Risk Yönetimi")

col1, col2 = st.columns([2, 1])
with col1:
    filter_opt = st.radio(
        "Filtrele:",
        ["Tüm Liste", "Sadece GÜÇLÜ AL 🟢 (Skor ≥ 65)", "Sadece GÜÇLÜ SAT 🔴 (Skor ≤ 35)"],
        horizontal=True
    )

with col2:
    portfolio_size = st.number_input("Portföy Büyüklüğü (TL):", value=100000.0, step=5000.0)

scan_btn = st.button("🔄 Radarı Başlat / Yenile")

if scan_btn or 'quant_data' not in st.session_state:
    results = []
    status = st.empty()
    status.text("BİST 100 verileri indiriliyor ve işleniyor...")
    
    batch_data = fetch_all_stocks_data(BIST_100_STOCKS)
    
    if batch_data is not None:
        for symbol in BIST_100_STOCKS:
            try:
                if len(BIST_100_STOCKS) > 1:
                    if symbol in batch_data.columns.levels[0]:
                        df = batch_data[symbol].dropna(how='all')
                    else:
                        continue
                else:
                    df = batch_data.dropna(how='all')
                    
                if df.empty or len(df) < 50:
                    continue

                df = df.dropna(subset=['Close', 'High', 'Low', 'Open', 'Volume'])
                
                df = calculate_indicators(df)
                score = compute_score(df)
                win_rate, profit_factor, trade_count = run_backtest(df)
                
                last = df.iloc[-1]
                close = last['Close']
                atr = last['ATR'] if not np.isnan(last['ATR']) else close * 0.02
                
                if score >= 65: signal = "🟢 GÜÇLÜ AL"
                elif score <= 35: signal = "🔴 GÜÇLÜ SAT"
                else: signal = "⚪ NÖTR"
                
                stop_loss = round(close - (atr * 1.5), 2)
                tp1 = round(close + (atr * 1.5), 2)
                tp2 = round(close + (atr * 3.0), 2)
                
                risk_per_share = abs(close - stop_loss)
                risk_amount = portfolio_size * 0.02
                suggested_lot = int(risk_amount / risk_per_share) if risk_per_share > 0 else 1
                suggested_lot = max(1, suggested_lot)
                
                results.append({
                    "Hisse": symbol.replace(".IS", ""),
                    "Sinyal": signal,
                    "Quant Skor": score,
                    "Son Fiyat": f"{close:.2f} ₺",
                    "Stop Loss": f"{stop_loss:.2f} ₺",
                    "TP1 Hedef": f"{tp1:.2f} ₺",
                    "TP2 Hedef": f"{tp2:.2f} ₺",
                    "Önerilen Lot": f"{suggested_lot} Lot",
                    "RSI": round(last['RSI'], 1),
                    "RVOL": round(last['RVOL'], 2),
                    "WinRate (%)": win_rate,
                    "Profit Factor": profit_factor,
                    "İşlem Sayısı": trade_count,
                    "raw_score": score,
                    "df": df
                })
            except Exception:
                continue
                
    status.empty()
    st.session_state['quant_data'] = results

results = st.session_state.get('quant_data', [])

if results:
    df_res = pd.DataFrame(results)
    
    if "GÜÇLÜ AL" in filter_opt:
        df_filtered = df_res[df_res['raw_score'] >= 65]
    elif "GÜÇLÜ SAT" in filter_opt:
        df_filtered = df_res[df_res['raw_score'] <= 35]
    else:
        df_filtered = df_res
        
    df_filtered = df_filtered.sort_values(by="raw_score", ascending=False)
    
    tab1, tab2, tab3 = st.tabs(["🔥 Canlı Sinyal Radarı", "📊 Backtest Sonuçları", "📈 Grafik Analizi"])
    
    with tab1:
        cols = ["Hisse", "Sinyal", "Quant Skor", "Son Fiyat", "Stop Loss", "TP1 Hedef", "TP2 Hedef", "Önerilen Lot", "RSI", "RVOL"]
        st.dataframe(df_filtered[cols], width="stretch", height=500)
        
    with tab2:
        bt_cols = ["Hisse", "Quant Skor", "WinRate (%)", "Profit Factor", "İşlem Sayısı"]
        st.dataframe(df_filtered[bt_cols], width="stretch")
        
    with tab3:
        selected_stock = st.selectbox("Hisse Seçin:", df_filtered['Hisse'].tolist())
        stock_data = next((item for item in results if item["Hisse"] == selected_stock), None)
        
        if stock_data:
            df_chart = stock_data['df']
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
            
            fig.add_trace(go.Candlestick(
                x=df_chart.index, open=df_chart['Open'], high=df_chart['High'],
                low=df_chart['Low'], close=df_chart['Close'], name='Fiyat'
            ), row=1, col=1)
            
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA_20'], line=dict(color='#ff9800', width=1), name='EMA 20'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA_50'], line=dict(color='#2196f3', width=1), name='EMA 50'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA_200'], line=dict(color='#9c27b0', width=1.5), name='EMA 200'), row=1, col=1)
            
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['RSI'], line=dict(color='#00e5ff', width=1.5), name='RSI (14)'), row=2, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="#ff5252", row=2, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="#00e676", row=2, col=1)
            
            fig.update_layout(template="plotly_dark", height=550, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, width="stretch")

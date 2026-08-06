import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime

# Page Configuration
st.set_page_config(
    page_title="BIST Quant v50.0 - Sinyal & SMC Taraması",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .metric-card {
        background-color: #1e222d;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #2a2e39;
        text-align: center;
    }
    .stApp {
        background-color: #131722;
        color: #d1d4dc;
    }
</style>
""", unsafe_allow_html=True)

# Top BIST 30 & Popular Stocks Default List
DEFAULT_STOCKS = [
    "THYAO.IS", "GARAN.IS", "EREGL.IS", "AKBNK.IS", "SISE.IS", 
    "BIMAS.IS", "TUPRS.IS", "KCHOL.IS", "SAHOL.IS", "ASELS.IS",
    "YKBNK.IS", "ISCTR.IS", "SASA.IS", "HEKTS.IS", "PENTAS.IS",
    "ASTOR.IS", "KONTR.IS", "ALARK.IS", "TOASO.IS", "FROTO.IS"
]

# ---------------------------------------------------------
# TECHNICAL & SMC INDICATORS CALCULATION
# ---------------------------------------------------------

def calculate_indicators(df):
    df = df.copy()
    
    # Moving Averages
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    # ATR (14)
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=14).mean()
    
    # Hacim Ortalaması
    df['Vol_SMA20'] = df['Volume'].rolling(window=20).mean()
    
    # --- SMC INDICATORS ---
    # Fair Value Gap (FVG)
    df['Bullish_FVG'] = (df['Low'] > df['High'].shift(2)) & (df['Close'].shift(1) > df['High'].shift(2))
    
    # Structure Break (BOS / CHOCH - Simplified)
    df['Swing_High'] = df['High'].rolling(window=5, center=True).max()
    df['Swing_Low'] = df['Low'].rolling(window=5, center=True).min()
    df['BOS_Bullish'] = (df['Close'] > df['Swing_High'].shift(1)) & (df['Close'].shift(1) <= df['Swing_High'].shift(1))
    
    # Bullish Order Block (Aşağı yönlü son mum sonrası güçlü çıkış)
    df['Bullish_OB'] = (df['Close'].shift(2) < df['Open'].shift(2)) &                        (df['Close'].shift(1) > df['Open'].shift(1)) &                        (df['Close'] > df['High'].shift(2))
                       
    return df

# ---------------------------------------------------------
# DYNAMIC SCORING ENGINE (0 - 100)
# ---------------------------------------------------------

def compute_score(df):
    if len(df) < 50:
        return 0, {}
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 1. Trend Score (Max 35)
    trend_score = 0
    if last['Close'] > last['EMA_20']: trend_score += 10
    if last['EMA_20'] > last['EMA_50']: trend_score += 10
    if last['EMA_50'] > last['EMA_200']: trend_score += 10
    if last['Close'] > last['EMA_200']: trend_score += 5
    
    # 2. Oscillator Score (Max 30)
    osc_score = 0
    if 40 <= last['RSI'] <= 65: osc_score += 15  # Sağlıklı yükseliş bölgesi
    elif last['RSI'] < 30: osc_score += 10       # Aşırı satım fırsatı
    
    if last['MACD'] > last['MACD_Signal']: osc_score += 10
    if last['MACD_Hist'] > prev['MACD_Hist']: osc_score += 5
    
    # 3. Volume Score (Max 15)
    vol_score = 0
    if last['Volume'] > last['Vol_SMA20'] * 1.5: vol_score += 15
    elif last['Volume'] > last['Vol_SMA20']: vol_score += 8
    
    # 4. SMC Score (Max 20)
    smc_score = 0
    if last['Bullish_FVG']: smc_score += 8
    if last['BOS_Bullish']: smc_score += 7
    if last['Bullish_OB']: smc_score += 5
    
    total_score = trend_score + osc_score + vol_score + smc_score
    
    breakdown = {
        "Trend (35)": trend_score,
        "Osilatör (30)": osc_score,
        "Hacim (15)": vol_score,
        "SMC (20)": smc_score
    }
    
    return total_score, breakdown

# ---------------------------------------------------------
# BACKTEST ENGINE
# ---------------------------------------------------------

def run_backtest(df, score_threshold=60, atr_mult=1.5):
    trades = []
    in_trade = False
    entry_price = 0
    sl = 0
    tp = 0
    
    for i in range(50, len(df)):
        sub_df = df.iloc[:i+1]
        score, _ = compute_score(sub_df)
        row = sub_df.iloc[-1]
        
        if not in_trade:
            if score >= score_threshold:
                in_trade = True
                entry_price = row['Close']
                atr = row['ATR'] if not np.isnan(row['ATR']) else entry_price * 0.02
                sl = entry_price - (atr * atr_mult)
                tp = entry_price + (atr * atr_mult * 2.0) # 1:2 Risk/Reward
        else:
            # Check exit conditions
            if row['Low'] <= sl:
                pnl = (sl - entry_price) / entry_price
                trades.append(pnl)
                in_trade = False
            elif row['High'] >= tp:
                pnl = (tp - entry_price) / entry_price
                trades.append(pnl)
                in_trade = False
                
    if len(trades) == 0:
        return 0.0, 0.0, 0
    
    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t <= 0]
    
    win_rate = (len(wins) / len(trades)) * 100
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 1e-9
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else gross_profit
    
    return round(win_rate, 1), round(profit_factor, 2), len(trades)

# ---------------------------------------------------------
# STREAMLIT UI & WORKFLOW
# ---------------------------------------------------------

st.title("📈 BIST Quant v50.0 - Algoritmik Tarama & SMC Paneli")
st.caption("Smart Money Concepts (SMC), Dinamik Skorlama ve Backtest Motoru Destekli Analiz Arayüzü")

# Sidebar
st.sidebar.header("⚙️ Tarama Parametreleri")

selected_stocks = st.sidebar.multiselect(
    "Taranacak Hisseleri Seçin:",
    options=DEFAULT_STOCKS + ["THYAO.IS", "GARAN.IS", "ASELS.IS", "BIMAS.IS", "AKBNK.IS", "TUPRS.IS"],
    default=DEFAULT_STOCKS[:10]
)

custom_symbol = st.sidebar.text_input("Ekstra Hisse Ekle (Örn: PGSUS.IS):")
if custom_symbol:
    symbol_formatted = custom_symbol.upper() if custom_symbol.endswith('.IS') else f"{custom_symbol.upper()}.IS"
    if symbol_formatted not in selected_stocks:
        selected_stocks.append(symbol_formatted)

years = st.sidebar.slider("Veri Geçmişi (Yıl):", min_value=1, max_value=5, value=2)
score_filter = st.sidebar.slider("Min. Sinyal Skoru Filtresi:", min_value=30, max_value=90, value=55)
atr_multiplier = st.sidebar.slider("ATR Stop Çarpanı:", min_value=1.0, max_value=3.0, value=1.5, step=0.1)

run_button = st.sidebar.button("🚀 Taramayı Başlat", type="primary", use_container_width=True)

# Caching Data Fetch
@st.cache_data(ttl=3600)
def load_stock_data(symbol, years_count):
    try:
        ticker = yf.Ticker(symbol)
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=years_count*365)
        df = ticker.history(start=start_date, end=end_date)
        if df.empty or len(df) < 50:
            return None
        return df
    except Exception:
        return None

if run_button or 'scan_results' in st.session_state:
    if run_button:
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, symbol in enumerate(selected_stocks):
            status_text.text(f"Analiz ediliyor ({idx+1}/{len(selected_stocks)}): {symbol}")
            df = load_stock_data(symbol, years)
            
            if df is not None:
                df = calculate_indicators(df)
                score, breakdown = compute_score(df)
                win_rate, profit_factor, trade_count = run_backtest(df, score_threshold=score_filter, atr_mult=atr_multiplier)
                
                last_row = df.iloc[-1]
                close_price = last_row['Close']
                atr = last_row['ATR'] if not np.isnan(last_row['ATR']) else close_price * 0.02
                
                stop_loss = round(close_price - (atr * atr_multiplier), 2)
                tp1 = round(close_price + (atr * atr_multiplier * 1.5), 2)
                tp2 = round(close_price + (atr * atr_multiplier * 2.5), 2)
                tp3 = round(close_price + (atr * atr_multiplier * 4.0), 2)
                
                # Signal Categorization
                if score >= 75:
                    signal = "🔥 Güçlü AL"
                elif score >= 55:
                    signal = "✅ AL"
                elif score <= 35:
                    signal = "🛑 SAT"
                else:
                    signal = "⏳ NÖTR"
                
                results.append({
                    "Hisse": symbol.replace(".IS", ""),
                    "Sinyal": signal,
                    "Skor": score,
                    "Fiyat (TL)": round(close_price, 2),
                    "RSI": round(last_row['RSI'], 1),
                    "Stop Loss": stop_loss,
                    "TP1 (Hedef 1)": tp1,
                    "TP2 (Hedef 2)": tp2,
                    "TP3 (Hedef 3)": tp3,
                    "WinRate (%)": win_rate,
                    "Profit Factor": profit_factor,
                    "İşlem Sayısı": trade_count,
                    "df": df
                })
            
            progress_bar.progress((idx + 1) / len(selected_stocks))
            
        status_text.text("Tarama tamamlandı!")
        st.session_state['scan_results'] = results

    results = st.session_state.get('scan_results', [])
    
    if results:
        df_res = pd.DataFrame(results)
        
        # Upper Metrics Dashboard
        st.subheader("📊 Genel Tarama Özeti")
        col1, col2, col3, col4 = st.columns(4)
        
        strong_buys = len(df_res[df_res['Skor'] >= 75])
        buys = len(df_res[(df_res['Skor'] >= 55) & (df_res['Skor'] < 75)])
        avg_wr = round(df_res['WinRate (%)'].mean(), 1)
        top_scorer = df_res.sort_values(by="Skor", ascending=False).iloc[0]['Hisse'] if len(df_res) > 0 else "-"
        
        col1.metric("🔥 Güçlü AL Sinyalleri", strong_buys)
        col2.metric("✅ AL Sinyalleri", buys)
        col3.metric("🎯 Ort. Backtest WinRate", f"%{avg_wr}")
        col4.metric("👑 En Yüksek Skorlu Hisse", top_scorer)
        
        st.divider()
        
        # Filtered Table Display
        st.subheader("📋 Tarama Sonuçları Tablosu")
        
        # Display Columns
        display_cols = ["Hisse", "Sinyal", "Skor", "Fiyat (TL)", "RSI", "Stop Loss", "TP1 (Hedef 1)", "TP2 (Hedef 2)", "WinRate (%)", "Profit Factor"]
        filtered_df = df_res[df_res['Skor'] >= score_filter][display_cols].sort_values(by="Skor", ascending=False)
        
        def highlight_signal(val):
            if "Güçlü AL" in str(val):
                return 'background-color: #1e4620; color: #4caf50; font-weight: bold;'
            elif "AL" in str(val):
                return 'background-color: #0d381e; color: #81c784;'
            elif "SAT" in str(val):
                return 'background-color: #4a1212; color: #e57373;'
            return ''

        st.dataframe(
            filtered_df.style.applymap(highlight_signal, subset=['Sinyal']),
            use_container_width=True,
            height=350
        )
        
        # Detailed Single Stock Chart View
        st.divider()
        st.subheader("🔍 Detaylı Grafikler ve SMC Görünümü")
        
        stock_list = filtered_df['Hisse'].tolist() if not filtered_df.empty else df_res['Hisse'].tolist()
        if stock_list:
            selected_stock = st.selectbox("İncelemek İçin Hisse Seçin:", stock_list)
            
            stock_data = next((item for item in results if item["Hisse"] == selected_stock), None)
            
            if stock_data:
                df_stock = stock_data['df']
                
                # Charting using Plotly
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                
                # Candlestick
                fig.add_trace(go.Candlestick(
                    x=df_stock.index,
                    open=df_stock['Open'],
                    high=df_stock['High'],
                    low=df_stock['Low'],
                    close=df_stock['Close'],
                    name='Fiyat'
                ), row=1, col=1)
                
                # EMAs
                fig.add_trace(go.Scatter(x=df_stock.index, y=df_stock['EMA_20'], line=dict(color='orange', width=1), name='EMA 20'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df_stock.index, y=df_stock['EMA_50'], line=dict(color='blue', width=1), name='EMA 50'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df_stock.index, y=df_stock['EMA_200'], line=dict(color='purple', width=1.5), name='EMA 200'), row=1, col=1)
                
                # RSI
                fig.add_trace(go.Scatter(x=df_stock.index, y=df_stock['RSI'], line=dict(color='cyan', width=1.5), name='RSI (14)'), row=2, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
                
                fig.update_layout(
                    title=f"{selected_stock} Technical & SMC Chart",
                    template="plotly_dark",
                    height=600,
                    xaxis_rangeslider_visible=False
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Metric Breakdown for Selected Stock
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Dinamik Skor", stock_data['Skor'])
                c2.metric("Stop Loss", f"{stock_data['Stop Loss']} TL")
                c3.metric("Kâr Al (TP1)", f"{stock_data['TP1 (Hedef 1)']} TL")
                c4.metric("Kâr Al (TP3)", f"{stock_data['TP3 (Hedef 3)']} TL")

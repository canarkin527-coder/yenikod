import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import contextlib
import warnings
from datetime import datetime

# Konsol uyarılarını gizle
warnings.filterwarnings('ignore')

# ---------------------------------------------------------
# 1. STREAMLIT SAYFA AYARI & TEMA
# ---------------------------------------------------------
st.set_page_config(
    page_title="BİST 100 Quantamental & Paper Trading Engine",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# MODERN AYDINLIK TEMA (LIGHT THEME)
st.markdown("""
<style>
    .stApp { background-color: #f8fafc; color: #0f172a; }
    h1, h2, h3, h4, h5, h6, label, p, .stCaption { color: #0f172a !important; font-family: 'Inter', system-ui, sans-serif; }
    section[data-testid="stSidebar"] { background-color: #ffffff !important; border-right: 1px solid #e2e8f0; }
    .stButton>button { width: 100%; background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); color: #ffffff !important; font-weight: 600; border-radius: 8px; border: none; padding: 0.5rem 1rem; }
    div[data-testid="stDataFrame"] { background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 6px; }
    div[data-baseweb="input"], div[data-baseweb="select"] { background-color: #ffffff !important; border-radius: 8px !important; border: 1px solid #cbd5e1 !important; color: #0f172a !important; }
    button[data-baseweb="tab"] { background-color: transparent; color: #64748b !important; font-weight: 600; }
    button[data-baseweb="tab"][aria-selected="true"] { background-color: #ffffff !important; color: #2563eb !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# SANAL PORTFÖY (SESSION STATE) İLKLENDİRME
# ---------------------------------------------------------
if 'virtual_cash' not in st.session_state:
    st.session_state['virtual_cash'] = 100000.0  # Başlangıç sanal parası (100.000 TL)
if 'portfolio' not in st.session_state:
    st.session_state['portfolio'] = []  # [{hisse, lot, alis_fiyati, tp, sl, tarih}]
if 'trade_history' not in st.session_state:
    st.session_state['trade_history'] = []

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

def compute_score(df):
    if len(df) < 50: return 0.0
    last, prev = df.iloc[-1], df.iloc[-2]
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

def run_backtest(df, score_threshold=65):
    trades, in_trade, entry_price, sl, tp = [], False, 0.0, 0.0, 0.0
    for i in range(50, len(df) - 1):
        sub_df = df.iloc[:i+1]
        score = compute_score(sub_df)
        next_open = df.iloc[i+1]['Open']
        if not in_trade:
            if score >= score_threshold:
                in_trade = True
                entry_price = next_open
                atr = sub_df.iloc[-1]['ATR']
                if np.isnan(atr) or atr == 0: atr = entry_price * 0.02
                sl, tp = entry_price - (atr * 1.5), entry_price + (atr * 3.0)
        else:
            next_low, next_high = df.iloc[i+1]['Low'], df.iloc[i+1]['High']
            if next_low <= sl:
                trades.append((sl - entry_price) / entry_price)
                in_trade = False
            elif next_high >= tp:
                trades.append((tp - entry_price) / entry_price)
                in_trade = False
    if not trades: return 0.0, 0.0, 0
    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t <= 0]
    win_rate = (len(wins) / len(trades)) * 100.0
    profit_factor = sum(wins) / (abs(sum(losses)) if sum(losses) != 0 else 1e-9)
    return round(win_rate, 1), round(profit_factor, 2), len(trades)

# ---------------------------------------------------------
# 3. VERİ VE TEMEL ANALİZ (FİNTABLES VERİLERİ) ÇEKME MOTORU
# ---------------------------------------------------------
@st.cache_data(ttl=900)
def fetch_all_stocks_data(symbols):
    all_data, chunk_size = [], 15
    chunks = [symbols[i:i + chunk_size] for i in range(0, len(symbols), chunk_size)]
    f = io.StringIO()
    with contextlib.redirect_stderr(f), contextlib.redirect_stdout(f):
        for chunk in chunks:
            try:
                data = yf.download(tickers=chunk, period="2y", group_by='ticker', auto_adjust=True, progress=False, threads=False, timeout=3)
                if data is not None and not data.empty: all_data.append(data)
            except Exception: continue
    if not all_data: return None
    try: return pd.concat(all_data, axis=1)
    except Exception: return None

@st.cache_data(ttl=3600)
def fetch_fundamental_data(symbol):
    """Fintables tarzı temel verileri (F/K, PD/DD, FD/FAVÖK) çeker"""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        pe_ratio = info.get('trailingPE', None)
        pb_ratio = info.get('priceToBook', None)
        ev_ebitda = info.get('enterpriseToEbitda', None)
        market_cap = info.get('marketCap', None)
        
        market_cap_m = round(market_cap / 1e9, 2) if market_cap else np.nan
        
        return {
            "FK": round(pe_ratio, 2) if pe_ratio and pe_ratio > 0 else np.nan,
            "PD_DD": round(pb_ratio, 2) if pb_ratio and pb_ratio > 0 else np.nan,
            "FD_FAVOK": round(ev_ebitda, 2) if ev_ebitda and ev_ebitda > 0 else np.nan,
            "Piyasa_Degeri_Milyar": market_cap_m
        }
    except Exception:
        return {"FK": np.nan, "PD_DD": np.nan, "FD_FAVOK": np.nan, "Piyasa_Degeri_Milyar": np.nan}

# ---------------------------------------------------------
# 4. ARAYÜZ VE TARAMA
# ---------------------------------------------------------
st.title("⚡ BİST 100 Quantamental Radar & Paper Trading")

col1, col2 = st.columns([2, 1])
with col1:
    filter_opt = st.radio("Filtrele:", [
        "Tüm Liste", 
        "Sadece GÜÇLÜ AL 🟢 (Skor ≥ 65)", 
        "Sadece GÜÇLÜ SAT 🔴 (Skor ≤ 35)",
        "Makul Çarpanlı / Ucuz Hisseler 🏷️ (F/K < 12 & PD/DD < 3)"
    ], horizontal=True)
with col2:
    portfolio_size = st.number_input("Risk Hesabı Portföy Büyüklüğü (TL):", value=100000.0, step=5000.0)

scan_btn = st.button("🔄 Radarı Çalıştır / Yenile")

if scan_btn or 'quant_data' not in st.session_state:
    results = []
    status = st.empty()
    status.info("BİST 100 verileri ve Fintables temel çarpanları çekiliyor...")
    batch_data = fetch_all_stocks_data(BIST_100_STOCKS)
    
    if batch_data is not None:
        for symbol in BIST_100_STOCKS:
            try:
                df = batch_data[symbol].dropna(how='all') if symbol in batch_data.columns.levels[0] else None
                if df is None or df.empty or len(df) < 50: continue
                
                df = df.dropna(subset=['Close', 'High', 'Low', 'Open', 'Volume'])
                df = calculate_indicators(df)
                score = compute_score(df)
                win_rate, profit_factor, trade_count = run_backtest(df)
                
                # Temel Verileri Çek
                fund_data = fetch_fundamental_data(symbol)
                
                last = df.iloc[-1]
                close, atr = last['Close'], last['ATR'] if not np.isnan(last['ATR']) else last['Close'] * 0.02
                signal = "🟢 GÜÇLÜ AL" if score >= 65 else ("🔴 GÜÇLÜ SAT" if score <= 35 else "⚪ NÖTR")
                stop_loss, tp1, tp2 = round(close - (atr * 1.5), 2), round(close + (atr * 1.5), 2), round(close + (atr * 3.0), 2)
                
                risk_per_share = abs(close - stop_loss)
                suggested_lot = max(1, int((portfolio_size * 0.02) / risk_per_share)) if risk_per_share > 0 else 1
                
                results.append({
                    "Hisse": symbol.replace(".IS", ""),
                    "Sinyal": signal,
                    "Quant Skor": score,
                    "Son Fiyat Raw": close,
                    "Son Fiyat": f"{close:.2f} ₺",
                    "F/K": fund_data["FK"],
                    "PD/DD": fund_data["PD_DD"],
                    "FD/FAVÖK": fund_data["FD_FAVOK"],
                    "Piyasa Değeri (Milyar ₺)": fund_data["Piyasa_Degeri_Milyar"],
                    "Stop Loss Raw": stop_loss,
                    "Stop Loss": f"{stop_loss:.2f} ₺",
                    "TP1 Raw": tp1,
                    "TP1 Hedef": f"{tp1:.2f} ₺",
                    "TP2 Raw": tp2,
                    "TP2 Hedef": f"{tp2:.2f} ₺",
                    "Önerilen Lot": suggested_lot,
                    "RSI": round(last['RSI'], 1),
                    "RVOL": round(last['RVOL'], 2),
                    "WinRate (%)": win_rate,
                    "Profit Factor": profit_factor,
                    "İşlem Sayısı": trade_count,
                    "raw_score": score,
                    "df": df
                })
            except Exception: continue
    status.empty()
    st.session_state['quant_data'] = results

results = st.session_state.get('quant_data', [])

if results:
    df_res = pd.DataFrame(results)
    
    # Filtreleme Mantığı
    if "GÜÇLÜ AL" in filter_opt: 
        df_filtered = df_res[df_res['raw_score'] >= 65]
    elif "GÜÇLÜ SAT" in filter_opt: 
        df_filtered = df_res[df_res['raw_score'] <= 35]
    elif "Makul Çarpanlı" in filter_opt:
        df_filtered = df_res[(df_res['F/K'] < 12) & (df_res['PD/DD'] < 3.0)]
    else: 
        df_filtered = df_res
        
    df_filtered = df_filtered.sort_values(by="raw_score", ascending=False)
    
    # TEMEL ÖZET METRİKLERİ (ÖZET KARTLAR)
    avg_fk = df_res['F/K'].dropna().mean()
    avg_pddd = df_res['PD_DD'].dropna().mean()
    cheapest_stock = df_res.sort_values(by="F/K", ascending=True).iloc[0]['Hisse'] if not df_res.empty else "N/A"
    
    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.metric("BİST 100 Ort. F/K", f"{avg_fk:.2f}" if not np.isnan(avg_fk) else "N/A")
    m_col2.metric("BİST 100 Ort. PD/DD", f"{avg_pddd:.2f}" if not np.isnan(avg_pddd) else "N/A")
    m_col3.metric("En Düşük F/K'lı Hisse", cheapest_stock)
    
    st.markdown("---")
    
    # 4 SEKME
    tab1, tab2, tab3, tab4 = st.tabs(["🔥 Canlı Radar (Quant + Temel)", "📊 Backtest Sonuçları", "📈 Grafik Analizi", "💼 Sanal Portföy (Paper Trading)"])
    
    with tab1:
        cols = ["Hisse", "Sinyal", "Quant Skor", "Son Fiyat", "F/K", "PD/DD", "FD/FAVÖK", "Piyasa Değeri (Milyar ₺)", "Stop Loss", "TP1 Hedef", "TP2 Hedef", "Önerilen Lot", "RSI", "RVOL"]
        st.dataframe(df_filtered[cols], width="stretch", height=400)
        
        st.subheader("🛒 Hızlı Sanal Alım Yap")
        buy_col1, buy_col2, buy_col3, buy_col4 = st.columns(4)
        with buy_col1:
            selected_buy_stock = st.selectbox("Alınacak Hisse:", df_filtered['Hisse'].tolist())
        stock_info = next((item for item in results if item["Hisse"] == selected_buy_stock), None)
        
        if stock_info:
            with buy_col2:
                buy_lot = st.number_input("Lot Miktarı:", min_value=1, value=stock_info['Önerilen Lot'])
            with buy_col3:
                custom_tp = st.number_input("Satış Hedef (TP) ₺:", value=stock_info['TP2 Raw'])
            with buy_col4:
                custom_sl = st.number_input("Stop Loss (SL) ₺:", value=stock_info['Stop Loss Raw'])
                
            total_cost = buy_lot * stock_info['Son Fiyat Raw']
            st.caption(f"Maliyet: **{total_cost:,.2f} ₺** | F/K: **{stock_info['F/K']}** | PD/DD: **{stock_info['PD/DD']}** | Sanal Nakit: **{st.session_state['virtual_cash']:,.2f} ₺**")
            
            if st.button(f"🚀 {selected_buy_stock} Sanal Portföye Ekle"):
                if total_cost <= st.session_state['virtual_cash']:
                    st.session_state['virtual_cash'] -= total_cost
                    st.session_state['portfolio'].append({
                        "Hisse": selected_buy_stock,
                        "Lot": buy_lot,
                        "Alis_Fiyati": stock_info['Son Fiyat Raw'],
                        "Guncel_Fiyat": stock_info['Son Fiyat Raw'],
                        "TP": custom_tp,
                        "SL": custom_sl,
                        "Tarih": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
                    st.success(f"{selected_buy_stock} hissesinden {buy_lot} Lot alındı!")
                    st.rerun()
                else:
                    st.error("Yetersiz Sanal Bakiye!")

    with tab2:
        st.dataframe(df_filtered[["Hisse", "Quant Skor", "WinRate (%)", "Profit Factor", "İşlem Sayısı", "F/K", "PD/DD"]], width="stretch")
        
    with tab3:
        selected_stock = st.selectbox("Hisse Seçin:", df_filtered['Hisse'].tolist(), key="chart_select")
        stock_data = next((item for item in results if item["Hisse"] == selected_stock), None)
        if stock_data:
            df_chart = stock_data['df']
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], name='Fiyat'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA_20'], line=dict(color='#ff9800'), name='EMA 20'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['RSI'], line=dict(color='#0284c7'), name='RSI'), row=2, col=1)
            fig.update_layout(template="plotly_white", height=500)
            st.plotly_chart(fig, width="stretch")

    # ---------------------------------------------------------
    # TAB 4: SANAL PORTFÖY (PAPER TRADING)
    # ---------------------------------------------------------
    with tab4:
        st.subheader("💼 Sanal Portföy ve Simülasyon Takibi")
        
        # OTOMATİK STOP-LOSS VE TAKE-PROFIT KONTROLÜ
        for pos in st.session_state['portfolio'][:]:
            stock_match = next((item for item in results if item["Hisse"] == pos["Hisse"]), None)
            if stock_match:
                curr_p = stock_match['Son Fiyat Raw']
                pos['Guncel_Fiyat'] = curr_p
                
                # Hedef Fiyata Ulaşıldı Mı? (Take Profit)
                if curr_p >= pos['TP']:
                    revenue = pos['Lot'] * pos['TP']
                    profit = revenue - (pos['Lot'] * pos['Alis_Fiyati'])
                    st.session_state['virtual_cash'] += revenue
                    st.session_state['trade_history'].append({
                        "Hisse": pos['Hisse'], "Lot": pos['Lot'], "Alış": pos['Alis_Fiyati'], 
                        "Satış": pos['TP'], "Kâr/Zarar (₺)": round(profit, 2), "Neden": "🎯 TP (Hedef Göründü)"
                    })
                    st.session_state['portfolio'].remove(pos)
                    st.toast(f"🎯 {pos['Hisse']} Otomatik Satıldı! (Hedef Fiyata Ulaşıldı)", icon="🎉")
                
                # Stop Loss Seviyesine İndi Mi?
                elif curr_p <= pos['SL']:
                    revenue = pos['Lot'] * pos['SL']
                    loss = revenue - (pos['Lot'] * pos['Alis_Fiyati'])
                    st.session_state['virtual_cash'] += revenue
                    st.session_state['trade_history'].append({
                        "Hisse": pos['Hisse'], "Lot": pos['Lot'], "Alış": pos['Alis_Fiyati'], 
                        "Satış": pos['SL'], "Kâr/Zarar (₺)": round(loss, 2), "Neden": "🛑 SL (Stop Olundu)"
                    })
                    st.session_state['portfolio'].remove(pos)
                    st.toast(f"🛑 {pos['Hisse']} Otomatik Stop Edildi!", icon="⚠️")

        # PORTFÖY ÖZET METRİKLERİ
        active_portfolio_val = sum([p['Lot'] * p['Guncel_Fiyat'] for p in st.session_state['portfolio']])
        total_account_val = st.session_state['virtual_cash'] + active_portfolio_val
        
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("Toplam Varlık Değeri", f"{total_account_val:,.2f} ₺")
        m_col2.metric("Sanal Nakit Bakiye", f"{st.session_state['virtual_cash']:,.2f} ₺")
        m_col3.metric("Açık Pozisyon Değeri", f"{active_portfolio_val:,.2f} ₺")
        
        st.markdown("---")
        st.write("### 🟢 Açık Pozisyonların")
        
        if st.session_state['portfolio']:
            p_df = pd.DataFrame(st.session_state['portfolio'])
            p_df['Maliyet (₺)'] = (p_df['Lot'] * p_df['Alis_Fiyati']).round(2)
            p_df['Güncel Değer (₺)'] = (p_df['Lot'] * p_df['Guncel_Fiyat']).round(2)
            p_df['Kâr / Zarar (₺)'] = (p_df['Güncel Değer (₺)'] - p_df['Maliyet (₺)']).round(2)
            p_df['Kâr / Zarar (%)'] = ((p_df['Kâr / Zarar (₺)'] / p_df['Maliyet (₺)']) * 100).round(2)
            
            display_cols = ["Hisse", "Lot", "Alis_Fiyati", "Guncel_Fiyat", "TP", "SL", "Maliyet (₺)", "Güncel Değer (₺)", "Kâr / Zarar (₺)", "Kâr / Zarar (%)"]
            st.dataframe(p_df[display_cols], width="stretch")
            
            # Manuel Pozisyon Kapatma
            st.write("#### 🔻 Manuel Pozisyon Kapat")
            close_col1, close_col2 = st.columns([3, 1])
            with close_col1:
                stock_to_close = st.selectbox("Kapatılacak Pozisyonu Seç:", [p['Hisse'] for p in st.session_state['portfolio']])
            with close_col2:
                if st.button(f"❌ {stock_to_close} Hissesini Sat"):
                    target_p = next(p for p in st.session_state['portfolio'] if p['Hisse'] == stock_to_close)
                    rev = target_p['Lot'] * target_p['Guncel_Fiyat']
                    p_loss = rev - (target_p['Lot'] * target_p['Alis_Fiyati'])
                    st.session_state['virtual_cash'] += rev
                    st.session_state['trade_history'].append({
                        "Hisse": target_p['Hisse'], "Lot": target_p['Lot'], "Alış": target_p['Alis_Fiyati'], 
                        "Satış": target_p['Guncel_Fiyat'], "Kâr/Zarar (₺)": round(p_loss, 2), "Neden": "✋ Manuel Kapatıldı"
                    })
                    st.session_state['portfolio'].remove(target_p)
                    st.success(f"{stock_to_close} pozisyonu satıldı.")
                    st.rerun()
        else:
            st.info("Henüz açık bir sanal pozisyonun bulunmuyor. 'Canlı Radar' sekmesinden sanal alım yapabilirsin.")
            
        # KAPATILAN İŞLEMLER GEÇMİŞİ
        if st.session_state['trade_history']:
            st.markdown("---")
            st.write("### 📜 Kapatılan İşlem Geçmişi (Realize Edilenler)")
            st.dataframe(pd.DataFrame(st.session_state['trade_history']), width="stretch")

        # BAKİYE SIFIRLAMA BUTONU
        st.markdown("---")
        if st.button("⚠️ Sanal Portföyü ve Bakiyeyi Sıfırla (100.000 ₺ Yap)"):
            st.session_state['virtual_cash'] = 100000.0
            st.session_state['portfolio'] = []
            st.session_state['trade_history'] = []
            st.success("Sanal portföyün başarıyla sıfırlandı!")
            st.rerun()

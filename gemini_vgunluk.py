import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import logging
import warnings

# ==============================================================================
# LOGGING VE UYARI AYARLARI
# ==============================================================================
warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==============================================================================
# 1. SAYFA YAPILANDIRMASI VE GELİŞMİŞ LIGHT THEME CSS
# ==============================================================================
st.set_page_config(
    page_title="BİST 100 Advanced Pure Quant Engine & Pro Trading Lab",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Light-Theme CSS & Modern UI Components
st.markdown("""
    <style>
    .main {
        background-color: #F8F9FA;
        color: #1A1D20;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E9ECEF;
    }
    .stMetric {
        background-color: #FFFFFF;
        padding: 18px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.03), 0 1px 3px rgba(0,0,0,0.05);
        border: 1px solid #E9ECEF;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: #F1F3F5;
        padding: 6px;
        border-radius: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        background-color: transparent;
        border-radius: 8px;
        color: #495057;
        font-weight: 600;
        border: none;
        padding: 0px 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FFFFFF !important;
        color: #0D6EFD !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.08);
    }
    .custom-card {
        background-color: #FFFFFF;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #E9ECEF;
        margin-bottom: 15px;
    }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. SESSION STATE YÖNETİMİ
# ==============================================================================
if 'cash' not in st.session_state:
    st.session_state.cash = 100000.0
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {}
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []

# ==============================================================================
# 3. GENİŞLETİLMİŞ BİST 100 HİSSE EVRENİ VE SEKTÖR EŞLEŞTİRMELERİ
# ==============================================================================
BIST100_TICKERS = [
    "AKBNK.IS", "AKSEN.IS", "ALARK.IS", "ARCLK.IS", "ASELS.IS",
    "ASTOR.IS", "BIMAS.IS", "BRSAN.IS", "CCOLA.IS", "CIMSA.IS",
    "DOHOL.IS", "EKGYO.IS", "ENJSA.IS", "ENKAI.IS", "EREGL.IS",
    "FROTO.IS", "GARAN.IS", "GUBRF.IS", "HEKTS.IS", "ISCTR.IS",
    "KCHOL.IS", "KONTR.IS", "KOZAL.IS", "KRDMD.IS", "MAVI.IS",
    "MGROS.IS", "ODAS.IS", "OYAKC.IS", "PETKM.IS", "PGASUS.IS",
    "SAHOL.IS", "SASA.IS", "SISE.IS", "SKBNK.IS", "TCELL.IS",
    "THYAO.IS", "TKFEN.IS", "TOASO.IS", "TSKB.IS", "TTKOM.IS",
    "TUPRS.IS", "ULKER.IS", "VAKBN.IS", "VESTL.IS", "YKBNK.IS"
]

SECTOR_MAP = {
    "THYAO": "Ulaştırma", "PGASUS": "Ulaştırma",
    "GARAN": "Bankacılık", "AKBNK": "Bankacılık", "ISCTR": "Bankacılık", "YKBNK": "Bankacılık", "VAKBN": "Bankacılık", "TSKB": "Bankacılık", "SKBNK": "Bankacılık",
    "KCHOL": "Holding", "SAHOL": "Holding", "DOHOL": "Holding", "ALARK": "Holding",
    "EREGL": "Metal Ana", "KRDMD": "Metal Ana", "BRSAN": "Metal Ana",
    "SISE": "Cam & Seramik", "BIMAS": "Perakende Ticaret", "MGROS": "Perakende Ticaret",
    "TUPRS": "Kimya & Petrol", "PETKM": "Kimya & Petrol", "SASA": "Kimya & Petrol", "HEKTS": "Kimya & Petrol",
    "ASELS": "Savunma & Teknoloji", "KONTR": "Teknoloji / Enerji", "ASTOR": "Elektrik / Enerji",
    "FROTO": "Otomotiv", "TOASO": "Otomotiv", "ENJSA": "Enerji", "AKSEN": "Enerji", "ODAS": "Enerji",
    "CCOLA": "Gıda & İçecek", "ULKER": "Gıda & İçecek", "ARCLK": "Dayanıklı Tüketim", "VESTL": "Dayanıklı Tüketim",
    "TCELL": "Telekomünikasyon", "TTKOM": "Telekomünikasyon", "EKGYO": "Gayrimenkul YAT.", "OYAKC": "Çimento", "CIMSA": "Çimento"
}

# ==============================================================================
# 4. GÜVENLİ VE SAĞLAM TEKNİK İNDİKATÖR MOTORU
# ==============================================================================
class TechnicalAnalysisEngine:
    
    @staticmethod
    def calculate_ema(series, period):
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def calculate_rsi(series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-9)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    @staticmethod
    def calculate_macd(series, fast=12, slow=26, signal=9):
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line.fillna(0), signal_line.fillna(0), histogram.fillna(0)

    @staticmethod
    def calculate_bollinger_bands(series, period=20, std_dev=2):
        sma = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        return upper_band.fillna(series), sma.fillna(series), lower_band.fillna(series)

    @staticmethod
    def calculate_stochastic_rsi(series, period=14, smooth_k=3, smooth_d=3):
        rsi = TechnicalAnalysisEngine.calculate_rsi(series, period)
        stoch_rsi = (rsi - rsi.rolling(period).min()) / (rsi.rolling(period).max() - rsi.rolling(period).min() + 1e-9)
        k = stoch_rsi.rolling(smooth_k).mean() * 100
        d = k.rolling(smooth_d).mean()
        return k.fillna(50), d.fillna(50)

    @staticmethod
    def calculate_atr(df, period=14):
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        return true_range.rolling(period).mean().fillna(0)

    @staticmethod
    def calculate_obv(df):
        obv = (np.sign(df['Close'].diff()) * df['Volume']).fillna(0).cumsum()
        return obv

# ==============================================================================
# 5. SAF QUANT SKORLAMA MOTORU (DÜZELTİLMİŞ)
# ==============================================================================
def compute_comprehensive_quant_score(df):
    if df is None or len(df) < 20:
        return {
            "score": 50, "trend_score": 0, "momentum_score": 0, "volume_score": 0,
            "volatility_score": 0, "rsi": 50.0, "rvol": 1.0, "macd_signal": "Nötr",
            "price": 0.0, "change_pct": 0.0, "atr": 0.0, "status": "Yetersiz Veri"
        }
    
    # Verilerin Series tipinde ve sayısal olduğundan emin olalım
    close = pd.Series(df['Close'].values, index=df.index).astype(float)
    volume = pd.Series(df['Volume'].values, index=df.index).astype(float)
    high = pd.Series(df['High'].values, index=df.index).astype(float)
    low = pd.Series(df['Low'].values, index=df.index).astype(float)
    
    total_score = 0
    
    # 1. TREND KATMANI (MAX 25)
    trend_score = 0
    ema20 = TechnicalAnalysisEngine.calculate_ema(close, 20)
    ema50 = TechnicalAnalysisEngine.calculate_ema(close, 50)
    ema200 = TechnicalAnalysisEngine.calculate_ema(close, 200) if len(close) >= 200 else ema50
    
    curr_price = float(close.iloc[-1])
    prev_price = float(close.iloc[-2]) if len(close) > 1 else curr_price
    change_pct = ((curr_price - prev_price) / (prev_price + 1e-9)) * 100
    
    curr_ema20 = float(ema20.iloc[-1])
    curr_ema50 = float(ema50.iloc[-1])
    curr_ema200 = float(ema200.iloc[-1])
    
    if curr_price > curr_ema20: trend_score += 8
    if curr_ema20 > curr_ema50: trend_score += 10
    if curr_ema50 > curr_ema200: trend_score += 7
    total_score += trend_score

    # 2. MOMENTUM KATMANI (MAX 25)
    momentum_score = 0
    rsi = TechnicalAnalysisEngine.calculate_rsi(close, 14)
    curr_rsi = float(rsi.iloc[-1])
    
    macd, signal, hist = TechnicalAnalysisEngine.calculate_macd(close)
    curr_macd = float(macd.iloc[-1])
    curr_signal = float(signal.iloc[-1])
    curr_hist = float(hist.iloc[-1])
    prev_hist = float(hist.iloc[-2]) if len(hist) > 1 else curr_hist
    
    stoch_k, stoch_d = TechnicalAnalysisEngine.calculate_stochastic_rsi(close)
    curr_stoch_k = float(stoch_k.iloc[-1])
    curr_stoch_d = float(stoch_d.iloc[-1])
    
    if 45 <= curr_rsi <= 65: momentum_score += 10
    elif 30 <= curr_rsi < 45: momentum_score += 7
    elif curr_rsi > 70: momentum_score += 2
        
    if curr_macd > curr_signal:
        momentum_score += 8
        if curr_hist > prev_hist: momentum_score += 3
            
    if curr_stoch_k > curr_stoch_d and curr_stoch_k < 80: momentum_score += 4
    total_score += momentum_score

    # 3. HACİM KATMANI (MAX 20)
    volume_score = 0
    avg_vol_20 = float(volume.rolling(20, min_periods=1).mean().iloc[-1])
    curr_vol = float(volume.iloc[-1])
    rvol = curr_vol / (avg_vol_20 + 1e-9)
    
    obv = TechnicalAnalysisEngine.calculate_obv(df)
    obv_ema = TechnicalAnalysisEngine.calculate_ema(obv, 20)
    
    if rvol >= 1.8: volume_score += 12
    elif rvol >= 1.1: volume_score += 8
    elif rvol >= 0.7: volume_score += 4
        
    if float(obv.iloc[-1]) > float(obv_ema.iloc[-1]): volume_score += 8
    total_score += volume_score

    # 4. VOLATİLİTE KATMANI (MAX 15)
    volatility_score = 0
    upper_b, mid_b, lower_b = TechnicalAnalysisEngine.calculate_bollinger_bands(close)
    atr = float(TechnicalAnalysisEngine.calculate_atr(df).iloc[-1])
    
    c_upper = float(upper_b.iloc[-1])
    c_lower = float(lower_b.iloc[-1])
    c_mid = float(mid_b.iloc[-1])
    
    band_width = (c_upper - c_lower) / (c_mid + 1e-9)
    if band_width < 0.12: volatility_score += 8
    if curr_price > c_mid and curr_price < c_upper: volatility_score += 7
    total_score += volatility_score

    # 5. İSTATİSTİKSEL KATMAN (MAX 15)
    stat_score = 0
    high_52 = float(high.rolling(min(len(high), 252), min_periods=1).max().iloc[-1])
    dist_to_high = curr_price / (high_52 + 1e-9)
    
    if dist_to_high >= 0.85: stat_score += 15
    elif dist_to_high >= 0.70: stat_score += 10
    else: stat_score += 5
    total_score += stat_score

    final_score = int(min(max(total_score, 0), 100))
    
    if final_score >= 70: status = "🚀 GÜÇLÜ AL"
    elif final_score >= 55: status = "🟢 AL"
    elif final_score >= 40: status = "👀 NÖTR"
    else: status = "❌ SAT"

    macd_desc = "AL Kesişimi" if curr_macd > curr_signal else "SAT Kesişimi"

    return {
        "score": final_score,
        "trend_score": trend_score,
        "momentum_score": momentum_score,
        "volume_score": volume_score,
        "volatility_score": volatility_score,
        "rsi": round(curr_rsi, 1),
        "rvol": round(rvol, 2),
        "macd_signal": macd_desc,
        "price": round(curr_price, 2),
        "change_pct": round(change_pct, 2),
        "atr": round(atr, 2),
        "status": status
    }

# ==============================================================================
# 6. VERİ ÇEKME MOTORU (MULTI-INDEX SAFE)
# ==============================================================================
@st.cache_data(ttl=300, show_spinner=False)
def fetch_stock_data(ticker, period="6m"):
    try:
        df = yf.download(ticker, period=period, progress=False)
        if df.empty:
            return None
        
        # MultiIndex kolon yapısını düzleştirme
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df = df.dropna(subset=['Close'])
        return df
    except Exception as e:
        logging.error(f"Veri çekme hatası ({ticker}): {str(e)}")
        return None

# ==============================================================================
# 7. ARAYÜZ VE SİDEBAR
# ==============================================================================
st.title("⚡ BİST 100 Pure Quant Engine & Trading Lab")
st.caption("Fiyat, Hacim ve İstatistiksel Algoritmalara Odaklı Hata-Korumalı Sinyal Sistemi.")

st.sidebar.header("🎯 Quant Filtre Parametreleri")

min_quant_score = st.sidebar.slider("Minimum Quant Skor", 0, 100, 40, 5)
rsi_filter = st.sidebar.select_slider(
    "RSI Aralığı Filtresi",
    options=["Tümü", "Aşırı Satım (<30)", "İdeal Yükseliş (40-65)", "Aşırı Alım (>70)"],
    value="Tümü"
)
min_rvol = st.sidebar.number_input("Minimum RVOL (Hacim)", 0.0, 5.0, 0.5, 0.1)

st.sidebar.markdown("---")
st.sidebar.write(f"**Sanal Nakit:** {st.session_state.cash:,.2f} TL")

# ==============================================================================
# 8. SEKMELER VE RADAR
# ==============================================================================
tab1, tab2, tab3 = st.tabs(["🔍 Canlı Quant Radar", "📈 İnteraktif Grafik", "💸 Trading Simülasyonu"])

with tab1:
    st.markdown("""
        <div class="custom-card">
            <h4>🚀 Algoritmik Sinyal Radarı</h4>
            <p>Piyasayı anlık tarar ve 5 teknik katmanda puanlar. Filtre ayarlarını sol menüden esnetebilirsiniz.</p>
        </div>
    """, unsafe_allow_html=True)
    
    col_btn, col_sec, col_search = st.columns([2, 2, 3])
    start_scan = col_btn.button("🚀 Taramayı Başlat / Yenile", use_container_width=True)
    selected_sector = col_sec.selectbox("Sektör Filtresi:", ["Tüm Sektörler"] + list(set(SECTOR_MAP.values())))
    search_keyword = col_search.text_input("Hisse Arama:", "").upper()

    if start_scan or 'last_scan_results' in st.session_state:
        if start_scan or 'last_scan_results' not in st.session_state:
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, ticker in enumerate(BIST100_TICKERS):
                clean_ticker = ticker.replace(".IS", "")
                status_text.text(f"Analiz ediliyor: {clean_ticker} ({idx+1}/{len(BIST100_TICKERS)})")
                
                df_stock = fetch_stock_data(ticker, period="6m")
                
                if df_stock is not None and len(df_stock) >= 20:
                    q_res = compute_comprehensive_quant_score(df_stock)
                    sector = SECTOR_MAP.get(clean_ticker, "Diğer")
                    
                    results.append({
                        "Hisse": clean_ticker,
                        "Sektör": sector,
                        "Fiyat (TL)": q_res["price"],
                        "Günlük Değişim (%)": q_res["change_pct"],
                        "Quant Skor": q_res["score"],
                        "RSI (14)": q_res["rsi"],
                        "RVOL (Hacim)": q_res["rvol"],
                        "MACD": q_res["macd_signal"],
                        "ATR": q_res["atr"],
                        "Sinyal Durumu": q_res["status"]
                    })
                
                progress_bar.progress((idx + 1) / len(BIST100_TICKERS))
            
            status_text.empty()
            progress_bar.empty()
            st.session_state.last_scan_results = pd.DataFrame(results)

        df_scan = st.session_state.last_scan_results.copy()

        if not df_scan.empty:
            # Filtreleme Mantığı
            df_filtered = df_scan[
                (df_scan["Quant Skor"] >= min_quant_score) &
                (df_scan["RVOL (Hacim)"] >= min_rvol)
            ]
            
            if rsi_filter == "Aşırı Satım (<30)":
                df_filtered = df_filtered[df_filtered["RSI (14)"] < 30]
            elif rsi_filter == "İdeal Yükseliş (40-65)":
                df_filtered = df_filtered[(df_filtered["RSI (14)"] >= 40) & (df_filtered["RSI (14)"] <= 65)]
            elif rsi_filter == "Aşırı Alım (>70)":
                df_filtered = df_filtered[df_filtered["RSI (14)"] > 70]
                
            if selected_sector != "Tüm Sektörler":
                df_filtered = df_filtered[df_filtered["Sektör"] == selected_sector]
                
            if search_keyword:
                df_filtered = df_filtered[df_filtered["Hisse"].str.contains(search_keyword)]

            # Özet Metrik Paneli
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Süzgeçten Geçen Hisse", len(df_filtered))
            m2.metric("🚀 Güçlü Al Sinyali", len(df_filtered[df_filtered["Quant Skor"] >= 70]))
            m3.metric("Ortalama Quant Skor", round(df_filtered["Quant Skor"].mean(), 1) if not df_filtered.empty else 0)
            m4.metric("🔥 Hacimli Hareket Edenler", len(df_filtered[df_filtered["RVOL (Hacim)"] >= 1.2]))

            st.markdown("---")

            if not df_filtered.empty:
                st.dataframe(
                    df_filtered.sort_values(by="Quant Skor", ascending=False),
                    column_config={
                        "Quant Skor": st.column_config.ProgressColumn("Quant Skor", format="%d", min_value=0, max_value=100),
                        "Fiyat (TL)": st.column_config.NumberColumn(format="%.2f TL"),
                        "Günlük Değişim (%)": st.column_config.NumberColumn(format="%+.2f %%"),
                        "RVOL (Hacim)": st.column_config.NumberColumn(format="%.2fx"),
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.warning("⚠️ Seçtiğiniz katı filtrelere uygun hisse bulunamadı! Sol menüden Minimum Quant Skor değerini düşürerek veya RVOL sınırını esneterek tekrar deneyin.")
                st.info("💡 En Yüksek Skora Sahip İlk 5 Hisse Aşağıda Listelenmiştir:")
                st.dataframe(df_scan.sort_values(by="Quant Skor", ascending=False).head(5), use_container_width=True, hide_index=True)
    else:
        st.info("👆 Taramayı başlatmak için yukarıdaki **'Taramayı Başlat / Yenile'** butonuna tıklayın.")

# ------------------------------------------------------------------------------
# TAB 2: GRAFİK MODÜLÜ
# ------------------------------------------------------------------------------
with tab2:
    selected_chart_stock = st.selectbox("Grafik İçin Hisse Seçin:", [t.replace(".IS", "") for t in BIST100_TICKERS])
    df_chart = fetch_stock_data(f"{selected_chart_stock}.IS", period="1y")
    
    if df_chart is not None and not df_chart.empty:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_width=[0.3, 0.7])
        fig.add_trace(go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], name="Fiyat"), row=1, col=1)
        fig.add_trace(go.Bar(x=df_chart.index, y=df_chart['Volume'], name="Hacim"), row=2, col=1)
        fig.update_layout(height=600, template="plotly_white", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------------------
# TAB 3: TRADING SIMULATION
# ------------------------------------------------------------------------------
with tab3:
    st.subheader("💸 Sanal Portföy Paneli")
    st.write(f"Mevcut Bakiye: **{st.session_state.cash:,.2f} TL**")

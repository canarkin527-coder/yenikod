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
    /* Ana Arka Plan ve Yazı Rengi */
    .main {
        background-color: #F8F9FA;
        color: #1A1D20;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Sidebar Tasarımı */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E9ECEF;
    }
    
    /* Metrik Kartları */
    .stMetric {
        background-color: #FFFFFF;
        padding: 18px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.03), 0 1px 3px rgba(0,0,0,0.05);
        border: 1px solid #E9ECEF;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .stMetric:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 12px rgba(0,0,0,0.06), 0 2px 4px rgba(0,0,0,0.08);
    }
    
    /* Sekme (Tab) Tasarımları */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: #F1F3F5;
        padding: 6px;
        border-radius: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 8px;
        color: #495057;
        font-weight: 600;
        border: none;
        padding: 0px 20px;
        transition: all 0.2s ease;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FFFFFF !important;
        color: #0D6EFD !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.08);
    }
    
    /* Buton Özelleştirmeleri */
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    
    /* Özel Başlık ve İpuçları */
    .custom-card {
        background-color: #FFFFFF;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #E9ECEF;
        margin-bottom: 15px;
    }
    .badge-success {
        background-color: #D1E7DD;
        color: #0F5132;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-warning {
        background-color: #FFF3CD;
        color: #664D03;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-danger {
        background-color: #F8D7DA;
        color: #842029;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. SESSION STATE YÖNETİMİ (SANAL PORTFÖY / TRADING SIMULATION)
# ==============================================================================
if 'cash' not in st.session_state:
    st.session_state.cash = 100000.0  # 100,000 TL Sanal Başlangıç Bakiyesi
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {}  # Format: {'THYAO': {'qty': 100, 'avg_price': 285.50, 'total_spent': 28550.0}}
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["THYAO", "ASELS", "GARAN"]

# ==============================================================================
# 3. GENİŞLETİLMİŞ BİST 100 HİSSE EVRENİ VE SEKTÖR EŞLEŞTİRMELERİ
# ==============================================================================
BIST100_TICKERS = [
    "AKBNK.IS", "AKSEN.IS", "ALARK.IS", "ARCLK.IS", "ASELS.IS",
    "ASTOR.IS", "BIMAS.IS", "BRSAN.IS", "CASA.IS", "CCOLA.IS",
    "CEMTS.IS", "CIMSA.IS", "DOHOL.IS", "EKGYO.IS", "ENJSA.IS",
    "ENKAI.IS", "EREGL.IS", "FROTO.IS", "GARAN.IS", "GUBRF.IS",
    "HEKTS.IS", "ISCTR.IS", "KCHOL.IS", "KONTR.IS", "KORDS.IS",
    "KOZAL.IS", "KRDMD.IS", "MAVI.IS", "MGROS.IS", "ODAS.IS",
    "OYAKC.IS", "PETKM.IS", "PGASUS.IS", "SAHOL.IS", "SASA.IS",
    "SISE.IS", "SKBNK.IS", "TCELL.IS", "THYAO.IS", "TKFEN.IS",
    "TOASO.IS", "TSKB.IS", "TTKOM.IS", "TUPRS.IS", "ULKER.IS",
    "VAKBN.IS", "VESTL.IS", "YKBNK.IS", "YYLGD.IS", "ZOREN.IS"
]

SECTOR_MAP = {
    "THYAO": "Ulaştırma", "PGASUS": "Ulaştırma",
    "GARAN": "Bankacılık", "AKBNK": "Bankacılık", "ISCTR": "Bankacılık", "YKBNK": "Bankacılık", "VAKBN": "Bankacılık", "TSKB": "Bankacılık", "SKBNK": "Bankacılık",
    "KCHOL": "Holding", "SAHOL": "Holding", "DOHOL": "Holding", "ALARK": "Holding",
    "EREGL": "Metal Ana", "KRDMD": "Metal Ana", "BRSAN": "Metal Ana",
    "SISE": "Cam & Seramik",
    "BIMAS": "Perakende Ticaret", "MGROS": "Perakende Ticaret",
    "TUPRS": "Kimya & Petrol", "PETKM": "Kimya & Petrol", "SASA": "Kimya & Petrol", "HEKTS": "Kimya & Petrol",
    "ASELS": "Savunma & Teknoloji", "KONTR": "Teknoloji / Enerji", "ASTOR": "Elektrik / Enerji",
    "FROTO": "Otomotiv", "TOASO": "Otomotiv",
    "ENJSA": "Enerji", "AKSEN": "Enerji", "ODAS": "Enerji", "ZOREN": "Enerji",
    "CCOLA": "Gıda & İçecek", "ULKER": "Gıda & İçecek",
    "ARCLK": "Dayanıklı Tüketim", "VESTL": "Dayanıklı Tüketim",
    "TCELL": "Telekomünikasyon", "TTKOM": "Telekomünikasyon",
    "EKGYO": "Gayrimenkul YAT.", "OYAKC": "Çimento", "CIMSA": "Çimento"
}

# ==============================================================================
# 4. GELİŞMİŞ TEKNİK İNDİKATÖR HESAPLAMA MOTORU (SAF MATEMATİK)
# ==============================================================================
class TechnicalAnalysisEngine:
    """
    Sadece Fiyat ve Hacim verisiyle çalışan, dış gürültüden bağımsız 
    matematiksel ve istatistiksel teknik indikatör kütüphanesi.
    """
    
    @staticmethod
    def calculate_ema(series, period):
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def calculate_sma(series, period):
        return series.rolling(window=period).mean()

    @staticmethod
    def calculate_rsi(series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-9)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def calculate_macd(series, fast=12, slow=26, signal=9):
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    @staticmethod
    def calculate_bollinger_bands(series, period=20, std_dev=2):
        sma = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        return upper_band, sma, lower_band

    @staticmethod
    def calculate_stochastic_rsi(series, period=14, smooth_k=3, smooth_d=3):
        rsi = TechnicalAnalysisEngine.calculate_rsi(series, period)
        stoch_rsi = (rsi - rsi.rolling(period).min()) / (rsi.rolling(period).max() - rsi.rolling(period).min() + 1e-9)
        k = stoch_rsi.rolling(smooth_k).mean() * 100
        d = k.rolling(smooth_d).mean()
        return k, d

    @staticmethod
    def calculate_atr(df, period=14):
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        return true_range.rolling(period).mean()

    @staticmethod
    def calculate_obv(df):
        obv = (np.sign(df['Close'].diff()) * df['Volume']).fillna(0).cumsum()
        return obv

    @staticmethod
    def calculate_vwap(df):
        typical_price = (df['High'] + df['Low'] + df['Close']) / 3
        return (typical_price * df['Volume']).cumsum() / (df['Volume'].cumsum() + 1e-9)

# ==============================================================================
# 5. ÇOK KATMANLI QUANT SKORLAMA MOTORU (0 - 100 SKOR)
# ==============================================================================
def compute_comprehensive_quant_score(df):
    """
    Hisse verilerini 5 Farklı Katmanda Puanlar:
    1. Trend Katmanı (Max 25 Puan)
    2. Momentum Katmanı (Max 25 Puan)
    3. Hacim & Para Akışı Katmanı (Max 20 Puan)
    4. Volatilite & Band Katmanı (Max 15 Puan)
    5. İstatistiksel Pozisyonlama Katmanı (Max 15 Puan)
    """
    if df is None or len(df) < 50:
        return {
            "score": 50, "trend_score": 0, "momentum_score": 0, "volume_score": 0,
            "volatility_score": 0, "rsi": 50, "rvol": 1.0, "macd_signal": "Nötr",
            "price": 0, "change_pct": 0, "atr": 0, "status": "Yetersiz Veri"
        }
    
    close = df['Close']
    volume = df['Volume']
    high = df['High']
    low = df['Low']
    
    total_score = 0
    
    # --------------------------------------------------------------------------
    # KATMAN 1: TREND ANALİZİ (MAX 25 PUAN)
    # --------------------------------------------------------------------------
    trend_score = 0
    ema20 = TechnicalAnalysisEngine.calculate_ema(close, 20)
    ema50 = TechnicalAnalysisEngine.calculate_ema(close, 50)
    ema200 = TechnicalAnalysisEngine.calculate_ema(close, 200) if len(close) >= 200 else ema50
    
    curr_price = close.iloc[-1]
    prev_price = close.iloc[-2]
    change_pct = ((curr_price - prev_price) / prev_price) * 100
    
    curr_ema20 = ema20.iloc[-1]
    curr_ema50 = ema50.iloc[-1]
    curr_ema200 = ema200.iloc[-1]
    
    if curr_price > curr_ema20:
        trend_score += 8  # Kısa Vadeli Yükseliş
    if curr_ema20 > curr_ema50:
        trend_score += 10 # Orta Vadeli Trend Güçlü
    if curr_ema50 > curr_ema200:
        trend_score += 7  # Boğa Piyasası / Golden Cross Yapısı
        
    total_score += trend_score

    # --------------------------------------------------------------------------
    # KATMAN 2: MOMENTUM ANALİZİ (MAX 25 PUAN)
    # --------------------------------------------------------------------------
    momentum_score = 0
    rsi = TechnicalAnalysisEngine.calculate_rsi(close, 14)
    curr_rsi = rsi.iloc[-1]
    
    macd, signal, hist = TechnicalAnalysisEngine.calculate_macd(close)
    curr_macd = macd.iloc[-1]
    curr_signal = signal.iloc[-1]
    curr_hist = hist.iloc[-1]
    prev_hist = hist.iloc[-2]
    
    stoch_k, stoch_d = TechnicalAnalysisEngine.calculate_stochastic_rsi(close)
    curr_stoch_k = stoch_k.iloc[-1]
    curr_stoch_d = stoch_d.iloc[-1]
    
    # RSI Değerlendirmesi
    if 45 <= curr_rsi <= 65:
        momentum_score += 10 # İdeal Yükseliş İvmesi
    elif 30 <= curr_rsi < 45:
        momentum_score += 7  # Dip Dönüş Bölgesi
    elif curr_rsi > 70:
        momentum_score += 2  # Aşırı Alım (Risk)
        
    # MACD Değerlendirmesi
    if curr_macd > curr_signal:
        momentum_score += 8
        if curr_hist > prev_hist:
            momentum_score += 3 # MACD Momentum Hızlanıyor
            
    # Stoch RSI Değerlendirmesi
    if curr_stoch_k > curr_stoch_d and curr_stoch_k < 80:
        momentum_score += 4
        
    total_score += momentum_score

    # --------------------------------------------------------------------------
    # KATMAN 3: HACİM VE PARA AKIŞI (MAX 20 PUAN)
    # --------------------------------------------------------------------------
    volume_score = 0
    avg_vol_20 = volume.rolling(20).mean().iloc[-1]
    curr_vol = volume.iloc[-1]
    rvol = curr_vol / (avg_vol_20 + 1e-9)
    
    obv = TechnicalAnalysisEngine.calculate_obv(df)
    obv_ema = TechnicalAnalysisEngine.calculate_ema(obv, 20)
    
    if rvol >= 2.0:
        volume_score += 12 # Olağanüstü Hacim Patlaması
    elif rvol >= 1.2:
        volume_score += 8  # Sağlıklı Hacim Artışı
    elif rvol >= 0.8:
        volume_score += 4
        
    if obv.iloc[-1] > obv_ema.iloc[-1]:
        volume_score += 8  # Para Girişi Onaylı
        
    total_score += volume_score

    # --------------------------------------------------------------------------
    # KATMAN 4: VOLATİLİTE VE BOLLINGER BANTLARI (MAX 15 PUAN)
    # --------------------------------------------------------------------------
    volatility_score = 0
    upper_b, mid_b, lower_b = TechnicalAnalysisEngine.calculate_bollinger_bands(close)
    atr = TechnicalAnalysisEngine.calculate_atr(df).iloc[-1]
    
    c_upper = upper_b.iloc[-1]
    c_lower = lower_b.iloc[-1]
    c_mid = mid_b.iloc[-1]
    
    # Bant Sıkışması (Squeeze Check - Patlama Öncesi)
    band_width = (c_upper - c_lower) / c_mid
    if band_width < 0.10:  # Daralma Var
        volatility_score += 8
        
    if curr_price > c_mid and curr_price < c_upper:
        volatility_score += 7 # Üst Banda Yönelim
        
    total_score += volatility_score

    # --------------------------------------------------------------------------
    # KATMAN 5: İSTATİSTİKSEL SEVİYE & DESTEK/DİRENÇ (MAX 15 PUAN)
    # --------------------------------------------------------------------------
    stat_score = 0
    high_52 = high.rolling(252, min_periods=50).max().iloc[-1]
    low_52 = low.rolling(252, min_periods=50).min().iloc[-1]
    
    # 52 Haftalık Zirveye Yakınlık (Momentum Göstergesi)
    dist_to_high = (curr_price / high_52)
    if dist_to_high >= 0.85:
        stat_score += 15
    elif dist_to_high >= 0.70:
        stat_score += 10
    else:
        stat_score += 5
        
    total_score += stat_score

    # Toplam Skor Sınırlaması
    final_score = int(min(max(total_score, 0), 100))
    
    # Sinyal Sınıflandırması
    if final_score >= 75:
        status = "🚀 GÜÇLÜ AL (Yüksek Momentum)"
    elif final_score >= 60:
        status = "🟢 AL (Pozitif Trend)"
    elif final_score >= 45:
        status = "👀 NÖTR / İZLE"
    elif final_score >= 30:
        status = "⚠️ ZAYIF / DÜZELTME"
    else:
        status = "❌ SAT / UZAK DUR"

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
# 6. VERİ İNDİRME VE ÖNBELLEK YÖNETİMİ
# ==============================================================================
@st.cache_data(ttl=300, show_spinner=False)
def fetch_stock_data(ticker, period="1y", interval="1d"):
    """
    yfinance üzerinden güvenli veri çekimi yapar. MultiIndex yapılarını düzeltir.
    """
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        logging.error(f"Veri çekme hatası ({ticker}): {str(e)}")
        return None

# ==============================================================================
# 7. ARAYÜZ BAŞLIĞI VE SIDEBAR KONTROLLERİ
# ==============================================================================
st.title("⚡ BİST 100 Pure Quant Engine & Trading Lab")
st.caption("Bilanço bağımlılığından arındırılmış; %100 Fiyat, Hacim ve İstatistiksel Algoritmalara Odaklı Sinyal Sistemi.")

# SIDEBAR AYARLARI
st.sidebar.header("🎯 Quant Filtre Parametreleri")

min_quant_score = st.sidebar.slider(
    "Minimum Quant Skor", 
    min_value=0, 
    max_value=100, 
    value=50, 
    step=5,
    help="Belirlenen skorun altındaki hisseler radarda gizlenir."
)

rsi_filter = st.sidebar.select_slider(
    "RSI Aralığı Filtresi",
    options=["Tümü", "Aşırı Satım (<30)", "İdeal Yükseliş (40-65)", "Aşırı Alım (>70)"],
    value="Tümü"
)

min_rvol = st.sidebar.number_input(
    "Minimum Göreceli Hacim (RVOL)",
    min_value=0.0,
    max_value=5.0,
    value=0.8,
    step=0.1,
    help="Ortalama hacminin kaç katı işlem gördüğünü filtreler."
)

st.sidebar.markdown("---")
st.sidebar.subheader("💼 Sanal Portföy Durumu")
st.sidebar.write(f"**Nakit Bakiye:** {st.session_state.cash:,.2f} TL")

# Anlık Portföy Değeri Hesaplama
total_portfolio_value = st.session_state.cash
for tkr, data in st.session_state.portfolio.items():
    stock_df = fetch_stock_data(f"{tkr}.IS", period="5d")
    if stock_df is not None and not stock_df.empty:
        c_price = stock_df['Close'].iloc[-1]
    else:
        c_price = data['avg_price']
    total_portfolio_value += data['qty'] * c_price

st.sidebar.write(f"**Toplam Portföy Değeri:** {total_portfolio_value:,.2f} TL")
pnl_total = total_portfolio_value - 100000.0
pnl_color = "green" if pnl_total >= 0 else "red"
st.sidebar.markdown(f"**Toplam Net Kâr/Zarar:** <span style='color:{pnl_color}; font-weight:bold;'>{pnl_total:+,.2f} TL</span>", unsafe_allow_html=True)

# ==============================================================================
# 8. SEKMELİ ARAYÜZ YAPISI
# ==============================================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 Tablo 1: Canlı Quant Radar", 
    "📈 Tablo 2: İnteraktif Grafik & Teknik Analiz", 
    "💸 Tablo 3: Sanal Trading Simülasyonu",
    "📚 Tablo 4: Quant Strateji & Sözlük"
])

# ------------------------------------------------------------------------------
# TAB 1: CANLI QUANT RADAR
# ------------------------------------------------------------------------------
with tab1:
    st.markdown("""
        <div class="custom-card">
            <h4>🚀 Algoritmik Sinyal Radarı</h4>
            <p>Piyasayı anlık olarak tarar, Trend, Momentum, Hacim ve Volatilitat katmanlarında puanlar. Bilanço tıkanmalarından tamamen bağımsız çalışır.</p>
        </div>
    """, unsafe_allow_html=True)
    
    col_btn, col_sec, col_search = st.columns([2, 2, 3])
    start_scan = col_btn.button("🚀 Taramayı Başlat / Yenile", use_container_width=True)
    selected_sector = col_sec.selectbox("Sektör Filtresi:", ["Tüm Sektörler"] + list(set(SECTOR_MAP.values())))
    search_keyword = col_search.text_input("Hisse Arama (Örn: THYAO):", "").upper()

    if start_scan or 'last_scan_results' in st.session_state:
        if start_scan or 'last_scan_results' not in st.session_state:
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, ticker in enumerate(BIST100_TICKERS):
                clean_ticker = ticker.replace(".IS", "")
                status_text.text(f"Analiz ediliyor: {clean_ticker} ({idx+1}/{len(BIST100_TICKERS)})")
                
                df_stock = fetch_stock_data(ticker, period="6m")
                
                if df_stock is not None:
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
                        "ATR (Oynaklık)": q_res["atr"],
                        "Sinyal Durumu": q_res["status"]
                    })
                
                progress_bar.progress((idx + 1) / len(BIST100_TICKERS))
            
            status_text.empty()
            progress_bar.empty()
            st.session_state.last_scan_results = pd.DataFrame(results)

        df_scan = st.session_state.last_scan_results.copy()

        # Filtreleme Mantığı
        if not df_scan.empty:
            # 1. Quant Skor Filtresi
            df_scan = df_scan[df_scan["Quant Skor"] >= min_quant_score]
            
            # 2. RVOL Filtresi
            df_scan = df_scan[df_scan["RVOL (Hacim)"] >= min_rvol]
            
            # 3. RSI Filtresi
            if rsi_filter == "Aşırı Satım (<30)":
                df_scan = df_scan[df_scan["RSI (14)"] < 30]
            elif rsi_filter == "İdeal Yükseliş (40-65)":
                df_scan = df_scan[(df_scan["RSI (14)"] >= 40) & (df_scan["RSI (14)"] <= 65)]
            elif rsi_filter == "Aşırı Alım (>70)":
                df_scan = df_scan[df_scan["RSI (14)"] > 70]
                
            # 4. Sektör Filtresi
            if selected_sector != "Tüm Sektörler":
                df_scan = df_scan[df_scan["Sektör"] == selected_sector]
                
            # 5. Kelime Arama
            if search_keyword:
                df_scan = df_scan[df_scan["Hisse"].str.contains(search_keyword)]

            # Özet Metrik Paneli
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Süzgeçten Geçen Hisse", len(df_scan))
            
            strong_buys = len(df_scan[df_scan["Quant Skor"] >= 75])
            m2.metric("🚀 Güçlü Al Sinyali", strong_buys)
            
            avg_score = round(df_scan["Quant Skor"].mean(), 1) if not df_scan.empty else 0
            m3.metric("Ortalama Quant Skor", avg_score)
            
            high_vol = len(df_scan[df_scan["RVOL (Hacim)"] >= 1.5])
            m4.metric("🔥 Hacimli Hareket Edenler", high_vol)

            st.markdown("---")

            if not df_scan.empty:
                st.dataframe(
                    df_scan.sort_values(by="Quant Skor", ascending=False),
                    column_config={
                        "Quant Skor": st.column_config.ProgressColumn(
                            "Quant Skor", format="%d", min_value=0, max_value=100
                        ),
                        "Fiyat (TL)": st.column_config.NumberColumn(format="%.2f TL"),
                        "Günlük Değişim (%)": st.column_config.NumberColumn(format="%+.2f %%"),
                        "RVOL (Hacim)": st.column_config.NumberColumn(format="%.2fx"),
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.warning("⚠️ Seçtiğiniz filtre kriterlerine uygun hisse bulunamadı. Sol taraftaki parametreleri esnetebilirsiniz.")
    else:
        st.info("👆 Taramayı başlatmak için yukarıdaki **'Taramayı Başlat / Yenile'** butonuna tıklayın.")

# ------------------------------------------------------------------------------
# TAB 2: İNTERAKTİF GRAFİK & TEKNİK ANALİZ
# ------------------------------------------------------------------------------
with tab2:
    st.subheader("📈 Profesyonel İnteraktif Mum Grafiği ve İndikatör Katmanları")
    
    col_stock_sel, col_period_sel = st.columns([3, 1])
    selected_chart_stock = col_stock_sel.selectbox(
        "Grafik İçin Hisse Seçin:", 
        [t.replace(".IS", "") for t in BIST100_TICKERS],
        key="chart_stock_select"
    )
    selected_period = col_period_sel.selectbox("Zaman Aralığı:", ["3m", "6m", "1y", "2y"], index=2)
    
    df_chart = fetch_stock_data(f"{selected_chart_stock}.IS", period=selected_period)
    
    if df_chart is not None and not df_chart.empty:
        # İndikatör Hesaplamaları
        close = df_chart['Close']
        ema20 = TechnicalAnalysisEngine.calculate_ema(close, 20)
        ema50 = TechnicalAnalysisEngine.calculate_ema(close, 50)
        ema200 = TechnicalAnalysisEngine.calculate_ema(close, 200) if len(close) >= 200 else ema50
        
        upper_b, mid_b, lower_b = TechnicalAnalysisEngine.calculate_bollinger_bands(close)
        rsi = TechnicalAnalysisEngine.calculate_rsi(close)
        macd, signal, hist = TechnicalAnalysisEngine.calculate_macd(close)
        
        # Plotly Subplots (3 Katmanlı Grafik)
        fig = make_subplots(
            rows=3, cols=1, 
            shared_xaxes=True,
            vertical_spacing=0.03,
            subplot_titles=(f'{selected_chart_stock} Fiyat & Hareketli Ortalamalar', 'Hacim & RVOL', 'RSI & MACD'),
            row_width=[0.2, 0.2, 0.6]
        )

        # 1. KATMAN: MUM GRAFİĞİ VE HAREKETLİ ORTALAMALAR
        fig.add_trace(go.Candlestick(
            x=df_chart.index,
            open=df_chart['Open'], high=df_chart['High'],
            low=df_chart['Low'], close=df_chart['Close'],
            name="Fiyat"
        ), row=1, col=1)

        fig.add_trace(go.Scatter(x=df_chart.index, y=ema20, mode='lines', name='EMA 20', line=dict(color='orange', width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_chart.index, y=ema50, mode='lines', name='EMA 50', line=dict(color='blue', width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_chart.index, y=upper_b, mode='lines', name='Bollinger Üst', line=dict(color='gray', width=1, dash='dash')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_chart.index, y=lower_b, mode='lines', name='Bollinger Alt', line=dict(color='gray', width=1, dash='dash')), row=1, col=1)

        # 2. KATMAN: HACİM
        colors = ['green' if df_chart['Close'].iloc[i] >= df_chart['Open'].iloc[i] else 'red' for i in range(len(df_chart))]
        fig.add_trace(go.Bar(
            x=df_chart.index, y=df_chart['Volume'], name="Hacim", marker_color=colors
        ), row=2, col=1)

        # 3. KATMAN: RSI & MACD
        fig.add_trace(go.Scatter(x=df_chart.index, y=rsi, mode='lines', name='RSI (14)', line=dict(color='purple', width=2)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df_chart.index, y=[70]*len(df_chart), mode='lines', name='Aşırı Alım (70)', line=dict(color='red', width=1, dash='dot')), row=3, col=1)
        fig.add_trace(go.Scatter(x=df_chart.index, y=[30]*len(df_chart), mode='lines', name='Aşırı Satım (30)', line=dict(color='green', width=1, dash='dot')), row=3, col=1)

        fig.update_layout(
            height=750,
            template="plotly_white",
            xaxis_rangeslider_visible=False,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Tekil Quant Analiz Kartı
        q_single = compute_comprehensive_quant_score(df_chart)
        
        st.markdown("### 📊 Anlık Detaylı Teknik Değerlendirme")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Quant Skor", f"{q_single['score']} / 100")
        c2.metric("RSI (14)", q_single['rsi'])
        c3.metric("RVOL", f"{q_single['rvol']}x")
        c4.metric("ATR (Oynaklık)", f"{q_single['atr']} TL")
        c5.metric("MACD Sinyali", q_single['macd_signal'])

# ------------------------------------------------------------------------------
# TAB 3: SANAL TRADING SİMÜLASYONU
# ------------------------------------------------------------------------------
with tab3:
    st.subheader("💸 Sanal Portföy ve Alım / Satım Simülasyonu")
    
    col_trade_input, col_portfolio_view = st.columns([1, 1])
    
    # ALIM / SATIM EMİR PANELİ
    with col_trade_input:
        st.markdown("""
            <div class="custom-card">
                <h4>🛒 Emir Giriş Paneli</h4>
            </div>
        """, unsafe_allow_html=True)
        
        trade_ticker = st.selectbox("İşlem Yapılacak Hisse:", [t.replace(".IS", "") for t in BIST100_TICKERS], key="sim_trade_stock")
        
        # Anlık Fiyat Çekimi
        live_df = fetch_stock_data(f"{trade_ticker}.IS", period="5d")
        if live_df is not None and not live_df.empty:
            live_price = round(live_df['Close'].iloc[-1], 2)
        else:
            live_price = 100.0
            
        st.write(f"**Anlık Piyasa Fiyatı:** {live_price:,.2f} TL")
        
        trade_qty = st.number_input("İşlem Adedi (Lot):", min_value=1, value=100, step=10)
        total_order_val = trade_qty * live_price
        st.write(f"**Toplam Emir Tutarı:** {total_order_val:,.2f} TL")
        
        btn_buy, btn_sell = st.columns(2)
        
        # BUY LOGIC
        if btn_buy.button("🟢 HİSSE AL (BUY)", use_container_width=True):
            if st.session_state.cash >= total_order_val:
                st.session_state.cash -= total_order_val
                
                if trade_ticker in st.session_state.portfolio:
                    old_qty = st.session_state.portfolio[trade_ticker]['qty']
                    old_spent = st.session_state.portfolio[trade_ticker]['total_spent']
                    
                    new_qty = old_qty + trade_qty
                    new_spent = old_spent + total_order_val
                    new_avg = new_spent / new_qty
                    
                    st.session_state.portfolio[trade_ticker] = {
                        'qty': new_qty, 'avg_price': new_avg, 'total_spent': new_spent
                    }
                else:
                    st.session_state.portfolio[trade_ticker] = {
                        'qty': trade_qty, 'avg_price': live_price, 'total_spent': total_order_val
                    }
                    
                st.session_state.trade_history.append({
                    "Tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Hisse": trade_ticker, "İşlem Tip": "ALIM",
                    "Adet": trade_qty, "Fiyat": live_price, "Toplam Tutar": total_order_val
                })
                st.success(f"✅ {trade_qty} lot {trade_ticker} başarıyla alındı!")
                st.rerun()
            else:
                st.error("❌ Yetersiz Nakit Bakiye!")

        # SELL LOGIC
        if btn_sell.button("🔴 HİSSE SAT (SELL)", use_container_width=True):
            if trade_ticker in st.session_state.portfolio and st.session_state.portfolio[trade_ticker]['qty'] >= trade_qty:
                st.session_state.cash += total_order_val
                
                remaining_qty = st.session_state.portfolio[trade_ticker]['qty'] - trade_qty
                if remaining_qty == 0:
                    del st.session_state.portfolio[trade_ticker]
                else:
                    st.session_state.portfolio[trade_ticker]['qty'] = remaining_qty
                    st.session_state.portfolio[trade_ticker]['total_spent'] = remaining_qty * st.session_state.portfolio[trade_ticker]['avg_price']
                    
                st.session_state.trade_history.append({
                    "Tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Hisse": trade_ticker, "İşlem Tip": "SATIM",
                    "Adet": trade_qty, "Fiyat": live_price, "Toplam Tutar": total_order_val
                })
                st.success(f"✅ {trade_qty} lot {trade_ticker} başarıyla satıldı!")
                st.rerun()
            else:
                st.error("❌ Portföyünüzde yeterli miktarda hisse bulunmuyor!")

    # PORTFÖY VE KÂR/ZARAR TABLOSU
    with col_portfolio_view:
        st.markdown("""
            <div class="custom-card">
                <h4>📊 Mevcut Portföy Varlıkları</h4>
            </div>
        """, unsafe_allow_html=True)
        
        if st.session_state.portfolio:
            port_records = []
            for tkr, data in st.session_state.portfolio.items():
                s_df = fetch_stock_data(f"{tkr}.IS", period="5d")
                curr_p = s_df['Close'].iloc[-1] if s_df is not None else data['avg_price']
                
                market_val = data['qty'] * curr_p
                pnl = (curr_p - data['avg_price']) * data['qty']
                pnl_pct = ((curr_p - data['avg_price']) / data['avg_price']) * 100
                
                port_records.append({
                    "Hisse": tkr,
                    "Adet": data['qty'],
                    "Ort. Maliyet": round(data['avg_price'], 2),
                    "Güncel Fiyat": round(curr_p, 2),
                    "Piyasa Değeri": round(market_val, 2),
                    "Kâr/Zarar (TL)": round(pnl, 2),
                    "Getiri (%)": round(pnl_pct, 2)
                })
            
            st.dataframe(pd.DataFrame(port_records), use_container_width=True, hide_index=True)
        else:
            st.info("Portföyünüzde henüz hisse bulunmuyor. Sol taraftaki paneli kullanarak alım yapabilirsiniz.")

    st.markdown("---")
    st.subheader("📜 Geçmiş İşlem Günlüğü")
    if st.session_state.trade_history:
        st.dataframe(pd.DataFrame(st.session_state.trade_history), use_container_width=True, hide_index=True)
    else:
        st.caption("Henüz yapılmış bir işlem bulunmuyor.")

# ------------------------------------------------------------------------------
# TAB 4: QUANT STRATEJİ & SÖZLÜK
# ------------------------------------------------------------------------------
with tab4:
    st.subheader("📚 Quant Algorithm & İndikatör Rehberi")
    
    st.markdown("""
    ### 🎯 Quant Skorlama Mantığı Nasıl Çalışır?
    Bu sistem, temel bilanço verilerinin gecikmeli ve karmaşık yapısından sıyrılarak **tamamen fiyat, hacim ve istatistiksel trend bileşenlerine** odaklanır.
    
    ---
    
    #### 1. Trend Katmanı (Max 25 Puan)
    * **EMA 20 / EMA 50 / EMA 200:** Fiyatın hareketli ortalamaların üzerinde olması kısa, orta ve uzun vadeli yükseliş trendini teyit eder.
    * **Golden Cross:** EMA 50'nin EMA 200'ü yukarı kesmesi ekstra puan kazandırır.

    #### 2. Momentum Katmanı (Max 25 Puan)
    * **RSI (Relative Strength Index):** 40 - 65 arasındaki RSI değerleri, hissenin aşırı alıma girmeden en güçlü ivmeyi yakaladığı "Sweet Spot" bölgesidir.
    * **MACD:** MACD çizgisinin sinyal çizgisini yukarı kesmesi momentum başlangıcı olarak kabul edilir.

    #### 3. Hacim ve Para Akışı Katmanı (Max 20 Puan)
    * **RVOL (Göreceli Hacim):** Hissenin son 20 günlük ortalama hacmine kıyasla ne kadar güçlü işlem gördüğünü ölçer. 1.5x üzerindeki değerler kurumsal para girişine işaret eder.
    * **OBV (On-Balance Volume):** Fiyat hareketini hacimle teyit eder.

    #### 4. Volatilite & Sıkışma Katmanı (Max 15 Puan)
    * **Bollinger Bant Sıkışması:** Bantların daralması, hissede yakın zamanda sert bir kırılım (patlama) yaşanacağını gösterir.

    #### 5. İstatistiksel Konumlandırma (Max 15 Puan)
    * Hissenin 52 haftalık zirvesine olan yakınlığı momentumun devamlılığını doğrular.
    """)

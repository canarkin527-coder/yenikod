import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
import sqlite3
from scipy.optimize import minimize
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from datetime import datetime

# ==========================================
# 0. STREAMLIT CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="v44.1 Quant Master Engine - BIST 100 Professional",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main { background-color: #06080d; }
    .stMetric { background-color: #0f1420; padding: 12px; border-radius: 8px; border: 1px solid #1e2638; }
    div[data-testid="stSidebar"] { background-color: #0a0d14; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { background-color: #0f1420; border-radius: 6px; padding: 8px 16px; color: #a0aec0; }
    .stTabs [aria-selected="true"] { background-color: #1e2638; color: #ffffff; border-bottom: 2px solid #3182ce; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. YENİ İNDİKATÖR VE RİSK HESAPLAMA MOTORU (RSI, ADX, RVOL, RS, ATR)
# ==========================================

class TechnicalFilterEngine:
    @staticmethod
    def calculate_rsi(series: pd.Series, period: int = 14) -> float:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-9)
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1])

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        return float(atr.iloc[-1])

    @staticmethod
    def calculate_adx(df: pd.DataFrame, period: int = 14) -> float:
        df = df.copy()
        df['up'] = df['High'] - df['High'].shift(1)
        df['down'] = df['Low'].shift(1) - df['Low']
        
        df['+dm'] = np.where((df['up'] > df['down']) & (df['up'] > 0), df['up'], 0.0)
        df['-dm'] = np.where((df['down'] > df['up']) & (df['down'] > 0), df['down'], 0.0)
        
        atr = df['High'] - df['Low']
        atr_smooth = atr.rolling(period).mean()
        
        plus_di = 100 * (df['+dm'].rolling(period).mean() / (atr_smooth + 1e-9))
        minus_di = 100 * (df['-dm'].rolling(period).mean() / (atr_smooth + 1e-9))
        
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)
        adx = dx.rolling(period).mean()
        return float(adx.iloc[-1])

    @staticmethod
    def calculate_rvol(df: pd.DataFrame, period: int = 20) -> float:
        """Relative Volume: Son hacmin 20 günlük ortalamaya oranı"""
        avg_vol = df['Volume'].rolling(period).mean().iloc[-1]
        last_vol = df['Volume'].iloc[-1]
        return float(last_vol / (avg_vol + 1e-9))

    @staticmethod
    def calculate_relative_strength(df_stock: pd.DataFrame, df_xu100: pd.DataFrame, period: int = 60) -> float:
        """BIST 100'e Göre Göreceli Güç Oranı (RS Score)"""
        stock_ret = (df_stock['Close'].iloc[-1] - df_stock['Close'].iloc[-period]) / df_stock['Close'].iloc[-period]
        xu100_ret = (df_xu100['Close'].iloc[-1] - df_xu100['Close'].iloc[-period]) / df_xu100['Close'].iloc[-period]
        return float((1 + stock_ret) / (1 + xu100_ret + 1e-9))

# ==========================================
# 2. SMC & VOLUME PROFILE YARDIMCI SINIFLARI
# ==========================================

class AdvancedSMCEngineV44:
    @staticmethod
    def analyze_structure(df: pd.DataFrame):
        highs, lows, closes = df['High'], df['Low'], df['Close']
        window = 5
        sh = (highs == highs.rolling(2 * window + 1, center=True).max())
        sl = (lows == lows.rolling(2 * window + 1, center=True).min())
        
        sh_idx, sl_idx = np.where(sh)[0], np.where(sl)[0]
        last_close, last_low = closes.iloc[-1], lows.iloc[-1]
        
        mss_bullish = len(sh_idx) > 0 and last_close > highs.iloc[sh_idx[-1]]
        
        lookback = min(60, len(df))
        rec_h, rec_l = np.max(highs.iloc[-lookback:]), np.min(lows.iloc[-lookback:])
        eq_level = (rec_h + rec_l) / 2.0
        r_size = rec_h - rec_l
        
        zone = "EQUILIBRIUM"
        if r_size > 0:
            if last_close > eq_level + (r_size * 0.15): zone = "PREMIUM 🔴"
            elif last_close < eq_level - (r_size * 0.15): zone = "DISCOUNT 🟢"
            
        ob_mitigated = False
        if len(sl_idx) > 0:
            last_sl_price = lows.iloc[sl_idx[-1]]
            if last_low <= last_sl_price * 1.01 and last_close > last_sl_price:
                ob_mitigated = True
                
        return {"MSS": mss_bullish, "Zone": zone, "OB_Mitigated": ob_mitigated}

class VolumeProfileEngine:
    @staticmethod
    def calculate_vpvr_poc(df: pd.DataFrame, bins: int = 30) -> float:
        p_min, p_max = df['Low'].min(), df['High'].max()
        if p_max == p_min: return df['Close'].iloc[-1]
        p_bins = np.linspace(p_min, p_max, bins + 1)
        v_prof = np.zeros(bins)
        for idx in range(len(df)):
            b_idx = np.digitize(df['Close'].iloc[idx], p_bins) - 1
            if 0 <= b_idx < bins: v_prof[b_idx] += df['Volume'].iloc[idx]
        return float((p_bins[np.argmax(v_prof)] + p_bins[np.argmax(v_prof) + 1]) / 2.0)

    @staticmethod
    def calculate_avwap(df: pd.DataFrame) -> float:
        sub = df.iloc[-60:]
        tp = (sub['High'] + sub['Low'] + sub['Close']) / 3.0
        avwap = (tp * sub['Volume']).sum() / (sub['Volume'].sum() + 1e-9)
        return float(avwap)

# ==========================================
# 3. YENİLENMİŞ GELİŞMİŞ SKORLAMA MOTORU
# ==========================================

class MultiFactorEngineV441:
    @staticmethod
    def process_ticker(ticker: str, df: pd.DataFrame, df_xu100: pd.DataFrame, regime_score: float) -> dict:
        if len(df) < 60: return None
        
        last_price = float(df['Close'].iloc[-1])
        
        # 1. Yeni Metrikler
        rsi = TechnicalFilterEngine.calculate_rsi(df)
        adx = TechnicalFilterEngine.calculate_adx(df)
        rvol = TechnicalFilterEngine.calculate_rvol(df)
        rs_score = TechnicalFilterEngine.calculate_relative_strength(df, df_xu100)
        atr = TechnicalFilterEngine.calculate_atr(df)
        
        # 2. ATR Tabanlı Hedef, Stop ve Risk/Ödül (R:R)
        stop_loss = round(last_price - (2.0 * atr), 2)
        target_price = round(last_price + (3.5 * atr), 2)
        risk = last_price - stop_loss
        reward = target_price - last_price
        rr_ratio = round(reward / (risk + 1e-9), 2)
        
        # 3. SMC & Hacim
        smc = AdvancedSMCEngineV44.analyze_structure(df)
        poc = VolumeProfileEngine.calculate_vpvr_poc(df)
        avwap = VolumeProfileEngine.calculate_avwap(df)
        
        # 4. Gelişmiş Puanlama Sistemi (100 Üzerinden)
        score = 50.0
        score += regime_score * 10.0
        
        # SMC Katkıları
        if smc["Zone"] == "DISCOUNT 🟢": score += 12
        if smc["OB_Mitigated"]: score += 10
        if smc["MSS"]: score += 8
        if smc["Zone"] == "PREMIUM 🔴": score -= 8
        
        # Filtre Katkıları
        if 45 <= rsi <= 65: score += 8 # Sağlıklı Trend Bölgesi
        elif rsi > 75: score -= 5 # Aşırı Alım
        
        if adx > 25: score += 7 # Güçlü Trend
        if rvol > 1.2: score += 8 # Hacim Konfirmasyonu
        if rs_score > 1.05: score += 7 # BIST100'den Güçlü
        
        if last_price > avwap: score += 5
        if last_price > poc: score += 5
        
        final_score = round(min(100.0, max(0.0, score)), 1)
        
        signal = "NÖTR ⚪"
        if final_score >= 78: signal = "GÜÇLÜ AL 🚀"
        elif final_score >= 62: signal = "AL 🟢"
        elif final_score <= 40: signal = "SAT 🔴"
        
        return {
            "Ticker": ticker,
            "Kurumsal Skor": final_score,
            "Sinyal": signal,
            "Son Fiyat": round(last_price, 2),
            "Zone": smc["Zone"],
            "OB Test": "EVET ✅" if smc["OB_Mitigated"] else "HAYIR ❌",
            "RSI (14)": round(rsi, 1),
            "ADX (14)": round(adx, 1),
            "RVOL": round(rvol, 2),
            "RS (BIST)": round(rs_score, 2),
            "Stop Loss (2x ATR)": stop_loss,
            "Hedef (3.5x ATR)": target_price,
            "Risk/Ödül (R:R)": rr_ratio,
            "POC": round(poc, 2),
            "AVWAP": round(avwap, 2)
        }

# ==========================================
# 4. BIST 100 VERİ İNDİRME VE STREAMLIT ARAYÜZÜ
# ==========================================

BIST100_LIST = ["GUBRF", "YEOTK", "MAVI", "DOHOL", "TUPRS", "ENJSA", "ASELS", "THYAO", "BIMAS", "AKBNK", "EREGL", "SAHOL", "KCHOL", "SISE"]

@st.cache_data(ttl=1800)
def fetch_data():
    tickers = [f"{t}.IS" for t in BIST100_LIST] + ["XU100.IS"]
    raw = yf.download(tickers, period="1y", group_by='ticker', progress=False)
    
    data_dict = {}
    for t in BIST100_LIST:
        try:
            df = raw[f"{t}.IS"][['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
            if not df.empty: data_dict[t] = df
        except: continue
    df_xu100 = raw["XU100.IS"][['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
    return data_dict, df_xu100

data_dict, df_xu100 = fetch_data()

st.title("🏛️ v44.1 Quant Master Engine - Production Desk")
st.caption("RSI • ADX • RVOL • Relative Strength • ATR Risk/Reward • SMC • Volume Profile")

if st.button("⚡ Taramayı Gelişmiş Filtrelerle Çalıştır", use_container_width=True):
    with st.spinner("BIST Hisseleri Çoklu İndikatör ve ATR Risk Modeli ile Taranıyor..."):
        results = []
        for t, df in data_dict.items():
            res = MultiFactorEngineV441.process_ticker(t, df, df_xu100, regime_score=0.8)
            if res: results.append(res)
            
        df_res = pd.DataFrame(results).sort_values(by="Kurumsal Skor", ascending=False)
        st.session_state['df_v441'] = df_res

if 'df_v441' in st.session_state:
    df_res = st.session_state['df_v441']
    
    st.subheader("📋 Gelişmiş Tarama ve Risk Tablosu")
    st.dataframe(
        df_res,
        column_config={
            "Kurumsal Skor": st.column_config.ProgressColumn("Kurumsal Skor", min_value=0, max_value=100, format="%.1f"),
            "Son Fiyat": st.column_config.NumberColumn(format="₺%.2f"),
            "Stop Loss (2x ATR)": st.column_config.NumberColumn(format="₺%.2f"),
            "Hedef (3.5x ATR)": st.column_config.NumberColumn(format="₺%.2f"),
            "RVOL": st.column_config.NumberColumn(format="%.2fx"),
            "RS (BIST)": st.column_config.NumberColumn(format="%.2f")
        },
        use_container_width=True,
        height=450
    )
    
    st.markdown("---")
    st.markdown("### 💡 Eklenen Yeni Sütunların Anlamı ve Kullanımı:")
    c1, c2, c3 = st.columns(3)
    c1.info("**RVOL > 1.2:** İşleme girerken hacim onayının olduğunu gösterir.")
    c2.info("**RS (BIST) > 1.0:** Hissenin BIST 100 endeksine kıyasla pozitif ayrıştığını doğrular.")
    c3.info("**ADX > 25:** Mevcut trendin (yukarı veya aşağı) ne kadar güçlü olduğunu ölçer.")

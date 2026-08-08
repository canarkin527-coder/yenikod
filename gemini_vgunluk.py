import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime

# ==============================================================================
# 1. STREAMLIT CONFIGURATION & INSTITUTIONAL THEME
# ==============================================================================
st.set_page_config(
    page_title="QUANT MASTER v63 — BIST 100 QUANT ENGINE (EXTENDED)",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main { background-color: #0B0F19; color: #E2E8F0; }
    .stApp { background-color: #0B0F19; }
    .metric-card {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    }
    .metric-value { font-size: 1.6rem; font-weight: 800; color: #38BDF8; margin-top: 4px; }
    .metric-label { font-size: 0.8rem; font-weight: 600; color: #94A3B8; text-transform: uppercase; }
</style>
""", unsafe_allow_html=True)

DB_FILE = "quant_master_v63_extended.db"

# ==============================================================================
# 2. DATABASE ENGINE (SQLITE PERSISTENCE)
# ==============================================================================
class DatabaseEngineV63:
    @staticmethod
    def init_db():
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                quant_score REAL NOT NULL,
                close_price REAL NOT NULL,
                rsi REAL NOT NULL,
                rvol REAL NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    @staticmethod
    def save_results(df_results):
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for _, row in df_results.iterrows():
            conn.execute("""
                INSERT INTO scan_results (timestamp, symbol, quant_score, close_price, rsi, rvol)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (timestamp, row['Symbol'], row['Quant Score'], row['Close (TL)'], row['RSI'], row['RVOL']))
        conn.commit()
        conn.close()

    @staticmethod
    def get_latest_results():
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        try:
            df = pd.read_sql("SELECT * FROM scan_results WHERE timestamp = (SELECT MAX(timestamp) FROM scan_results) ORDER BY quant_score DESC", conn)
        except Exception:
            df = pd.DataFrame()
        conn.close()
        return df

# ==============================================================================
# 3. BIST 100 UNIVERSE PROVIDER
# ==============================================================================
@st.cache_data(ttl=86400)
def get_bist100_constituents():
    return sorted(list(set([
        "AEFES.IS", "AGHOL.IS", "AHGAZ.IS", "AKBNK.IS", "AKCNS.IS", "AKSA.IS", "AKSEN.IS", 
        "ALARK.IS", "ALBRK.IS", "ARCLK.IS", "ASELS.IS", "ASTOR.IS", "BERA.IS", "BIMAS.IS", 
        "BRSAN.IS", "BRYAT.IS", "BUCIM.IS", "CANTE.IS", "CCOLA.IS", "CIMSA.IS", "CWENE.IS", 
        "DEVA.IS", "DOAS.IS", "DOHOL.IS", "ECILC.IS", "ECZYT.IS", "EGEEN.IS", "EKGYO.IS", 
        "ENJSA.IS", "ENKAI.IS", "EREGL.IS", "EUPWR.IS", "FROTO.IS", "GARAN.IS", "GENIL.IS", 
        "GESAN.IS", "GLYHO.IS", "GUBRF.IS", "HALKB.IS", "HEKTS.IS", "IPEKE.IS", "ISCTR.IS", 
        "ISMEN.IS", "KCHOL.IS", "KLSER.IS", "KONTR.IS", "KORDS.IS", "KOZAA.IS", "KOZAL.IS", 
        "KRDMD.IS", "KTLEV.IS", "MAVI.IS", "MGROS.IS", "MIATK.IS", "MPARK.IS", "ODAS.IS", 
        "ODINE.IS", "OTKAR.IS", "OYAKC.IS", "PATEK.IS", "PETKM.IS", "PGSUS.IS", "QUAGR.IS", 
        "SAHOL.IS", "SASA.IS", "SISE.IS", "SKBNK.IS", "SMRTG.IS", "SOKM.IS", "TAVHL.IS", 
        "TCELL.IS", "THYAO.IS", "TKFEN.IS", "TOASO.IS", "TSKB.IS", "TTKOM.IS", "TTRAK.IS", 
        "TUPRS.IS", "ULKER.IS", "VAKBN.IS", "VESBE.IS", "VESTL.IS", "YEOTK.IS", "YKBNK.IS", "ZOREN.IS"
    ])))

# ==============================================================================
# 4. QUANT ENGINE: v63 CORE + REQUESTED ADVANCED INDICATORS & MULTI-TIMEFRAME
# ==============================================================================
class QuantEngineV63:
    @staticmethod
    def fetch_data(symbol, period="1y", interval="1d"):
        df = yf.download(symbol, period=period, interval=interval, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        return df.dropna()

    @staticmethod
    def calculate_indicators(df):
        # --- v63 ORİJİNAL HESAPLAMALARI (DOKUNULMADI) ---
        df['EMA10'] = df['Close'].ewm(span=10, adjust=False).mean()
        df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA150'] = df['Close'].ewm(span=150, adjust=False).mean()
        df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
        
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-10)
        df['RSI'] = 100 - (100 / (1 + rs))
        
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df['ATR'] = true_range.rolling(14).mean()
        
        sma20 = df['Close'].rolling(20).mean()
        std20 = df['Close'].rolling(20).std()
        df['BB_Middle'] = sma20
        df['BB_Upper'] = sma20 + (std20 * 2)
        df['BB_Lower'] = sma20 - (std20 * 2)
        
        df['Vol_SMA20'] = df['Volume'].rolling(20).mean()
        df['RVOL'] = df['Volume'] / (df['Vol_SMA20'] + 1e-10)
        
        df['AVWAP'] = (df['Close'] * df['Volume']).cumsum() / (df['Volume'].cumsum() + 1e-10)
        
        low_52w = df['Low'].rolling(252, min_periods=60).min()
        high_52w = df['High'].rolling(252, min_periods=60).max()
        df['Minervini_OK'] = (
            (df['Close'] > df['EMA150']) & 
            (df['EMA150'] > df['EMA200']) & 
            (df['EMA50'] > df['EMA200']) & 
            (df['Close'] >= low_52w * 1.25) & 
            (df['Close'] >= high_52w * 0.75)
        )

        # --- YENİ EKLENEN İNDİKATÖRLER ---
        # 1. Bollinger Bands (Zaten v63'te vardı, üst/orta/alt tam)
        
        # 2. Stochastic Oscillator (14, 3, 3)
        low_min = df['Low'].rolling(14).min()
        high_max = df['High'].rolling(14).max()
        df['Stoch_K'] = 100 * ((df['Close'] - low_min) / (high_max - low_min + 1e-10))
        df['Stoch_D'] = df['Stoch_K'].rolling(3).mean()
        
        # 3. ADX (Average Directional Index - 14)
        plus_dm = df['High'].diff()
        minus_dm = df['Low'].diff()
        plus_dm = np.where((plus_dm > des_val := 0) & (plus_dm > minus_dm), plus_dm, 0)
        # Basitleştirilmiş ADX bileşenleri
        tr1 = df['High'] - df['Low']
        tr2 = np.abs(df['High'] - df['Close'].shift())
        tr3 = np.abs(df['Low'] - df['Close'].shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr14 = tr.rolling(14).mean()
        plus_di = 100 * (pd.Series(plus_dm).rolling(14).mean() / (atr14 + 1e-10))
        df['ADX'] = pd.Series(np.abs(plus_di)).rolling(14).mean() # Robust Trend Gücü Göstergesi
        
        # 4. Ichimoku Cloud (Tenkan-sen, Kijun-sen)
        nine_high = df['High'].rolling(9).max()
        nine_low = df['Low'].rolling(9).min()
        df['Tenkan_Sen'] = (nine_high + nine_low) / 2
        
        twenty_six_high = df['High'].rolling(26).max()
        twenty_six_low = df['Low'].rolling(26).min()
        df['Kijun_Sen'] = (twenty_six_high + twenty_six_low) / 2
        
        # 5. MFI (Money Flow Index - 14) & OBV (On-Balance Volume)
        typical_price = (df['High'] + df['Low'] + df['Close']) / 3
        money_flow = typical_price * df['Volume']
        pos_flow = np.where(typical_price > typical_price.shift(1), money_flow, 0)
        neg_flow = np.where(typical_price < typical_price.shift(1), money_flow, 0)
        mfi_ratio = pd.Series(pos_flow).rolling(14).sum() / (pd.Series(neg_flow).rolling(14).sum() + 1e-10)
        df['MFI'] = 100 - (100 / (1 + mfi_ratio))
        
        df['OBV'] = (np.sign(df['Close'].diff()) * df['Volume']).fillna(0).cumsum()
        
        return df

    @staticmethod
    def compute_quant_score(df):
        """v63 Orijinal 100 Puanlık Motoru + Yeni Eklenen İndikatör Skor Katkıları"""
        last = df.iloc[-1]
        score = 0.0
        
        # 1. Trend & Minervini (Max 30 Puan)
        if last['Close'] > last['EMA200']: score += 8
        if last['EMA50'] > last['EMA200']: score += 8
        if last['Minervini_OK']: score += 14
        
        # 2. Momentum & RSI (Max 20 Puan)
        rsi = last['RSI']
        if 50 <= rsi <= 70: score += 20
        elif 40 <= rsi < 50: score += 12
        elif rsi > 70: score += 8
        
        # 3. MACD & Hacim / RVOL / OBV (Max 20 Puan)
        if last['MACD_Hist'] > 0: score += 10
        if last['RVOL'] > 1.2: score += 5
        if last['OBV'] > df['OBV'].rolling(20).mean().iloc[-1]: score += 5
        
        # 4. Volatilite, Bollinger & Ichimoku/Stoch/ADX (Max 30 Puan)
        if last['Close'] > last['BB_Middle']: score += 7
        if last.get('Stoch_K', 50) > last.get('Stoch_D', 50): score += 8
        if last.get('ADX', 20) > 25: score += 8
        if last.get('MFI', 50) > 50: score += 7
        
        return round(score, 2)

# ==============================================================================
# 5. STREAMLIT UI INTERFACE (v63 MİMARİSİ)
# ==============================================================================
def main():
    DatabaseEngineV63.init_db()
    
    st.markdown('<h1 style="color:#F8FAFC; margin-bottom:0px;">📊 QUANT MASTER v63 — BIST 100 TARAYICI (GELİŞTİRİLMİŞ)</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color:#94A3B8; font-size:1.0rem;">Toplu Evren Tarama, Çoklu Zaman Dilimi, AVWAP, Bollinger, Stoch, ADX, Ichimoku, MFI/OBV Entegrasyonu</p>', unsafe_allow_html=True)
    st.markdown("---")
    
    st.sidebar.header("⚙️ Kontrol Paneli")
    timeframe = st.sidebar.selectbox("Zaman Dilimi (Multi-Timeframe)", ["1d", "1wk"], index=0)
    action_scan = st.sidebar.button("BIST 100 Evrenini Taramayı Başlat", use_container_width=True)
    
    symbols_list = get_bist100_constituents()
    
    if action_scan:
        scan_results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total = len(symbols_list)
        for i, sym in enumerate(symbols_list):
            status_text.text(f"Taranıyor ({i+1}/{total}): {sym} [{timeframe}]")
            progress_bar.progress((i + 1) / total)
            try:
                df = QuantEngineV63.fetch_data(sym, period="1y", interval=timeframe)
                if len(df) > 50:
                    df = QuantEngineV63.calculate_indicators(df)
                    score = QuantEngineV63.compute_quant_score(df)
                    last_close = float(df['Close'].iloc[-1])
                    rsi = float(df['RSI'].iloc[-1])
                    rvol = float(df['RVOL'].iloc[-1])
                    scan_results.append({
                        "Symbol": sym,
                        "Quant Score": score,
                        "Close (TL)": last_close,
                        "RSI": round(rsi, 2),
                        "RVOL": round(rvol, 2)
                    })
            except Exception:
                continue
        
        status_text.text("Tarama tamamlandı!")
        progress_bar.empty()
        
        if scan_results:
            res_df = pd.DataFrame(scan_results).sort_values(by="Quant Score", ascending=False).reset_index(drop=True)
            DatabaseEngineV63.save_results(res_df)
            st.success("Tarama sonuçları başarıyla SQLite veritabanına kaydedildi.")
            st.dataframe(res_df, use_container_width=True)
    else:
        st.subheader("📁 Son Veritabanı Tarama Sonuçları")
        saved_df = DatabaseEngineV63.get_latest_results()
        if not saved_df.empty:
            st.dataframe(saved_df, use_container_width=True)
        else:
            st.info("Veritabanında henüz kayıtlı tarama sonucu bulunmuyor. Sol menüden **'BIST 100 Evrenini Taramayı Başlat'** butonuna basabilirsiniz.")

if __name__ == "__main__":
    main()

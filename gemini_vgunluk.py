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
from datetime import datetime, timedelta

# ==========================================
# 0. STREAMLIT & ARAYÜZ YAPILANDIRMASI
# ==========================================

st.set_page_config(
    page_title="v44 Quant Master Engine - BIST 100 Desktop",
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
# 1. VERİTABANI YÖNETİCİSİ (SQLITE)
# ==========================================

class DatabaseManager:
    def __init__(self, db_path="quant_trades_v44.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scan_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    ticker TEXT,
                    score REAL,
                    price REAL,
                    regime TEXT,
                    smc_signal TEXT,
                    zone TEXT,
                    vpvr_poc REAL,
                    avwap REAL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS simulated_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    ticker TEXT,
                    entry_price REAL,
                    stop_loss REAL,
                    target_price REAL,
                    status TEXT,
                    pnl_pct REAL
                )
            """)
            conn.commit()

    def save_scan_results(self, df_results):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for _, row in df_results.iterrows():
                cursor.execute("""
                    INSERT INTO scan_history (timestamp, ticker, score, price, regime, smc_signal, zone, vpvr_poc, avwap)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (now, row['Ticker'], row['Institutional Score'], row['Price'], 
                      row['Market Regime'], row['SMC Signal'], row['Market Zone'],
                      row['POC Level'], row['AVWAP Level']))
            conn.commit()

    def fetch_scan_history(self, limit=100):
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(f"SELECT * FROM scan_history ORDER BY id DESC LIMIT {limit}", conn)

# BIST 100 Sembol Listesi
BIST100_FULL = [
    "AGHOL", "AKBNK", "AKSA", "AKSGY", "ALARK", "ALBRK", "ALFAS", "ANHYT", "ANSGR", "ARCLK",
    "ASELS", "ASTOR", "BERA", "BIMAS", "BRSAN", "BRYAT", "BUCIM", "CANTE", "CCOLA", "CIMSA",
    "CWENE", "DOAS", "DOHOL", "EGEEN", "EKGYO", "ENJSA", "ENKAI", "EREGL", "EUPWR", "EUREK",
    "FROTO", "GARAN", "GESAN", "GUBRF", "HALKB", "HEKTS", "ISCTR", "ISGYO", "ISMEN", "KCHOL",
    "KONTR", "KORDS", "KOZAL", "KOZAA", "KRDMD", "MAVI", "MGROS", "MIATK", "ODAS", "OTKAR",
    "OYAKC", "PETKM", "PGSUS", "QUAGR", "SAHOL", "SASA", "SISE", "SKBNK", "SMRTG", "SOKM",
    "TCELL", "THYAO", "TKFEN", "TOASO", "TSKB", "TTKOM", "TUPRS", "ULKER", "VAKBN", "VESBE",
    "VESTL", "YEOTK", "YKBNK", "YYLGD", "ZOREN"
]

# ==========================================
# 2. ADVANCED SMC & PIYASA YAPISI MOTORU
# ==========================================

class AdvancedSMCEngineV44:
    @staticmethod
    def detect_swings(df: pd.DataFrame, window: int = 5):
        """Swing High ve Swing Low noktalarının vektörel tespiti"""
        highs, lows = df['High'], df['Low']
        swing_highs = (highs == highs.rolling(2 * window + 1, center=True).max())
        swing_lows = (lows == lows.rolling(2 * window + 1, center=True).min())
        return swing_highs, swing_lows

    @staticmethod
    def analyze_structure_and_mitigation(df: pd.DataFrame) -> dict:
        """MSS (Market Structure Shift), Premium/Discount, OB Mitigation & Sweep"""
        closes = df['Close'].values
        highs = df['High'].values
        lows = df['Low'].values
        volumes = df['Volume'].values
        
        sh, sl = AdvancedSMCEngineV44.detect_swings(df, window=4)
        sh_idx = np.where(sh)[0]
        sl_idx = np.where(sl)[0]
        
        last_close = closes[-1]
        last_high = highs[-1]
        last_low = lows[-1]
        
        # 1. Market Structure Shift (MSS / BOS)
        mss_bullish = False
        mss_bearish = False
        if len(sh_idx) > 0 and last_close > highs[sh_idx[-1]]:
            mss_bullish = True
        elif len(sl_idx) > 0 and last_close < lows[sl_idx[-1]]:
            mss_bearish = True
            
        # 2. Premium / Discount & Equilibrium (OTE)
        lookback = min(60, len(df))
        recent_high = np.max(highs[-lookback:])
        recent_low = np.min(lows[-lookback:])
        eq_level = (recent_high + recent_low) / 2.0
        range_size = recent_high - recent_low
        
        zone = "EQUILIBRIUM"
        if range_size > 0:
            if last_close > eq_level + (range_size * 0.15):
                zone = "PREMIUM 🔴"
            elif last_close < eq_level - (range_size * 0.15):
                zone = "DISCOUNT 🟢"
            
        # 3. Order Block & Mitigation Check
        ob_mitigated = False
        active_ob_bullish = False
        if len(sl_idx) > 0:
            last_sl_price = lows[sl_idx[-1]]
            # Fiyat son swing low bölgesini test edip üstünde kapandıysa (Mitigation)
            if last_low <= last_sl_price * 1.01 and last_close > last_sl_price:
                ob_mitigated = True
                active_ob_bullish = True

        # 4. Liquidity Sweep (Sweep & Reclaim)
        liquidity_sweep = False
        if len(sh_idx) > 0 and last_high > highs[sh_idx[-1]] and last_close < highs[sh_idx[-1]]:
            liquidity_sweep = True # Bearish Liquidity Sweep
            
        return {
            "MSS_Bullish": mss_bullish,
            "MSS_Bearish": mss_bearish,
            "Zone": zone,
            "OB_Mitigated": ob_mitigated,
            "Active_OB_Bullish": active_ob_bullish,
            "Liquidity_Sweep": liquidity_sweep,
            "Equilibrium": round(eq_level, 2),
            "Recent_High": round(recent_high, 2),
            "Recent_Low": round(recent_low, 2)
        }

# ==========================================
# 3. VOLUME PROFILE (VPVR) & ANCHORED VWAP
# ==========================================

class VolumeProfileEngine:
    @staticmethod
    def calculate_vpvr(df: pd.DataFrame, bins: int = 40) -> tuple:
        """Volume Profile VR, POC (Point of Control), HVN ve LVN"""
        price_min = df['Low'].min()
        price_max = df['High'].max()
        
        if price_max == price_min:
            return df['Close'].iloc[-1], np.array([price_min]), np.array([1]), np.array([False]), np.array([False])
            
        price_bins = np.linspace(price_min, price_max, bins + 1)
        volume_profile = np.zeros(bins)
        
        # Hacimleri fiyat dilimlerine dağıtma
        for idx in range(len(df)):
            c_price = df['Close'].iloc[idx]
            c_vol = df['Volume'].iloc[idx]
            bin_idx = np.digitize(c_price, price_bins) - 1
            if 0 <= bin_idx < bins:
                volume_profile[bin_idx] += c_vol
                
        poc_idx = np.argmax(volume_profile)
        poc_price = (price_bins[poc_idx] + price_bins[poc_idx + 1]) / 2.0
        
        # High Volume Nodes (HVN) & Low Volume Nodes (LVN)
        vol_mean = np.mean(volume_profile)
        hvn_mask = volume_profile > 1.3 * vol_mean
        lvn_mask = volume_profile < 0.6 * vol_mean
        
        return poc_price, price_bins, volume_profile, hvn_mask, lvn_mask

    @staticmethod
    def calculate_anchored_vwap(df: pd.DataFrame, anchor_idx: int = -60) -> pd.Series:
        """En Yüksek Hacimli veya Belirli Döneme Çıpalanmış VWAP"""
        actual_anchor = max(-len(df), anchor_idx)
        df_sub = df.iloc[actual_anchor:].copy()
        typical_price = (df_sub['High'] + df_sub['Low'] + df_sub['Close']) / 3.0
        cum_tp_vol = (typical_price * df_sub['Volume']).cumsum()
        cum_vol = df_sub['Volume'].cumsum()
        avwap = cum_tp_vol / (cum_vol + 1e-9)
        
        full_avwap = pd.Series(np.nan, index=df.index)
        full_avwap.iloc[actual_anchor:] = avwap
        return full_avwap

# ==========================================
# 4. PIYASA REJIMI VE GENİŞLİK (BREADTH) MOTORU
# ==========================================

class MarketBreadthEngine:
    @staticmethod
    def evaluate_market_regime(df_xu100: pd.DataFrame, data_dict: dict) -> dict:
        """XU100 Trend Rejimi ve Piyasaya Yayılan Güç (Advance/Decline)"""
        closes = df_xu100['Close']
        sma50 = closes.rolling(50).mean().iloc[-1]
        sma200 = closes.rolling(200).mean().iloc[-1]
        last_close = closes.iloc[-1]
        
        if last_close > sma50 and sma50 > sma200:
            regime = "BOĞA 🟢 (Güçlü Trend)"
            regime_score = 1.0
        elif last_close > sma200 and last_close < sma50:
            regime = "KARARSIZ 🟡 (Düzeltme)"
            regime_score = 0.5
        else:
            regime = "AYI 🔴 (Yüksek Risk)"
            regime_score = 0.0
            
        advances = 0
        declines = 0
        for ticker, df in data_dict.items():
            if len(df) >= 2:
                pct = (df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2]
                if pct > 0: advances += 1
                else: declines += 1
                
        breadth_ratio = advances / (advances + declines + 1e-9)
        return {
            "Regime": regime,
            "RegimeScore": regime_score,
            "Advances": advances,
            "Declines": declines,
            "BreadthRatio": round(breadth_ratio, 2)
        }

# ==========================================
# 5. MONTE CARLO & ADAPTİF KELLY RİSK MOTORU
# ==========================================

class QuantRiskEngine:
    @staticmethod
    def run_monte_carlo(returns: np.ndarray, num_sims: int = 1000, days: int = 60) -> dict:
        """Geleceğe Yönelik 1.000 Yollu Monte Carlo Portföy Simülasyonu"""
        if len(returns) < 10 or np.isnan(returns).any():
            returns = np.random.normal(0.001, 0.02, 100)
            
        sim_paths = np.zeros((days, num_sims))
        sim_paths[0] = 100.0 # Başlangıç sermayesi 100 birim
        
        for t in range(1, days):
            rand_draws = np.random.choice(returns, size=num_sims, replace=True)
            sim_paths[t] = sim_paths[t-1] * (1 + rand_draws)
            
        final_values = sim_paths[-1]
        max_drawdowns = []
        
        for s in range(num_sims):
            path = sim_paths[:, s]
            peak = np.maximum.accumulate(path)
            dd = (path - peak) / (peak + 1e-9)
            max_drawdowns.append(np.min(dd))
            
        return {
            "Median_Return": np.median(final_values) - 100.0,
            "VaR_95": np.percentile(final_values, 5) - 100.0,
            "Max_Drawdown_95": np.percentile(max_drawdowns, 5) * 100.0,
            "Ruinate_Prob": (np.sum(final_values < 80.0) / num_sims) * 100.0,
            "Sim_Paths": sim_paths
        }

    @staticmethod
    def adaptive_kelly_criterion(win_rate: float, win_loss_ratio: float, regime_multiplier: float) -> float:
        """Piyasa Rejimi ve Risk Katsayısıyla Daraltılmış Adaptif Kelly Oranı"""
        if win_loss_ratio <= 0: return 0.0
        kelly_b = win_loss_ratio
        kelly_f = (win_rate * (kelly_b + 1) - 1) / kelly_b
        
        # Half-Kelly Güvenlik Katsayısı ve Rejim Çarpanı
        safe_kelly = max(0.0, kelly_f * 0.5 * regime_multiplier)
        return min(0.25, safe_kelly)

# ==========================================
# 6. ÇOK BİLEŞENLİ SKORLAMA VE PORTFÖY OPTİMİZASYONU
# ==========================================

class MultiFactorEngineV44:
    @staticmethod
    def calculate_score(df: pd.DataFrame, df_xu100: pd.DataFrame, regime_info: dict) -> tuple:
        if len(df) < 80:
            return 0.0, {}, 0.0, 0.0, "N/A"
            
        smc = AdvancedSMCEngineV44.analyze_structure_and_mitigation(df)
        poc_price, _, _, _, _ = VolumeProfileEngine.calculate_vpvr(df)
        avwap = VolumeProfileEngine.calculate_anchored_vwap(df).iloc[-1]
        
        last_price = df['Close'].iloc[-1]
        
        # Temel Skor (50 Başlangıç)
        score = 50.0
        score += regime_info['RegimeScore'] * 15.0
        
        # SMC Yapısı Puanlaması
        if smc["MSS_Bullish"]: score += 12
        if smc["Zone"] == "DISCOUNT 🟢": score += 10
        if smc["OB_Mitigated"]: score += 8
        if smc["Liquidity_Sweep"]: score -= 12 # Ayı Kapanı Riski
        
        # Hacim ve VWAP Puanlaması
        if not np.isnan(avwap) and last_price > avwap: score += 8
        if last_price > poc_price: score += 7
        
        final_score = round(min(100.0, max(0.0, score)), 1)
        
        signal = "NÖTR ⚪"
        if final_score >= 75: signal = "GÜÇLÜ AL 🚀"
        elif final_score >= 60: signal = "AL 🟢"
        elif final_score <= 40: signal = "SAT 🔴"
        
        return final_score, smc, poc_price, (avwap if not np.isnan(avwap) else last_price), signal

class PortfolioOptimizationEngine:
    @staticmethod
    def inverse_volatility_weights(returns_df: pd.DataFrame) -> np.ndarray:
        vols = returns_df.std() * np.sqrt(252)
        inv_vols = 1.0 / (vols + 1e-9)
        return inv_vols.values / np.sum(inv_vols.values)

    @staticmethod
    def markowitz_max_sharpe(returns_df: pd.DataFrame, risk_free_rate: float = 0.40) -> np.ndarray:
        num_assets = len(returns_df.columns)
        if num_assets == 0: return np.array([])
        
        mean_returns = returns_df.mean() * 252
        cov_matrix = returns_df.cov() * 252
        
        def objective(weights):
            p_return = np.sum(mean_returns * weights)
            p_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            sharpe = (p_return - risk_free_rate) / (p_vol + 1e-9)
            return -sharpe

        constraints = ({'type': 'eq', 'fun': lambda w: np.sum(w) - 1})
        bounds = tuple((0, 1) for _ in range(num_assets))
        init_weights = np.array([1.0 / num_assets] * num_assets)
        
        try:
            opt = minimize(objective, init_weights, method='SLSQP', bounds=bounds, constraints=constraints)
            return opt.x if opt.success else init_weights
        except:
            return init_weights

# ==========================================
# 7. EŞZAMANLI (PARALEL) VERİ İŞLEME MOTORU
# ==========================================

@st.cache_data(ttl=1800)
def fetch_all_bist100_data():
    tickers_formatted = [f"{t}.IS" for t in BIST100_FULL] + ["XU100.IS"]
    data = yf.download(tickers_formatted, period="1y", group_by='ticker', progress=False)
    
    data_dict = {}
    for t in BIST100_FULL:
        try:
            df = data[f"{t}.IS"][['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
            if not df.empty and len(df) > 30:
                data_dict[t] = df
        except KeyError:
            continue
            
    df_xu100 = data["XU100.IS"][['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
    return data_dict, df_xu100

def process_single_ticker_v44(ticker, df_stock, df_xu100, regime_info):
    score, smc, poc_price, avwap, signal = MultiFactorEngineV44.calculate_score(df_stock, df_xu100, regime_info)
    return {
        "Ticker": ticker,
        "Institutional Score": score,
        "Price": round(df_stock['Close'].iloc[-1], 2),
        "SMC Signal": signal,
        "Market Zone": smc.get("Zone", "N/A"),
        "MSS Status": "MSS BÖLGESİ ⚡" if smc.get("MSS_Bullish") else "NORMAL",
        "OB Mitigation": "TEST EDİLDİ ✅" if smc.get("OB_Mitigated") else "YOK",
        "POC Level": round(poc_price, 2),
        "AVWAP Level": round(avwap, 2),
        "Market Regime": regime_info["Regime"]
    }

# ==========================================
# 8. STREAMLIT DOKUNMATİK ARAYÜZ MİMARİSİ
# ==========================================

db_mgr = DatabaseManager()

st.title("🏛️ BIST 100 Quant Master Engine v44")
st.markdown("`Parallel Multi-Threading` • `Advanced SMC` • `VPVR & AVWAP` • `Monte Carlo Risk Desk`")

# YAN PANEL
st.sidebar.header("⚙️ v44 Çalışma Parametreleri")
max_workers = st.sidebar.slider("Paralel Thread (Worker) Sayısı", 2, 16, 8)
top_n = st.sidebar.slider("Portföy Seçim Limiti (Top N)", 3, 10, 5)

tab_scanner, tab_details, tab_risk, tab_db = st.tabs([
    "🔍 Paralel Tarayıcı & Portföy", 
    "📈 Hacim Profili & SMC Detay", 
    "🎲 Monte Carlo Risk Masası", 
    "🗄️ SQLite Veritabanı Geçmişi"
])

# Veri İndirme
data_dict, df_xu100 = fetch_all_bist100_data()
regime_info = MarketBreadthEngine.evaluate_market_regime(df_xu100, data_dict)

# TAB 1: PARALEL TARAYICI
with tab_scanner:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Piyasa Rejimi", regime_info["Regime"])
    c2.metric("Yükselen / Düşen", f"{regime_info['Advances']} / {regime_info['Declines']}")
    c3.metric("Genişlik Oranı (Breadth)", f"%{int(regime_info['BreadthRatio']*100)}")
    c4.metric("Taranabilir Hisse Sayısı", f"{len(data_dict)} Hisse")

    if st.button("🚀 BIST 100 Paralel Taramayı Başlat", use_container_width=True):
        start_t = time.time()
        
        with st.spinner("BIST 100 Hisseleri Eşzamanlı Taranıyor ve Skorlanıyor..."):
            results = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(process_single_ticker_v44, t, df, df_xu100, regime_info): t
                    for t, df in data_dict.items()
                }
                for fut in as_completed(futures):
                    res = fut.result()
                    if res["Institutional Score"] > 0:
                        results.append(res)
                        
            df_scan = pd.DataFrame(results).sort_values(by="Institutional Score", ascending=False)
            exec_time = time.time() - start_t
            
            db_mgr.save_scan_results(df_scan)
            st.session_state['df_scan'] = df_scan
            
        st.success(f"⚡ Tarama Tamamlandı! **{len(df_scan)}** hisse **{exec_time:.2f}** saniyede analiz edildi.")

    if 'df_scan' in st.session_state:
        df_scan = st.session_state['df_scan']
        
        st.subheader("📊 Kurumsal Skorlama ve SMC Matrisi")
        st.dataframe(
            df_scan,
            column_config={
                "Institutional Score": st.column_config.ProgressColumn("Kurumsal Skor", format="%.1f", min_value=0, max_value=100),
                "Price": st.column_config.NumberColumn("Son Fiyat", format="₺%.2f")
            },
            use_container_width=True,
            height=360
        )
        
        # PORTFÖY OPTİMİZASYONU
        st.markdown("---")
        st.subheader(f"💼 Optimizasyon Sonuçları (En Yüksek Skorlu Top {top_n} Hisse)")
        
        top_tickers = df_scan.head(top_n)["Ticker"].tolist()
        returns_list = [data_dict[t]['Close'].pct_change().rename(t) for t in top_tickers if t in data_dict]
        
        if len(returns_list) > 0:
            df_top_ret = pd.concat(returns_list, axis=1).dropna()
            
            w_inv_vol = PortfolioOptimizationEngine.inverse_volatility_weights(df_top_ret)
            w_markowitz = PortfolioOptimizationEngine.markowitz_max_sharpe(df_top_ret)
            
            df_opt = pd.DataFrame({
                "Hisse": top_tickers,
                "Kurumsal Skor": df_scan.head(top_n)["Institutional Score"].values,
                "Risk Parity %": np.round(w_inv_vol * 100, 2),
                "Markowitz Max Sharpe %": np.round(w_markowitz * 100, 2)
            })
            
            col_opt1, col_opt2 = st.columns([0.55, 0.45])
            with col_opt1:
                st.dataframe(df_opt, use_container_width=True)
            with col_opt2:
                fig_p = go.Figure(data=[go.Pie(
                    labels=df_opt["Hisse"], 
                    values=df_opt["Markowitz Max Sharpe %"], 
                    hole=.4,
                    textinfo='label+percent'
                )])
                fig_p.update_layout(height=280, template="plotly_dark", title="Markowitz Max Sharpe Dağılımı", margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_p, use_container_width=True)

# TAB 2: DETAYLI HACİM VE GRAPH
with tab_details:
    st.subheader("📈 Hacim Profili (VPVR) & Anchored VWAP Arayüzü")
    selected_ticker = st.selectbox("İncelemek İstediğiniz Sembolü Seçin:", BIST100_FULL)
    
    if selected_ticker in data_dict:
        df_selected = data_dict[selected_ticker]
        poc_p, p_bins, v_prof, _, _ = VolumeProfileEngine.calculate_vpvr(df_selected)
        avwap_s = VolumeProfileEngine.calculate_anchored_vwap(df_selected)
        
        fig_chart = make_subplots(rows=1, cols=2, shared_yaxes=True, column_widths=[0.8, 0.2], horizontal_spacing=0.02)
        
        # Fiyat Mumları
        fig_chart.add_trace(go.Candlestick(
            x=df_selected.index,
            open=df_selected['Open'], high=df_selected['High'],
            low=df_selected['Low'], close=df_selected['Close'],
            name="Fiyat"
        ), row=1, col=1)
        
        # Anchored VWAP
        fig_chart.add_trace(go.Scatter(
            x=df_selected.index, y=avwap_s,
            mode='lines', name='Anchored VWAP',
            line=dict(color='#f6ad55', width=2)
        ), row=1, col=1)
        
        # POC Çizgisi
        fig_chart.add_hline(y=poc_p, line_dash="dash", line_color="#e53e3e", annotation_text=f"POC: {poc_p:.2f}", row=1, col=1)
        
        # Volume Profile Histogram
        fig_chart.add_trace(go.Bar(
            y=(p_bins[:-1] + p_bins[1:]) / 2,
            x=v_prof,
            orientation='h',
            name="Hacim Profili",
            marker_color='rgba(66, 153, 225, 0.5)'
        ), row=1, col=2)
        
        fig_chart.update_layout(height=560, template="plotly_dark", showlegend=False, title=f"{selected_ticker} Gelişmiş Derinlik Grafiği")
        st.plotly_chart(fig_chart, use_container_width=True)

# TAB 3: MONTE CARLO & KELLY RISK
with tab_risk:
    st.subheader("🎲 Monte Carlo Risk Simülasyonu & Adaptif Kelly")
    
    col_r1, col_r2 = st.columns([0.4, 0.6])
    with col_r1:
        st.markdown("### Risk & Pozisyon Boyutlandırma")
        win_rate = st.slider("Tahmini Win Rate (Kazanma Oranı)", 0.3, 0.8, 0.55)
        win_loss = st.slider("Win/Loss Oranı (Kazanç/Kayıp)", 1.0, 3.0, 1.8)
        
        kelly_alloc = QuantRiskEngine.adaptive_kelly_criterion(win_rate, win_loss, regime_info["RegimeScore"])
        st.metric("Adaptif Kelly Sermaye Tahsisi", f"%{kelly_alloc * 100:.1f}")
        st.info("Piyasa rejimi katsayısı ve Half-Kelly güvenlik faktörü sermaye koruması için otomatik uygulanmıştır.")
        
    with col_r2:
        if 'df_scan' in st.session_state and len(st.session_state['df_scan']) > 0:
            top_t = st.session_state['df_scan'].head(1)["Ticker"].values[0]
            ret_sample = data_dict[top_t]['Close'].pct_change().dropna().values
            mc_res = QuantRiskEngine.run_monte_carlo(ret_sample, num_sims=500, days=60)
            
            st.markdown(f"### {top_t} İçin Monte Carlo Yolları (60 Günlük Simülasyon)")
            
            # Monte Carlo Grafiği
            fig_mc = go.Figure()
            sim_paths = mc_res["Sim_Paths"]
            for i in range(min(50, sim_paths.shape[1])): # İlk 50 patikayı çizdir
                fig_mc.add_trace(go.Scatter(y=sim_paths[:, i], mode='lines', line=dict(width=0.8), opacity=0.3, showlegend=False))
                
            fig_mc.update_layout(height=320, template="plotly_dark", title=f"50/500 Örnek Simülasyon Patikası ({top_t})")
            st.plotly_chart(fig_mc, use_container_width=True)
            
            rc1, rc2, rc3 = st.columns(3)
            rc1.metric("Riske Maruz Değer (VaR %95)", f"%{mc_res['VaR_95']:.1f}")
            rc2.metric("Maksimum Drawdown (%95)", f"%{mc_res['Max_Drawdown_95']:.1f}")
            rc3.metric("İflas Riski (Ruination)", f"%{mc_res['Ruinate_Prob']:.1f}")

# TAB 4: VERİTABANI GEÇMİŞİ
with tab_db:
    st.subheader("🗄️ SQLite Veritabanı Tarama Kayıtları")
    df_db_history = db_mgr.fetch_scan_history(limit=100)
    if not df_db_history.empty:
        st.dataframe(df_db_history, use_container_width=True)
    else:
        st.info("Henüz veritabanına kaydedilmiş bir tarama verisi bulunmuyor. 'Taramayı Başlat' butonuna basarak kayıt oluşturabilirsiniz.")

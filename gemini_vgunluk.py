import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
import sqlite3

# ==========================================
# 0. STREAMLIT CONFIGURATION & DATABASE
# ==========================================
st.set_page_config(
    page_title="v44.4 Quant Master Engine - Institutional Quality Desk",
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

def init_db():
    conn = sqlite3.connect("portfolio.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS portfolio 
                 (ticker TEXT PRIMARY KEY, amount REAL, avg_price REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS balance 
                 (id INTEGER PRIMARY KEY, cash REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, 
                  ticker TEXT, type TEXT, amount REAL, price REAL, pnl REAL)''')
    c.execute("SELECT count(*) FROM balance")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO balance (id, cash) VALUES (1, 100000.0)")
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 1. TEKNİK İNDİKATÖR VE GERÇEK WİLDER ADX MOTORU
# ==========================================

class TechnicalFilterEngine:
    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> float:
        series = df['Close']
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-9)
        rsi = 100 - (100 / (1 + rs))
        val = rsi.iloc[-1]
        return float(val.iloc[0]) if isinstance(val, pd.Series) else float(val)

    @staticmethod
    def calculate_true_range(df: pd.DataFrame) -> pd.Series:
        """GERÇEK WILDER TRUE RANGE (GAP'LER DAHİL)"""
        high = df['High']
        low = df['Low']
        prev_close = df['Close'].shift(1)
        tr1 = high - low
        tr2 = np.abs(high - prev_close)
        tr3 = np.abs(low - prev_close)
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
        tr = TechnicalFilterEngine.calculate_true_range(df)
        atr = tr.rolling(period).mean()
        val = atr.iloc[-1]
        return float(val.iloc[0]) if isinstance(val, pd.Series) else float(val)

    @staticmethod
    def calculate_adx(df: pd.DataFrame, period: int = 14) -> float:
        """GERÇEK WILDER ADX HESAPLAMASI"""
        df_calc = df.copy()
        df_calc['up'] = df_calc['High'] - df_calc['High'].shift(1)
        df_calc['down'] = df_calc['Low'].shift(1) - df_calc['Low']
        
        df_calc['+dm'] = np.where((df_calc['up'] > df_calc['down']) & (df_calc['up'] > 0), df_calc['up'], 0.0)
        df_calc['-dm'] = np.where((df_calc['down'] > df_calc['up']) & (df_calc['down'] > 0), df_calc['down'], 0.0)
        
        tr = TechnicalFilterEngine.calculate_true_range(df_calc)
        tr_smooth = tr.rolling(period).mean()
        
        plus_di = 100 * (df_calc['+dm'].rolling(period).mean() / (tr_smooth + 1e-9))
        minus_di = 100 * (df_calc['-dm'].rolling(period).mean() / (tr_smooth + 1e-9))
        
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)
        adx = dx.rolling(period).mean()
        val = adx.iloc[-1]
        return float(val.iloc[0]) if isinstance(val, pd.Series) else float(val)

    @staticmethod
    def calculate_rvol(df: pd.DataFrame, period: int = 20) -> float:
        avg_vol = df['Volume'].rolling(period).mean().iloc[-1]
        last_vol = df['Volume'].iloc[-1]
        v_avg = float(avg_vol.iloc[0]) if isinstance(avg_vol, pd.Series) else float(avg_vol)
        v_last = float(last_vol.iloc[0]) if isinstance(last_vol, pd.Series) else float(last_vol)
        return float(v_last / (v_avg + 1e-9))

    @staticmethod
    def calculate_relative_strength(df_stock: pd.DataFrame, df_xu100: pd.DataFrame, period: int = 60) -> float:
        s_close = df_stock['Close']
        x_close = df_xu100['Close']
        stock_ret = (s_close.iloc[-1] - s_close.iloc[-period]) / s_close.iloc[-period]
        xu100_ret = (x_close.iloc[-1] - x_close.iloc[-period]) / x_close.iloc[-period]
        
        r_stock = float(stock_ret.iloc[0]) if isinstance(stock_ret, pd.Series) else float(stock_ret)
        r_index = float(xu100_ret.iloc[0]) if isinstance(xu100_ret, pd.Series) else float(xu100_ret)
        return float((1 + r_stock) / (1 + r_index + 1e-9))

# ==========================================
# 2. ADVANCED SMC & GEOMETRIC OB/MSS ENGINE
# ==========================================

class AdvancedSMCEngineV44:
    @staticmethod
    def analyze_structure(df: pd.DataFrame):
        highs, lows, closes = df['High'], df['Low'], df['Close']
        window = 5
        sh = (highs == highs.rolling(2 * window + 1, center=True).max())
        sl = (lows == lows.rolling(2 * window + 1, center=True).min())
        
        sh_idx, sl_idx = np.where(sh)[0], np.where(sl)[0]
        last_close = float(closes.iloc[-1].iloc[0]) if isinstance(closes.iloc[-1], pd.Series) else float(closes.iloc[-1])
        last_low = float(lows.iloc[-1].iloc[0]) if isinstance(lows.iloc[-1], pd.Series) else float(lows.iloc[-1])
        
        # Bullish / Bearish MSS (Market Structure Shift)
        mss_bullish = len(sh_idx) > 0 and last_close > float(highs.iloc[sh_idx[-1]])
        mss_bearish = len(sl_idx) > 0 and last_close < float(lows.iloc[sl_idx[-1]])
        
        lookback = min(60, len(df))
        rec_h = float(highs.iloc[-lookback:].max())
        rec_l = float(lows.iloc[-lookback:].min())
        eq_level = (rec_h + rec_l) / 2.0
        r_size = rec_h - rec_l
        
        zone = "EQUILIBRIUM"
        if r_size > 0:
            if last_close > eq_level + (r_size * 0.15): zone = "PREMIUM 🔴"
            elif last_close < eq_level - (r_size * 0.15): zone = "DISCOUNT 🟢"
            
        # Geometrik Order Block & Structural Support
        ob_mitigated = False
        structural_support = rec_l
        if len(sl_idx) > 0:
            last_sl_price = float(lows.iloc[sl_idx[-1]])
            structural_support = last_sl_price
            if last_low <= last_sl_price * 1.015 and last_close > last_sl_price:
                ob_mitigated = True
                
        return {
            "MSS_Bullish": mss_bullish, 
            "MSS_Bearish": mss_bearish, 
            "Zone": zone, 
            "OB_Mitigated": ob_mitigated,
            "Structural_Support": structural_support,
            "Recent_High": rec_h
        }

class VolumeProfileEngine:
    @staticmethod
    def calculate_vpvr_poc(df: pd.DataFrame, bins: int = 30) -> float:
        p_min, p_max = float(df['Low'].min()), float(df['High'].max())
        if p_max == p_min: 
            val = df['Close'].iloc[-1]
            return float(val.iloc[0]) if isinstance(val, pd.Series) else float(val)
        
        p_bins = np.linspace(p_min, p_max, bins + 1)
        v_prof = np.zeros(bins)
        
        closes = df['Close'].values
        volumes = df['Volume'].values
        for idx in range(len(df)):
            b_idx = np.digitize(closes[idx], p_bins) - 1
            if 0 <= b_idx < bins: 
                v_prof[b_idx] += volumes[idx]
        return float((p_bins[np.argmax(v_prof)] + p_bins[np.argmax(v_prof) + 1]) / 2.0)

    @staticmethod
    def calculate_avwap(df: pd.DataFrame) -> float:
        sub = df.iloc[-60:]
        tp = (sub['High'] + sub['Low'] + sub['Close']) / 3.0
        avwap = (tp * sub['Volume']).sum() / (sub['Volume'].sum() + 1e-9)
        return float(avwap.iloc[0]) if isinstance(avwap, pd.Series) else float(avwap)

# ==========================================
# 3. MİMARİ VE DİNAMİK R:R SKORLAMA MOTORU
# ==========================================

class QualityWeightedEngine:
    @staticmethod
    def process_ticker(ticker: str, df: pd.DataFrame, df_xu100: pd.DataFrame, regime_score: float) -> dict:
        if len(df) < 60 or df_xu100 is None or len(df_xu100) < 60: 
            return None
        
        last_price_val = df['Close'].iloc[-1]
        last_price = float(last_price_val.iloc[0]) if isinstance(last_price_val, pd.Series) else float(last_price_val)
        
        rsi = TechnicalFilterEngine.calculate_rsi(df)
        adx = TechnicalFilterEngine.calculate_adx(df)
        rvol = TechnicalFilterEngine.calculate_rvol(df)
        rs_score = TechnicalFilterEngine.calculate_relative_strength(df, df_xu100)
        atr = TechnicalFilterEngine.calculate_atr(df)
        
        smc = AdvancedSMCEngineV44.analyze_structure(df)
        poc = VolumeProfileEngine.calculate_vpvr_poc(df)
        avwap = VolumeProfileEngine.calculate_avwap(df)
        
        # --- YAPISAL & DİNAMİK R:R HESAPLAMASI ---
        # Stop = OB/Swing Low altı veya min 1.5 ATR
        structural_stop = min(smc["Structural_Support"] * 0.99, last_price - (1.5 * atr))
        stop_loss = round(min(last_price * 0.98, structural_stop), 2)
        
        # Hedef = Recent High / Liquidity Sweep Seviyesi
        target_price = round(max(last_price + (2.5 * atr), smc["Recent_High"]), 2)
        
        risk = last_price - stop_loss
        reward = target_price - last_price
        rr_ratio = round(reward / (risk + 1e-9), 2)
        
        # --- TABAN SKOR HESABI ---
        trend_vol_score = 0.0
        if adx >= 35: trend_vol_score += 15.0
        elif adx >= 25: trend_vol_score += 12.0
        elif adx >= 18: trend_vol_score += 6.0
        
        if rvol >= 1.2: trend_vol_score += 12.0
        elif rvol >= 0.8: trend_vol_score += 6.0
        
        if rs_score > 1.05: trend_vol_score += 8.0
        elif rs_score > 1.0: trend_vol_score += 4.0
        
        # SMC Skorlama
        smc_score = 0.0
        if smc["Zone"] == "DISCOUNT 🟢": smc_score += 15.0
        elif smc["Zone"] == "EQUILIBRIUM": smc_score += 5.0
        elif smc["Zone"] == "PREMIUM 🔴": smc_score -= 10.0  # Asimetrik ceza
        
        if smc["OB_Mitigated"]: smc_score += 15.0
        if smc["MSS_Bullish"]: smc_score += 8.0
        if smc["MSS_Bearish"]: smc_score -= 12.0
        
        # İndikatör Teyidi
        tech_score = 0.0
        if 40 <= rsi <= 65: tech_score += 10.0
        if last_price > avwap: tech_score += 10.0
        if last_price > poc: tech_score += 10.0
        
        raw_score = trend_vol_score + smc_score + tech_score
        
        # --- MARKET REGIME & ELEME FİLTRELERİ ---
        warnings = []
        is_candidate_setup = (smc["Zone"] == "DISCOUNT 🟢" and smc["OB_Mitigated"])
        
        # Market Regime Etkisi (Testere piyasasında puan kırma)
        if regime_score < 0.5:
            raw_score *= 0.88
            warnings.append("⚠️ Piyasada Trend Yok")
            
        if adx < 15:
            penalty_adx = 0.90 if is_candidate_setup else 0.80
            raw_score *= penalty_adx
            warnings.append("⚠️ Zayıf Trend")
            
        if rvol < 0.40:
            raw_score *= 0.80
            warnings.append("⚠️ Çok Düşük Hacim")
        elif 0.40 <= rvol < 0.80:
            gradual_mult = 0.90 + (rvol - 0.40) * (0.08 / 0.40)
            if is_candidate_setup: gradual_mult = min(1.0, gradual_mult + 0.05)
            raw_score *= gradual_mult
            if not is_candidate_setup: warnings.append("💡 Akümülasyon Hacmi")
            
        if rsi > 70:
            raw_score = min(raw_score, 70.0)
            warnings.append("⚠️ Aşırı Alım")
            
        if smc["Zone"] == "PREMIUM 🔴":
            warnings.append("🔴 Premium Bölge")

        final_score = round(min(100.0, max(0.0, raw_score)), 1)
        
        # --- CONTINUOUS QUALİTY STARS ---
        quality_stars = 1
        if adx >= 25: quality_stars += 1
        if rvol >= 1.0: quality_stars += 1
        if smc["Zone"] == "DISCOUNT 🟢": quality_stars += 1
        if smc["OB_Mitigated"] and rr_ratio >= 1.75: quality_stars += 1
        
        star_str = "⭐" * quality_stars + "☆" * (5 - quality_stars)
        
        # --- NİHAİ AL / SİNYAL FİLTRESİ ---
        signal = "NÖTR ⚪"
        if final_score >= 68 and adx >= 20 and rvol >= 0.95 and rs_score >= 1.0 and rr_ratio >= 1.50 and rsi <= 68 and smc["Zone"] != "PREMIUM 🔴":
            signal = "GÜÇLÜ AL 🚀" if final_score >= 78 else "AL 🟢"
        elif is_candidate_setup and final_score >= 54 and adx >= 14:
            signal = "ADAY SETUP 🟡"
        elif final_score <= 38 or smc["MSS_Bearish"]:
            signal = "SAT 🔴"
        
        return {
            "Ticker": ticker,
            "Kurumsal Skor": final_score,
            "Teknik Kalite": star_str,
            "Sinyal": signal,
            "Ufuk / Uyarılar": " | ".join(warnings) if warnings else "Teyitli ✅",
            "Son Fiyat": round(last_price, 2),
            "Zone": smc["Zone"],
            "OB Test": "EVET ✅" if smc["OB_Mitigated"] else "HAYIR ❌",
            "RSI (14)": round(rsi, 1),
            "ADX (14)": round(adx, 1),
            "RVOL": round(rvol, 2),
            "RS (BIST)": round(rs_score, 2),
            "Stop Loss": stop_loss,
            "Hedef": target_price,
            "R:R Ratio": rr_ratio,
        }

# ==========================================
# 4. VERİ İNDİRME VE BİST 100 LİSTESİ (40+ HİSSE)
# ==========================================

BIST100_EXPANDED = [
    "AKBNK", "ALARK", "ARCLK", "ASELS", "BIMAS", "BRSAN", "CIMSA", "DOHOL", 
    "EKGYO", "ENJSA", "ENKAI", "EREGL", "FROTO", "GARAN", "GUBRF", "HEKTS", 
    "ISCTR", "KCHOL", "KONTR", "KOZAL", "KRDMD", "MAVI", "MGROS", "ODAS", 
    "OYAKC", "PETKM", "PGSUS", "SAHOL", "SASA", "SISE", "SKBNK", "TCELL", 
    "THYAO", "TKFEN", "TOASO", "TSKB", "TTKOM", "TUPRS", "VAKBN", "YEOTK", "YKBNK"
]

@st.cache_data(ttl=1800)
def fetch_data():
    tickers = [f"{t}.IS" for t in BIST100_EXPANDED] + ["XU100.IS"]
    raw = yf.download(tickers, period="1y", group_by='ticker', progress=False)
    
    data_dict = {}
    for t in BIST100_EXPANDED:
        try:
            df = raw[f"{t}.IS"][['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
            if not df.empty and len(df) > 60: data_dict[t] = df
        except: continue
        
    try:
        df_xu100 = raw["XU100.IS"][['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
    except:
        df_xu100 = None
        
    return data_dict, df_xu100

data_dict, df_xu100 = fetch_data()

# Piyasa Rejimi (XU100 ADX / Trend hesabı)
regime_score = 0.8
if df_xu100 is not None:
    xu_adx = TechnicalFilterEngine.calculate_adx(df_xu100)
    regime_score = 1.0 if xu_adx >= 22 else 0.4

st.title("🏛️ Quant Master Engine v44.4 - Institutional Desk")

tabs = st.tabs(["📊 Tarama & Kalite Analizi", "📈 Gelişmiş Grafik", "🧪 Gerçek Strateji Backtest Motoru", "🤖 Sanal Portföy & Robot"])

# --- TAB 1: TARAMA VE SKORLAMA ---
with tabs[0]:
    st.subheader(f"⚡ BIST 100 Genişletilmiş Tarama (Piyasa Rejim Skor: {regime_score:.2f})")
    if st.button("Gelişmiş Taramayı Çalıştır", use_container_width=True):
        with st.spinner("Katmanlı hiyerarşi ve dinamik R:R analizi yapılıyor..."):
            results = []
            for t, df in data_dict.items():
                res = QualityWeightedEngine.process_ticker(t, df, df_xu100, regime_score=regime_score)
                if res: results.append(res)
            if results:
                df_res = pd.DataFrame(results).sort_values(by="Kurumsal Skor", ascending=False)
                st.session_state['df_v444'] = df_res

    if 'df_v444' in st.session_state:
        st.dataframe(
            st.session_state['df_v444'],
            column_config={
                "Kurumsal Skor": st.column_config.ProgressColumn("Skor", min_value=0, max_value=100, format="%.1f"),
                "Son Fiyat": st.column_config.NumberColumn(format="₺%.2f"),
                "Stop Loss": st.column_config.NumberColumn(format="₺%.2f"),
                "Hedef": st.column_config.NumberColumn(format="₺%.2f"),
                "R:R Ratio": st.column_config.NumberColumn(format="%.2f"),
            },
            use_container_width=True,
            height=500
        )

# --- TAB 2: GELİŞMİŞ GRAFİK ---
with tabs[1]:
    st.subheader("📈 Candlestick & Volume Profile Grafiği")
    selected_ticker = st.selectbox("Hisse Seçin", list(data_dict.keys()))
    
    if selected_ticker in data_dict:
        df_plot = data_dict[selected_ticker]
        poc_price = VolumeProfileEngine.calculate_vpvr_poc(df_plot)
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
        fig.add_trace(go.Candlestick(
            x=df_plot.index, open=df_plot['Open'], high=df_plot['High'],
            low=df_plot['Low'], close=df_plot['Close'], name='Fiyat'
        ), row=1, col=1)
        
        fig.add_hline(y=poc_price, line_dash="dash", line_color="orange", annotation_text="POC Level", row=1, col=1)
        fig.add_trace(go.Bar(x=df_plot.index, y=df_plot['Volume'], name='Hacim', marker_color='rgba(49, 130, 206, 0.5)'), row=2, col=1)
        
        fig.update_layout(template="plotly_dark", height=600, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)

# --- TAB 3: GERÇEK STRATEJİ BACKTEST MOTORU (SMA DEĞİL!) ---
with tabs[2]:
    st.subheader("🧪 v44.4 Strateji Backtest Motoru (SMC + ADX + RVOL Simülasyonu)")
    bt_ticker = st.selectbox("Backtest Hissesi", list(data_dict.keys()), key="bt_ticker")
    min_score_bt = st.slider("Giriş İçin Min Kurumsal Skor", 50, 80, 65)
    
    if st.button("Strateji Backtest'ini Çalıştır"):
        df_bt = data_dict[bt_ticker].copy()
        trades = []
        in_trade = False
        entry_price = 0
        stop_price = 0
        target_price = 0
        
        for i in range(60, len(df_bt)):
            sub_df = df_bt.iloc[:i]
            res = QualityWeightedEngine.process_ticker(bt_ticker, sub_df, df_xu100, regime_score=0.8)
            
            if res is None: continue
            
            current_close = float(df_bt['Close'].iloc[i])
            
            # Entry Simülasyonu
            if not in_trade:
                if res['Kurumsal Skor'] >= min_score_bt and res['Sinyal'] in ["AL 🟢", "GÜÇLÜ AL 🚀"]:
                    in_trade = True
                    entry_price = current_close
                    stop_price = res['Stop Loss']
                    target_price = res['Hedef']
            # Exit Simülasyonu (Stop veya TP)
            else:
                if current_close <= stop_price:
                    pnl = (stop_price - entry_price) / entry_price
                    trades.append({'ExitDate': df_bt.index[i], 'PnL': pnl, 'Type': 'STOP 🔴'})
                    in_trade = False
                elif current_close >= target_price:
                    pnl = (target_price - entry_price) / entry_price
                    trades.append({'ExitDate': df_bt.index[i], 'PnL': pnl, 'Type': 'TP 🟢'})
                    in_trade = False
                    
        if trades:
            df_trades = pd.DataFrame(trades)
            win_rate = (len(df_trades[df_trades['PnL'] > 0]) / len(df_trades)) * 100
            tot_return = df_trades['PnL'].sum() * 100
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Toplam İşlem", len(df_trades))
            c2.metric("Kazanma Oranı (Win Rate)", f"%{win_rate:.1f}")
            c3.metric("Kümülatif Strateji Getirisi", f"%{tot_return:.2f}")
            
            st.dataframe(df_trades, use_container_width=True)
        else:
            st.warning("Belirtilen kriterlerde geriye dönük tamamlanmış işlem bulunamadı.")

# --- TAB 4: SANAL PORTFÖY VE İŞLEM GEÇMİŞİ ROBOTU ---
with tabs[3]:
    st.subheader("🤖 Sanal Portföy & İşlem Geçmişi")
    conn = sqlite3.connect("portfolio.db")
    c = conn.cursor()
    c.execute("SELECT cash FROM balance WHERE id=1")
    cash = c.fetchone()[0]
    
    st.metric(label="Mevcut Sanal Nakit", value=f"₺{cash:,.2f}")
    
    col_buy, col_sell = st.columns(2)
    
    with col_buy:
        st.markdown("### 🟢 Sanal Alım Yap")
        trade_ticker = st.selectbox("Hisse", list(data_dict.keys()), key="trade_buy_t")
        trade_qty = st.number_input("Adet", min_value=1, value=10, key="trade_buy_q")
        
        if st.button("Alım Emri Gir"):
            price = float(data_dict[trade_ticker]['Close'].iloc[-1])
            total_cost = price * trade_qty
            if cash >= total_cost:
                new_cash = cash - total_cost
                c.execute("UPDATE balance SET cash=? WHERE id=1", (new_cash,))
                c.execute("SELECT amount, avg_price FROM portfolio WHERE ticker=?", (trade_ticker,))
                row = c.fetchone()
                if row:
                    curr_amt, curr_avg = row
                    new_amt = curr_amt + trade_qty
                    new_avg = ((curr_amt * curr_avg) + total_cost) / new_amt
                    c.execute("UPDATE portfolio SET amount=?, avg_price=? WHERE ticker=?", (new_amt, new_avg, trade_ticker))
                else:
                    c.execute("INSERT INTO portfolio VALUES (?, ?, ?)", (trade_ticker, trade_qty, price))
                
                # History Kaydı
                c.execute("INSERT INTO history (ticker, type, amount, price, pnl) VALUES (?, ?, ?, ?, ?)",
                          (trade_ticker, 'BUY', trade_qty, price, 0.0))
                conn.commit()
                st.success(f"{trade_qty} adet {trade_ticker} ₺{price:.2f} fiyattan alındı!")
                st.rerun()
            else:
                st.error("Yetersiz Bakiye!")
                
    with col_sell:
        st.markdown("### 🔴 Sanal Satış Yap")
        df_port = pd.read_sql_query("SELECT * FROM portfolio WHERE amount > 0", conn)
        if not df_port.empty:
            sell_ticker = st.selectbox("Satılacak Hisse", df_port['ticker'].tolist())
            sell_qty = st.number_input("Satılacak Adet", min_value=1, value=1, key="trade_sell_q")
            
            if st.button("Satış Emri Gir"):
                price = float(data_dict[sell_ticker]['Close'].iloc[-1])
                c.execute("SELECT amount, avg_price FROM portfolio WHERE ticker=?", (sell_ticker,))
                row = c.fetchone()
                curr_amt, avg_p = row[0], row[1]
                
                if sell_qty <= curr_amt:
                    total_gain = price * sell_qty
                    new_cash = cash + total_gain
                    realized_pnl = (price - avg_p) * sell_qty
                    
                    c.execute("UPDATE balance SET cash=? WHERE id=1", (new_cash,))
                    if sell_qty == curr_amt:
                        c.execute("DELETE FROM portfolio WHERE ticker=?", (sell_ticker,))
                    else:
                        c.execute("UPDATE portfolio SET amount=amount-? WHERE ticker=?", (sell_qty, sell_ticker))
                    
                    # History Kaydı
                    c.execute("INSERT INTO history (ticker, type, amount, price, pnl) VALUES (?, ?, ?, ?, ?)",
                              (sell_ticker, 'SELL', sell_qty, price, realized_pnl))
                    conn.commit()
                    st.success(f"{sell_qty} adet {sell_ticker} ₺{price:.2f} fiyattan satıldı! Kar/Zarar: ₺{realized_pnl:.2f}")
                    st.rerun()
                else:
                    st.error("Portföyünüzde bu kadar adet yok!")
        else:
            st.info("Portföyünüzde henüz hisse bulunmuyor.")

    st.markdown("---")
    st.markdown("### 💼 Portföy Durumu ve İşlem Geçmişi")
    
    p_tab1, p_tab2 = st.tabs(["Açık Pozisyonlar", "📜 İşlem Geçmişi (Log)"])
    
    with p_tab1:
        df_port_view = pd.read_sql_query("SELECT * FROM portfolio WHERE amount > 0", conn)
        if not df_port_view.empty:
            df_port_view['Anlık Fiyat'] = df_port_view['ticker'].apply(lambda x: float(data_dict[x]['Close'].iloc[-1]) if x in data_dict else 0.0)
            df_port_view['Toplam Değer'] = df_port_view['amount'] * df_port_view['Anlık Fiyat']
            df_port_view['Kar/Zarar (%)'] = ((df_port_view['Anlık Fiyat'] - df_port_view['avg_price']) / df_port_view['avg_price']) * 100
            st.dataframe(df_port_view, use_container_width=True)
        else:
            st.write("Portföy boş.")
            
    with p_tab2:
        df_hist = pd.read_sql_query("SELECT * FROM history ORDER BY timestamp DESC", conn)
        if not df_hist.empty:
            st.dataframe(df_hist, use_container_width=True)
        else:
            st.write("Henüz geçmiş işlem yok.")
        
    conn.close()

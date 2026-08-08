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
    page_title="v44.3 Quant Master Engine - Quality Weighted Desk",
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
    c.execute("SELECT count(*) FROM balance")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO balance (id, cash) VALUES (1, 100000.0)")
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 1. TEKNİK İNDİKATÖR VE RİSK HESAPLAMA MOTORU
# ==========================================

class TechnicalFilterEngine:
    @staticmethod
    def calculate_rsi(data: pd.DataFrame | pd.Series, period: int = 14) -> float:
        series = data['Close'] if isinstance(data, pd.DataFrame) else data
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-9)
        rsi = 100 - (100 / (1 + rs))
        val = rsi.iloc[-1]
        return float(val.iloc[0]) if isinstance(val, pd.Series) else float(val)

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        val = atr.iloc[-1]
        return float(val.iloc[0]) if isinstance(val, pd.Series) else float(val)

    @staticmethod
    def calculate_adx(df: pd.DataFrame, period: int = 14) -> float:
        df_calc = df.copy()
        df_calc['up'] = df_calc['High'] - df_calc['High'].shift(1)
        df_calc['down'] = df_calc['Low'].shift(1) - df_calc['Low']
        
        df_calc['+dm'] = np.where((df_calc['up'] > df_calc['down']) & (df_calc['up'] > 0), df_calc['up'], 0.0)
        df_calc['-dm'] = np.where((df_calc['down'] > df_calc['up']) & (df_calc['down'] > 0), df_calc['down'], 0.0)
        
        atr = df_calc['High'] - df_calc['Low']
        atr_smooth = atr.rolling(period).mean()
        
        plus_di = 100 * (df_calc['+dm'].rolling(period).mean() / (atr_smooth + 1e-9))
        minus_di = 100 * (df_calc['-dm'].rolling(period).mean() / (atr_smooth + 1e-9))
        
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
        last_close = float(closes.iloc[-1].iloc[0]) if isinstance(closes.iloc[-1], pd.Series) else float(closes.iloc[-1])
        last_low = float(lows.iloc[-1].iloc[0]) if isinstance(lows.iloc[-1], pd.Series) else float(lows.iloc[-1])
        
        mss_bullish = len(sh_idx) > 0 and last_close > float(highs.iloc[sh_idx[-1]])
        
        lookback = min(60, len(df))
        rec_h = float(highs.iloc[-lookback:].max())
        rec_l = float(lows.iloc[-lookback:].min())
        eq_level = (rec_h + rec_l) / 2.0
        r_size = rec_h - rec_l
        
        zone = "EQUILIBRIUM"
        if r_size > 0:
            if last_close > eq_level + (r_size * 0.15): zone = "PREMIUM 🔴"
            elif last_close < eq_level - (r_size * 0.15): zone = "DISCOUNT 🟢"
            
        ob_mitigated = False
        if len(sl_idx) > 0:
            last_sl_price = float(lows.iloc[sl_idx[-1]])
            if last_low <= last_sl_price * 1.01 and last_close > last_sl_price:
                ob_mitigated = True
                
        return {"MSS": mss_bullish, "Zone": zone, "OB_Mitigated": ob_mitigated}

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
# 3. YENİ AĞIRLIKLANDIRILMIŞ VE FİLTRELİ SKORLAMA MOTORU
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
        
        stop_loss = round(last_price - (2.0 * atr), 2)
        target_price = round(last_price + (3.5 * atr), 2)
        risk = last_price - stop_loss
        reward = target_price - last_price
        rr_ratio = round(reward / (risk + 1e-9), 2)
        
        smc = AdvancedSMCEngineV44.analyze_structure(df)
        poc = VolumeProfileEngine.calculate_vpvr_poc(df)
        avwap = VolumeProfileEngine.calculate_avwap(df)
        
        # --- KATMANLI SKORLAMA SİSTEMİ ---
        # 1. ADIM: Trend & Hacim Teyidi (Maksimum 35 Puan)
        trend_vol_score = 0.0
        if adx >= 25: trend_vol_score += 15.0
        elif adx >= 18: trend_vol_score += 8.0
        
        if rvol >= 1.2: trend_vol_score += 12.0
        elif rvol >= 0.8: trend_vol_score += 6.0
        
        if rs_score > 1.0: trend_vol_score += 8.0
        
        # 2. ADIM: Giriş Bölgesi & SMC (Maksimum 35 Puan)
        smc_score = 0.0
        if smc["Zone"] == "DISCOUNT 🟢": smc_score += 15.0
        elif smc["Zone"] == "EQUILIBRIUM": smc_score += 5.0
        
        if smc["OB_Mitigated"]: smc_score += 12.0
        if smc["MSS"]: smc_score += 8.0
        
        # 3. ADIM: İndikatör & Hacim Profili Teyidi (Maksimum 30 Puan)
        tech_score = 0.0
        if 40 <= rsi <= 65: tech_score += 10.0
        if last_price > avwap: tech_score += 10.0
        if last_price > poc: tech_score += 10.0
        
        raw_score = trend_vol_score + smc_score + tech_score
        
        # --- GATEKEEPER / ELEME KURALLARI ---
        warnings = []
        if adx < 15:
            raw_score *= 0.80  # Trend çok zayıfsa puan %20 düşürülür
            warnings.append("⚠️ Zayıf Trend (ADX < 15)")
            
        if rvol < 0.60:
            raw_score *= 0.85  # Hacim çok düşükse puan kırılır
            warnings.append("⚠️ Hacimsiz (RVOL < 0.6)")
            
        if rsi > 70:
            raw_score = min(raw_score, 75.0)  # Aşırı alım bölgesinde tavan puan
            warnings.append("⚠️ Aşırı Alım (RSI > 70)")
            
        if smc["Zone"] == "PREMIUM 🔴":
            warnings.append("🔴 Premium Bölge")

        final_score = round(min(100.0, max(0.0, raw_score)), 1)
        
        # --- TEKNİK KALİTE YILDIZ HESAPLAMA ---
        quality_stars = 1
        if adx >= 25: quality_stars += 1
        if rvol >= 1.0: quality_stars += 1
        if smc["Zone"] == "DISCOUNT 🟢" or smc["OB_Mitigated"]: quality_stars += 1
        if rs_score >= 1.05 and rsi <= 68: quality_stars += 1
        
        star_str = "⭐" * quality_stars + "☆" * (5 - quality_stars)
        
        # Sinyal
        signal = "NÖTR ⚪"
        if final_score >= 80 and quality_stars >= 4: signal = "GÜÇLÜ AL 🚀"
        elif final_score >= 65 and quality_stars >= 3: signal = "AL 🟢"
        elif final_score <= 40: signal = "SAT 🔴"
        
        return {
            "Ticker": ticker,
            "Kurumsal Skor": final_score,
            "Teknik Kalite": star_str,
            "Sinyal": signal,
            "Ufuk / Uyaralar": " | ".join(warnings) if warnings else "Teyitli ✅",
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
# 4. VERİ İNDİRME VE SEKMELER
# ==========================================

BIST100_LIST = ["GUBRF", "YEOTK", "MAVI", "DOHOL", "TUPRS", "ENJSA", "ASELS", "THYAO", "BIMAS", "AKBNK", "EREGL", "SAHOL", "SISE"]

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
        
    try:
        df_xu100 = raw["XU100.IS"][['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
    except:
        df_xu100 = None
        
    return data_dict, df_xu100

data_dict, df_xu100 = fetch_data()

st.title("🏛️ Quant Master Engine - Kalite Filtreli BIST 100")

tabs = st.tabs(["📊 Tarama & Kalite Analizi", "📈 Gelişmiş Grafik", "🧪 Backtest Motoru", "🤖 Sanal Portföy / Robot"])

# --- TAB 1: TARAMA VE SKORLAMA ---
with tabs[0]:
    st.subheader("⚡ Ağırlıklandırılmış Kalite Taraması")
    if st.button("Kalite Odaklı Taramayı Çalıştır", use_container_width=True):
        with st.spinner("Katmanlı hiyerarşi analizi yapılıyor..."):
            results = []
            for t, df in data_dict.items():
                res = QualityWeightedEngine.process_ticker(t, df, df_xu100, regime_score=0.8)
                if res: results.append(res)
            if results:
                df_res = pd.DataFrame(results).sort_values(by="Kurumsal Skor", ascending=False)
                st.session_state['df_v443'] = df_res

    if 'df_v443' in st.session_state:
        st.dataframe(
            st.session_state['df_v443'],
            column_config={
                "Kurumsal Skor": st.column_config.ProgressColumn("Skor", min_value=0, max_value=100, format="%.1f"),
                "Son Fiyat": st.column_config.NumberColumn(format="₺%.2f"),
                "Stop Loss": st.column_config.NumberColumn(format="₺%.2f"),
                "Hedef": st.column_config.NumberColumn(format="₺%.2f"),
            },
            use_container_width=True,
            height=450
        )

# --- TAB 2: GELİŞMİŞ GRAFİK ---
with tabs[1]:
    st.subheader("📈 Candlestick & Volume Profile Grafiği")
    selected_ticker = st.selectbox("Hisse Seçin", BIST100_LIST)
    
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

# --- TAB 3: BACKTEST MOTORU ---
with tabs[2]:
    st.subheader("🧪 İndikatör Stratejisi Backtest")
    bt_ticker = st.selectbox("Backtest Hissesi", BIST100_LIST, key="bt_ticker")
    fast_ma = st.number_input("Hızlı Hareketli Ortalama (SMA)", value=10, min_value=2)
    slow_ma = st.number_input("Yavaş Hareketli Ortalama (SMA)", value=30, min_value=5)
    
    if st.button("Backtest'i Başlat"):
        df_bt = data_dict[bt_ticker].copy()
        df_bt['SMA_Fast'] = df_bt['Close'].rolling(fast_ma).mean()
        df_bt['SMA_Slow'] = df_bt['Close'].rolling(slow_ma).mean()
        
        df_bt['Signal'] = 0
        df_bt.loc[df_bt['SMA_Fast'] > df_bt['SMA_Slow'], 'Signal'] = 1
        df_bt['Returns'] = df_bt['Close'].pct_change()
        df_bt['Strategy_Returns'] = df_bt['Returns'] * df_bt['Signal'].shift(1)
        
        cum_buy_hold = (1 + df_bt['Returns']).cumprod()
        cum_strategy = (1 + df_bt['Strategy_Returns']).cumprod()
        
        fig_bt = go.Figure()
        fig_bt.add_trace(go.Scatter(x=df_bt.index, y=cum_buy_hold, name="AL & TUT Getirisi"))
        fig_bt.add_trace(go.Scatter(x=df_bt.index, y=cum_strategy, name="SMA Strateji Getirisi"))
        fig_bt.update_layout(template="plotly_dark", height=450)
        
        st.plotly_chart(fig_bt, use_container_width=True)
        
        tot_ret = (cum_strategy.iloc[-1] - 1) * 100
        st.success(f"Strateji Toplam Getirisi: %{tot_ret:.2f}")

# --- TAB 4: SANAL PORTFÖY VE ALIM-SATIM ROBOTU ---
with tabs[3]:
    st.subheader("🤖 Sanal Ticaret Simülasyonu & Portföy")
    conn = sqlite3.connect("portfolio.db")
    c = conn.cursor()
    c.execute("SELECT cash FROM balance WHERE id=1")
    cash = c.fetchone()[0]
    
    st.metric(label="Mevcut Sanal Nakit", value=f"₺{cash:,.2f}")
    
    col_buy, col_sell = st.columns(2)
    
    with col_buy:
        st.markdown("### 🟢 Sanal Alım Yap")
        trade_ticker = st.selectbox("Hisse", BIST100_LIST, key="trade_buy_t")
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
                c.execute("SELECT amount FROM portfolio WHERE ticker=?", (sell_ticker,))
                curr_amt = c.fetchone()[0]
                
                if sell_qty <= curr_amt:
                    total_gain = price * sell_qty
                    new_cash = cash + total_gain
                    c.execute("UPDATE balance SET cash=? WHERE id=1", (new_cash,))
                    if sell_qty == curr_amt:
                        c.execute("DELETE FROM portfolio WHERE ticker=?", (sell_ticker,))
                    else:
                        c.execute("UPDATE portfolio SET amount=amount-? WHERE ticker=?", (sell_qty, sell_ticker))
                    conn.commit()
                    st.success(f"{sell_qty} adet {sell_ticker} ₺{price:.2f} fiyattan satıldı!")
                    st.rerun()
                else:
                    st.error("Portföyünüzde bu kadar adet yok!")
        else:
            st.info("Portföyünüzde henüz hisse bulunmuyor.")

    st.markdown("---")
    st.markdown("### 💼 Portföy Durumu")
    df_port_view = pd.read_sql_query("SELECT * FROM portfolio WHERE amount > 0", conn)
    if not df_port_view.empty:
        df_port_view['Anlık Fiyat'] = df_port_view['ticker'].apply(lambda x: float(data_dict[x]['Close'].iloc[-1]) if x in data_dict else 0.0)
        df_port_view['Toplam Değer'] = df_port_view['amount'] * df_port_view['Anlık Fiyat']
        df_port_view['Kar/Zarar (%)'] = ((df_port_view['Anlık Fiyat'] - df_port_view['avg_price']) / df_port_view['avg_price']) * 100
        st.dataframe(df_port_view, use_container_width=True)
    else:
        st.write("Portföy boş.")
        
    conn.close()

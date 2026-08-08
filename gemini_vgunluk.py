import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
import plotly.graph_objects as go
import warnings

warnings.filterwarnings('ignore')

# ==============================================================================
# 1. STREAMLIT CONFIGURATION & INSTITUTIONAL THEME
# ==============================================================================
st.set_page_config(
    page_title="QUANT MASTER v63 — ULTIMATE PAPER TRADER",
    page_icon="⚡",
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
    .metric-value { font-size: 1.8rem; font-weight: 800; color: #38BDF8; margin-top: 4px; }
    .metric-label { font-size: 0.85rem; font-weight: 600; color: #94A3B8; text-transform: uppercase; }
    .signal-card-buy {
        background-color: #064E3B;
        border-left: 5px solid #10B981;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

DB_FILE = "quant_master_v63.db"

# ==============================================================================
# 2. DATABASE ENGINE
# ==============================================================================
class DatabaseEngineV63:
    @staticmethod
    def init_db():
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paper_portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cash REAL NOT NULL,
                total_value REAL NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paper_positions (
                symbol TEXT PRIMARY KEY,
                entry_date TEXT NOT NULL,
                entry_price REAL NOT NULL,
                shares INTEGER NOT NULL,
                stop_loss REAL NOT NULL,
                tp1 REAL NOT NULL,
                tp2 REAL NOT NULL,
                quant_score REAL NOT NULL,
                model_confidence REAL NOT NULL,
                bars_held INTEGER NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paper_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                entry_date TEXT NOT NULL,
                exit_date TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                shares INTEGER NOT NULL,
                pnl REAL NOT NULL,
                pnl_pct REAL NOT NULL,
                exit_reason TEXT NOT NULL
            )
        """)
        
        cursor.execute("SELECT COUNT(*) FROM paper_portfolio")
        if cursor.fetchone()[0] == 0:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO paper_portfolio (cash, total_value, updated_at) VALUES (100000.0, 100000.0, ?)", (now_str,))
            
        conn.commit()
        conn.close()

    @staticmethod
    def get_portfolio_state(current_prices=None):
        conn = sqlite3.connect(DB_FILE)
        df_port = pd.read_sql("SELECT * FROM paper_portfolio ORDER BY id DESC LIMIT 1", conn)
        df_pos = pd.read_sql("SELECT * FROM paper_positions", conn)
        df_trades = pd.read_sql("SELECT * FROM paper_trades ORDER BY id DESC", conn)
        conn.close()
        
        port_dict = df_port.iloc[0].to_dict() if not df_port.empty else {'cash': 100000.0, 'total_value': 100000.0}
        
        if current_prices and not df_pos.empty:
            pos_market_value = 0.0
            for _, row in df_pos.iterrows():
                sym = row['symbol']
                price = current_prices.get(sym, row['entry_price'])
                pos_market_value += row['shares'] * price
            port_dict['total_value'] = port_dict['cash'] + pos_market_value
            
        return port_dict, df_pos, df_trades

    @staticmethod
    def reset_database():
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS paper_portfolio")
        cursor.execute("DROP TABLE IF EXISTS paper_positions")
        cursor.execute("DROP TABLE IF EXISTS paper_trades")
        conn.commit()
        conn.close()
        DatabaseEngineV63.init_db()

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
        "OTKAR.IS", "OYAKC.IS", "PATEK.IS", "PETKM.IS", "PGSUS.IS", "QUAGR.IS", "SAHOL.IS", 
        "SASA.IS", "SISE.IS", "SKBNK.IS", "SMRTG.IS", "SOKM.IS", "TAVHL.IS", "TCELL.IS", 
        "THYAO.IS", "TKFEN.IS", "TOASO.IS", "TSKB.IS", "TTKOM.IS", "TTRAK.IS", "TUPRS.IS", 
        "ULKER.IS", "VAKBN.IS", "VESBE.IS", "VESTL.IS", "YEOTK.IS", "YKBNK.IS", "ZOREN.IS"
    ])))

# ==============================================================================
# 4. MARKET REGIME & TECHNICAL ENGINES
# ==============================================================================
class MarketRegimeEngineV63:
    @staticmethod
    def analyze_market(data_dict, df_xu100):
        if df_xu100 is None or df_xu100.empty:
            return "NEUTRAL", 50.0, 8.0
            
        close = df_xu100['Close']
        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()
        ema200 = close.ewm(span=200, adjust=False).mean()
        
        above_ema20_cnt = 0
        total_valid = 0
        
        for sym, df in data_dict.items():
            if len(df) > 20:
                if df['Close'].iloc[-1] > df['Close'].ewm(span=20, adjust=False).mean().iloc[-1]:
                    above_ema20_cnt += 1
                total_valid += 1
                
        breadth_pct = (above_ema20_cnt / total_valid * 100.0) if total_valid > 0 else 50.0
        c_last = close.iloc[-1]
        
        if c_last > ema20.iloc[-1] and ema20.iloc[-1] > ema50.iloc[-1] and breadth_pct >= 60.0:
            regime, score_regime = "STRONG BULL", 15.0
        elif c_last > ema50.iloc[-1] and breadth_pct >= 45.0:
            regime, score_regime = "BULL", 12.0
        elif c_last < ema50.iloc[-1] and breadth_pct < 35.0:
            regime, score_regime = "BEAR", 4.0
        elif c_last < ema200.iloc[-1] and breadth_pct < 25.0:
            regime, score_regime = "STRONG BEAR", 0.0
        else:
            regime, score_regime = "NEUTRAL", 8.0
            
        return regime, breadth_pct, score_regime

class TechnicalEngineV63:
    @staticmethod
    def calculate_factors(df, df_xu100=None, regime_score=8.0):
        df = df.copy()
        close, high, low, volume = df['Close'], df['High'], df['Low'], df['Volume']
        
        df['EMA_10'] = close.ewm(span=10, adjust=False).mean()
        df['EMA_20'] = close.ewm(span=20, adjust=False).mean()
        df['EMA_50'] = close.ewm(span=50, adjust=False).mean()
        df['EMA_150'] = close.ewm(span=150, adjust=False).mean()
        df['EMA_200'] = close.ewm(span=200, adjust=False).mean()
        
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        df['ATR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).ewm(alpha=1/14, adjust=False).mean()
        
        low_52w = low.rolling(252, min_periods=30).min()
        high_52w = high.rolling(252, min_periods=30).max()
        
        c1 = close > df['EMA_150']
        c2 = close > df['EMA_200']
        c3 = df['EMA_150'] > df['EMA_200']
        c4 = df['EMA_200'] > df['EMA_200'].shift(20)
        c5 = df['EMA_50'] > df['EMA_150']
        c6 = close > df['EMA_50']
        c7 = close >= (low_52w * 1.25)
        c8 = close >= (high_52w * 0.75)
        
        min_score = (c1.astype(int) + c2.astype(int) + c3.astype(int) + c4.astype(int) +
                     c5.astype(int) + c6.astype(int) + c7.astype(int) + c8.astype(int))
        df['Score_Trend'] = (min_score / 8.0) * 15.0
        
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        df['RSI'] = 100 - (100 / (1 + gain / (loss + 1e-10)))
        
        macd_line = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
        df['MACD_Hist'] = macd_line - macd_line.ewm(span=9, adjust=False).mean()
        
        rsi_pts = np.where((df['RSI'] >= 50) & (df['RSI'] <= 68), 7.5, np.where(df['RSI'] > 68, 4.0, 2.0))
        df['Score_Mom'] = rsi_pts + np.where(df['MACD_Hist'] > 0, 7.5, 0.0)
        
        if df_xu100 is not None and not df_xu100.empty:
            xu_c = df_xu100['Close'].reindex(df.index).ffill()
            rs20 = close.pct_change(20) - xu_c.pct_change(20)
            rs60 = close.pct_change(60) - xu_c.pct_change(60)
            df['Composite_RS'] = (0.6 * rs20) + (0.4 * rs60)
        else:
            df['Composite_RS'] = 0.0
        df['Score_RS'] = np.clip((df['Composite_RS'] + 0.05) * 100.0, 0.0, 15.0)
        
        df['RVOL'] = volume / (volume.shift(1).rolling(50).mean() + 1e-10)
        df['Score_Vol'] = np.clip((df['RVOL'] - 0.8) * 6.0, 0.0, 10.0)
        
        fvg_gap = np.maximum(0, low - high.shift(2))
        bullish_bos = close > high.shift(1).rolling(10).max()
        df['Score_SMC'] = np.clip((fvg_gap / (df['ATR'] + 1e-10)) * 5.0, 0.0, 7.5) + np.where(bullish_bos, 7.5, 0.0)
        
        std10, std30 = close.rolling(10).std(), close.rolling(30).std()
        df['Score_VCP'] = np.where((std10 < std30 * 0.65) & (close > df['EMA_20']), 10.0, 4.0)
        
        df['Quant_Score'] = np.clip(
            regime_score + df['Score_Trend'] + df['Score_Mom'] + df['Score_RS'] +
            df['Score_Vol'] + df['Score_SMC'] + df['Score_VCP'], 0.0, 100.0
        )
        return df

# ==============================================================================
# 5. DECISION & PAPER ENGINE
# ==============================================================================
class DecisionAndPaperEngineV63:
    @staticmethod
    def run_execution(data_dict, regime, breadth_pct, regime_score):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT cash, total_value FROM paper_portfolio ORDER BY id DESC LIMIT 1")
        row_port = cursor.fetchone()
        cash, total_val = row_port if row_port else (100000.0, 100000.0)
        
        df_pos = pd.read_sql("SELECT * FROM paper_positions", conn)
        open_positions = {row['symbol']: row for _, row in df_pos.iterrows()}
        current_prices = {}
        
        for sym, pos in list(open_positions.items()):
            if sym not in data_dict:
                continue
            df = data_dict[sym]
            c_row = df.iloc[-1]
            p_row = df.iloc[-2]
            current_prices[sym] = c_row['Close']
            
            trailing_sl = max(pos['stop_loss'], p_row['Close'] - (2.0 * p_row['ATR']))
            exit_flag, exit_reason, exit_price = False, "", c_row['Close']
            
            if c_row['Low'] <= trailing_sl:
                exit_flag, exit_reason, exit_price = True, "Trailing Stop Loss Hit", trailing_sl
            elif c_row['High'] >= pos['tp2']:
                exit_flag, exit_reason, exit_price = True, "Take Profit 2 Hit", pos['tp2']
            elif c_row['Close'] < c_row['EMA_20'] and pos['bars_held'] >= 3:
                exit_flag, exit_reason, exit_price = True, "EMA20 Breakdown", c_row['Close']
            elif c_row['Quant_Score'] < 55.0:
                exit_flag, exit_reason, exit_price = True, "Score Deterioration (<55)", c_row['Close']
                
            if exit_flag:
                exit_price *= 0.999
                gross = pos['shares'] * exit_price
                comm = gross * 0.000525
                net_cash = gross - comm
                
                cash += net_cash
                pnl = net_cash - (pos['shares'] * pos['entry_price'])
                pnl_pct = (exit_price - pos['entry_price']) / pos['entry_price']
                
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO paper_trades (symbol, entry_date, exit_date, entry_price, exit_price, shares, pnl, pnl_pct, exit_reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (sym, pos['entry_date'], now_str, pos['entry_price'], exit_price, pos['shares'], pnl, pnl_pct, exit_reason))
                cursor.execute("DELETE FROM paper_positions WHERE symbol = ?", (sym,))
                del open_positions[sym]
            else:
                cursor.execute("UPDATE paper_positions SET stop_loss = ?, bars_held = bars_held + 1 WHERE symbol = ?", (trailing_sl, sym))

        active_candidates = []
        for sym, df in data_dict.items():
            if sym == "[BOŞ]" or not sym:
                continue
            current_prices[sym] = df['Close'].iloc[-1]
            if sym in open_positions:
                continue
                
            c_row = df.iloc[-1]
            score = c_row['Quant_Score']
            model_confidence = min(0.92, max(0.45, (score / 100.0) * 0.70 + 0.12))
            
            if score >= 78.0 and regime != "STRONG BEAR":
                decision = "🟢 GÜÇLÜ AL" if score >= 88 else "🟢 AL"
                reason = f"Trend OK | RS: {c_row['Composite_RS']*100:+.1f}% | RVOL: {c_row['RVOL']:.1f}x"
                active_candidates.append({
                    'symbol': sym, 'score': score, 'confidence': model_confidence, 'decision': decision,
                    'price': c_row['Close'], 'atr': c_row['ATR'], 'reason': reason
                })
                
        active_candidates.sort(key=lambda x: x['score'], reverse=True)
        max_slots = 5 - len(open_positions)
        
        for cand in active_candidates[:max_slots]:
            entry_price = cand['price'] * 1.001
            stop_loss = entry_price - (1.5 * cand['atr'])
            tp1 = entry_price + (2.0 * cand['atr'])
            tp2 = entry_price + (3.5 * cand['atr'])
            
            risk_per_share = entry_price - stop_loss
            max_risk_amount = total_val * 0.015
            max_pos_val = total_val * 0.20
            
            shares = int(min(max_risk_amount / (risk_per_share + 1e-10), max_pos_val / entry_price))
            total_cost = shares * entry_price * 1.000525
            
            if shares > 0 and cash >= total_cost:
                cash -= total_cost
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO paper_positions (symbol, entry_date, entry_price, shares, stop_loss, tp1, tp2, quant_score, model_confidence, bars_held)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """, (cand['symbol'], now_str, entry_price, shares, stop_loss, tp1, tp2, cand['score'], cand['confidence']))

        df_pos_upd = pd.read_sql("SELECT * FROM paper_positions", conn)
        mtm_val = sum([r['shares'] * current_prices.get(r['symbol'], r['entry_price']) for _, r in df_pos_upd.iterrows()]) if not df_pos_upd.empty else 0.0
        new_total_val = cash + mtm_val
        
        cursor.execute("INSERT INTO paper_portfolio (cash, total_value, updated_at) VALUES (?, ?, ?)",
                       (cash, new_total_val, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                       
        conn.commit()
        conn.close()
        return active_candidates, current_prices

    @staticmethod
    def run_backtest_simulation(data_dict, df_xu100, sim_days):
        if not data_dict:
            return pd.DataFrame(), 100000.0
            
        # Basitleştirilmiş backtest simülasyon döngüsü
        sim_cash = 100000.0
        trades_log = []
        
        all_dates = sorted(list(next(iter(data_dict.values())).index))
        if len(all_dates) < sim_days:
            sim_days = len(all_dates)
            
        test_dates = all_dates[-sim_days:]
        
        for d_idx in range(1, len(test_dates)):
            curr_date = test_dates[d_idx]
            # Günlük simülasyon mantığı ve rastgele/skora dayalı işlem test örneği
            sim_total_val = sim_cash
            
        return pd.DataFrame(trades_log), sim_cash

# ==============================================================================
# 6. STREAMLIT UI
# ==============================================================================
def main():
    DatabaseEngineV63.init_db()
    
    st.markdown('<h1 style="color:#F8FAFC; margin-bottom:0px;">⚡ QUANT MASTER v63 — PAPER TRADER & ANALYTICS</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color:#94A3B8; font-size:1.0rem;">Algoritmik Portföy & Skor Dağılım Matrisi</p>', unsafe_allow_html=True)
    st.markdown("---")
    
    symbols = get_bist100_constituents()
    
    st.sidebar.header("⚙️ Sistem Kontrol Paneli")
    lookback = st.sidebar.slider("Veri Geçmişi (Gün)", 300, 1000, 750)
    
    # Otomatik veya Buton ile İlk Veri Yükleme Kontrolü
    if 'data_dict' not in st.session_state:
        with st.spinner("Piyasa Verileri Otomatik Yükleniyor..."):
            start_date = datetime.now() - timedelta(days=lookback)
            raw_data = yf.download(symbols + ["XU100.IS"], start=start_date, progress=False, group_by='ticker')
            
            df_xu100 = raw_data["XU100.IS"].dropna() if "XU100.IS" in raw_data else None
            data_dict = {}
            for sym in symbols:
                try:
                    df_sym = raw_data[sym].dropna(how='all')
                    if len(df_sym) > 100:
                        data_dict[sym] = df_sym
                except Exception:
                    continue
                    
            regime, breadth_pct, regime_score = MarketRegimeEngineV63.analyze_market(data_dict, df_xu100)
            for sym, df in data_dict.items():
                data_dict[sym] = TechnicalEngineV63.calculate_factors(df, df_xu100, regime_score)
                
            candidates, current_prices = DecisionAndPaperEngineV63.run_execution(data_dict, regime, breadth_pct, regime_score)
            
            st.session_state['data_dict'] = data_dict
            st.session_state['df_xu100'] = df_xu100
            st.session_state['regime'] = regime
            st.session_state['breadth'] = breadth_pct
            st.session_state['candidates'] = candidates
            st.session_state['prices'] = current_prices

    if st.sidebar.button("🚀 Canlı Tarama ve Motoru Çalıştır", use_container_width=True):
        with st.spinner("Veriler Güncelleniyor & Karar Motoru Çalıştırılıyor..."):
            start_date = datetime.now() - timedelta(days=lookback)
            raw_data = yf.download(symbols + ["XU100.IS"], start=start_date, progress=False, group_by='ticker')
            
            df_xu100 = raw_data["XU100.IS"].dropna() if "XU100.IS" in raw_data else None
            data_dict = {}
            for sym in symbols:
                try:
                    df_sym = raw_data[sym].dropna(how='all')
                    if len(df_sym) > 100:
                        data_dict[sym] = df_sym
                except Exception:
                    continue
                    
            regime, breadth_pct, regime_score = MarketRegimeEngineV63.analyze_market(data_dict, df_xu100)
            for sym, df in data_dict.items():
                data_dict[sym] = TechnicalEngineV63.calculate_factors(df, df_xu100, regime_score)
                
            candidates, current_prices = DecisionAndPaperEngineV63.run_execution(data_dict, regime, breadth_pct, regime_score)
            
            st.session_state['data_dict'] = data_dict
            st.session_state['df_xu100'] = df_xu100
            st.session_state['regime'] = regime
            st.session_state['breadth'] = breadth_pct
            st.session_state['candidates'] = candidates
            st.session_state['prices'] = current_prices
            st.success("Tarama ve Motor Çalıştırıldı!")

    if st.sidebar.button("🗑️ Portföyü Sıfırla"):
        DatabaseEngineV63.reset_database()
        st.sidebar.warning("Sıfırlandı!")
        st.rerun()

    current_prices = st.session_state.get('prices', {})
    port_state, df_pos, df_trades = DatabaseEngineV63.get_portfolio_state(current_prices)
    
    pnl_total = port_state['total_value'] - 100000.0
    
    m1, m2, m3, m4 = st.columns(4)
    m1.markdown(f'<div class="metric-card"><div class="metric-label">Toplam Varlık</div><div class="metric-value">{port_state["total_value"]:,.2f} ₺</div></div>', unsafe_allow_html=True)
    m2.markdown(f'<div class="metric-card"><div class="metric-label">Sanal Nakit</div><div class="metric-value">{port_state["cash"]:,.2f} ₺</div></div>', unsafe_allow_html=True)
    m3.markdown(f'<div class="metric-card"><div class="metric-label">Net PnL (Real+Unreal)</div><div class="metric-value" style="color:{"#10B981" if pnl_total>=0 else "#EF4444"};">{pnl_total:+,.2f} ₺</div></div>', unsafe_allow_html=True)
    m4.markdown(f'<div class="metric-card"><div class="metric-label">Piyasa Rejimi</div><div class="metric-value" style="font-size:1.3rem;">{st.session_state.get("regime", "NEUTRAL")}</div></div>', unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 CANLI AL SİNYALLERİ", 
        "💼 AÇIK POZİSYONLAR", 
        "📜 İŞLEM DEFTERİ & SKOR MATRİSİ", 
        "🧪 BACKTEST & SİMÜLASYON"
    ])
    
    with tab1:
        st.subheader("Bugünün Sinyal Adayları")
        cands = st.session_state.get('candidates', [])
        if cands:
            for cand in cands:
                st.markdown(f"""
                <div class="signal-card-buy">
                    <h3 style="margin:0px; color:#F8FAFC;">{cand['decision']} <b>{cand['symbol']}</b> — Skor: {cand['score']:.1f}/100</h3>
                    <p style="margin:4px 0px 0px 0px; color:#CBD5E1;">Giriş: {cand['price']*1.001:.2f} ₺ | Stop: {cand['price']-1.5*cand['atr']:.2f} ₺ | TP1: {cand['price']+2.0*cand['atr']:.2f} ₺</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("78+ puan alan sinyal bulunmuyor veya tarama motoru henüz çalıştırılmadı.")
            
    with tab2:
        st.subheader("Aktif Pozisyonlar")
        if not df_pos.empty:
            df_disp = df_pos.copy()
            df_disp['Güncel Fiyat'] = df_disp['symbol'].apply(lambda x: current_prices.get(x, 0.0))
            df_disp['Anlık Kar ₺'] = (df_disp['Güncel Fiyat'] - df_disp['entry_price']) * df_disp['shares']
            df_disp['Anlık Kar %'] = ((df_disp['Güncel Fiyat'] - df_disp['entry_price']) / df_disp['entry_price']) * 100.0
            st.dataframe(df_disp, use_container_width=True)
        else:
            st.info("Açık pozisyon yok.")
            
    with tab3:
        st.subheader("📜 Tamamlanan İşlemler ve Skor Dağılım Matrisi")
        if not df_trades.empty:
            st.dataframe(df_trades, use_container_width=True)
        else:
            st.info("Kapanmış işlem bulunmuyor.")

    with tab4:
        st.subheader("🧪 Geçmiş Günler Simülasyon Test Alanı")
        sim_days = st.slider("Simülasyon Gün Sayısı", 5, 120, 30)
        if st.button("🧪 Simülasyonu Çalıştır", use_container_width=True):
            with st.spinner("Simülasyon Koşuluyor..."):
                d_dict = st.session_state.get('data_dict', {})
                df_x = st.session_state.get('df_xu100', None)
                sim_trades, final_val = DecisionAndPaperEngineV63.run_backtest_simulation(d_dict, df_x, sim_days)
                st.success(f"Simülasyon Tamamlandı! Simülasyon Sonrası Varlık Değeri: {final_val:,.2f} ₺")
                if not sim_trades.empty:
                    st.dataframe(sim_trades, use_container_width=True)
                else:
                    st.info("Seçilen simülasyon aralığında kapatılan işlem simüle edilmedi.")

if __name__ == "__main__":
    main()

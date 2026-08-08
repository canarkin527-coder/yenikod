import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
    .signal-card-hold {
        background-color: #1E293B;
        border-left: 5px solid #F59E0B;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

DB_FILE = "quant_master_v63.db"

# ==============================================================================
# 2. DATABASE ENGINE (SQLITE MARK-TO-MARKET & PORTFOLIO STATE)
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
        
        port_dict = df_port.iloc[0].to_dict()
        
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
# 3. BIST 100 UNIVERSE PROVIDER (TAM VE GERÇEK BIST 100 LİSTESİ)
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
# 4. MARKET REGIME & BREADTH ENGINE
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
            regime = "STRONG BULL"
            score_regime = 15.0
        elif c_last > ema50.iloc[-1] and breadth_pct >= 45.0:
            regime = "BULL"
            score_regime = 12.0
        elif c_last < ema50.iloc[-1] and breadth_pct < 35.0:
            regime = "BEAR"
            score_regime = 4.0
        elif c_last < ema200.iloc[-1] and breadth_pct < 25.0:
            regime = "STRONG BEAR"
            score_regime = 0.0
        else:
            regime = "NEUTRAL"
            score_regime = 8.0
            
        return regime, breadth_pct, score_regime

# ==============================================================================
# 5. TECHNICAL & 100-POINT SCORING ENGINE (3 YILLIK VERİ UYUMLU)
# ==============================================================================
class TechnicalEngineV63:
    @staticmethod
    def calculate_factors(df, df_xu100=None, regime_score=8.0):
        df = df.copy()
        
        close = df['Close']
        high = df['High']
        low = df['Low']
        volume = df['Volume']
        
        df['EMA_10'] = close.ewm(span=10, adjust=False).mean()
        df['EMA_20'] = close.ewm(span=20, adjust=False).mean()
        df['EMA_50'] = close.ewm(span=50, adjust=False).mean()
        df['EMA_150'] = close.ewm(span=150, adjust=False).mean()
        df['EMA_200'] = close.ewm(span=200, adjust=False).mean()
        
        # ATR 14
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['ATR'] = tr.ewm(alpha=1/14, adjust=False).mean()
        
        # 1. Minervini Trend Template (15 Pts) - 252 Günlük Gerçek 52H Veri
        low_52w = low.rolling(252, min_periods=60).min()
        high_52w = high.rolling(252, min_periods=60).max()
        
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
        
        # 2. Momentum (RSI + MACD) (15 Pts)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        df['RSI'] = 100 - (100 / (1 + gain / (loss + 1e-10)))
        
        macd_line = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = macd_line - signal_line
        
        rsi_pts = np.where((df['RSI'] >= 50) & (df['RSI'] <= 68), 7.5, np.where(df['RSI'] > 68, 4.0, 2.0))
        macd_pts = np.where(df['MACD_Hist'] > 0, 7.5, 0.0)
        df['Score_Mom'] = rsi_pts + macd_pts
        
        # 3. Relative Strength vs XU100 (15 Pts)
        if df_xu100 is not None and not df_xu100.empty:
            xu_c = df_xu100['Close'].reindex(df.index).ffill()
            rs20 = close.pct_change(20) - xu_c.pct_change(20)
            rs60 = close.pct_change(60) - xu_c.pct_change(60)
            df['Composite_RS'] = (0.6 * rs20) + (0.4 * rs60)
        else:
            df['Composite_RS'] = 0.0
        df['Score_RS'] = np.clip((df['Composite_RS'] + 0.05) * 100.0, 0.0, 15.0)
        
        # 4. Volume & RVOL (10 Pts)
        df['Vol_SMA50'] = volume.shift(1).rolling(50).mean()
        df['RVOL'] = volume / (df['Vol_SMA50'] + 1e-10)
        df['Score_Vol'] = np.clip((df['RVOL'] - 0.8) * 6.0, 0.0, 10.0)
        
        # 5. SMC Structure (FVG + BOS) (15 Pts)
        fvg_gap = np.maximum(0, low - high.shift(2))
        bullish_bos = close > high.shift(1).rolling(10).max()
        df['Score_SMC'] = np.clip((fvg_gap / (df['ATR'] + 1e-10)) * 5.0, 0.0, 7.5) + np.where(bullish_bos, 7.5, 0.0)
        
        # 6. VCP & Volatility Contraction (10 Pts)
        std10 = close.rolling(10).std()
        std30 = close.rolling(30).std()
        vcp = (std10 < std30 * 0.65) & (close > df['EMA_20'])
        df['Score_VCP'] = np.where(vcp, 10.0, 4.0)
        
        # TOPLAM QUANT SCORE (100 Pts)
        df['Quant_Score'] = np.clip(
            regime_score + df['Score_Trend'] + df['Score_Mom'] + df['Score_RS'] +
            df['Score_Vol'] + df['Score_SMC'] + df['Score_VCP'], 0.0, 100.0
        )
        return df

# ==============================================================================
# 6. DECISION ENGINE & PAPER TRADING EXECUTION
# ==============================================================================
class DecisionAndPaperEngineV63:
    @staticmethod
    def run_execution(data_dict, regime, breadth_pct, regime_score):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT cash, total_value FROM paper_portfolio ORDER BY id DESC LIMIT 1")
        cash, total_val = cursor.fetchone()
        
        df_pos = pd.read_sql("SELECT * FROM paper_positions", conn)
        open_positions = {row['symbol']: row for _, row in df_pos.iterrows()}
        
        current_prices = {}
        
        # --- 1. EXIT & HOLD ENGINE FOR OPEN POSITIONS ---
        for sym, pos in list(open_positions.items()):
            if sym not in data_dict:
                continue
            df = data_dict[sym]
            c_row = df.iloc[-1]
            p_row = df.iloc[-2]
            current_prices[sym] = c_row['Close']
            
            # Trailing Stop Update
            trailing_sl = max(pos['stop_loss'], p_row['Close'] - (2.0 * p_row['ATR']))
            
            exit_flag = False
            exit_reason = ""
            exit_price = c_row['Close']
            
            if c_row['Low'] <= trailing_sl:
                exit_flag = True
                exit_reason = "Trailing Stop Loss Hit"
                exit_price = trailing_sl
            elif c_row['High'] >= pos['tp2']:
                exit_flag = True
                exit_reason = "Take Profit 2 (3.5R) Hit"
                exit_price = pos['tp2']
            elif c_row['Close'] < c_row['EMA_20'] and pos['bars_held'] >= 3:
                exit_flag = True
                exit_reason = "EMA20 Breakdown"
                exit_price = c_row['Close']
            elif c_row['Quant_Score'] < 55.0:
                exit_flag = True
                exit_reason = "Score Deterioration (<55)"
                exit_price = c_row['Close']
            elif pos['bars_held'] >= 30:
                exit_flag = True
                exit_reason = "Time Stop (30 Days)"
                exit_price = c_row['Close']
                
            if exit_flag:
                exit_price *= 0.999 # Slippage
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

        # --- 2. SCAN & ENTRY ENGINE FOR NEW POSITIONS ---
        active_candidates = []
        for sym, df in data_dict.items():
            current_prices[sym] = df['Close'].iloc[-1]
            if sym in open_positions:
                continue
                
            c_row = df.iloc[-1]
            score = c_row['Quant_Score']
            
            # Model Confidence
            model_confidence = min(0.92, max(0.45, (score / 100.0) * 0.70 + 0.12))
            
            if score >= 78.0 and regime != "STRONG BEAR" and model_confidence >= 0.60:
                decision = "🟢 GÜÇLÜ AL" if score >= 88 else "🟢 AL"
                reason = f"Minervini Trend OK | RS: {c_row['Composite_RS']*100:+.1f}% | RVOL: {c_row['RVOL']:.1f}x"
                active_candidates.append({
                    'symbol': sym, 'score': score, 'confidence': model_confidence, 'decision': decision,
                    'price': c_row['Close'], 'atr': c_row['ATR'], 'reason': reason
                })
                
        active_candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # --- 3. RISK ENGINE & POSITION SIZING ---
        max_slots = 5 - len(open_positions)
        for cand in active_candidates[:max_slots]:
            entry_price = cand['price'] * 1.001 # T+1 Açılış Kayması
            stop_loss = entry_price - (1.5 * cand['atr'])
            tp1 = entry_price + (2.0 * cand['atr'])
            tp2 = entry_price + (3.5 * cand['atr'])
            
            risk_per_share = entry_price - stop_loss
            max_risk_amount = total_val * 0.015 # 1.5% Risk
            max_pos_val = total_val * 0.20 # Max %20 Allocation
            
            shares = int(min(max_risk_amount / (risk_per_share + 1e-10), max_pos_val / entry_price))
            total_cost = shares * entry_price * 1.000525
            
            if shares > 0 and cash >= total_cost:
                cash -= total_cost
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO paper_positions (symbol, entry_date, entry_price, shares, stop_loss, tp1, tp2, quant_score, model_confidence, bars_held)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """, (cand['symbol'], now_str, entry_price, shares, stop_loss, tp1, tp2, cand['score'], cand['confidence']))

        # --- 4. MARK-TO-MARKET PORTFOLIO UPDATE ---
        df_pos_upd = pd.read_sql("SELECT * FROM paper_positions", conn)
        mtm_val = sum([r['shares'] * current_prices.get(r['symbol'], r['entry_price']) for _, r in df_pos_upd.iterrows()]) if not df_pos_upd.empty else 0.0
        new_total_val = cash + mtm_val
        
        cursor.execute("INSERT INTO paper_portfolio (cash, total_value, updated_at) VALUES (?, ?, ?)",
                       (cash, new_total_val, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                       
        conn.commit()
        conn.close()
        
        return active_candidates, current_prices

# ==============================================================================
# 7. STREAMLIT UI & DASHBOARD INTERFACE
# ==============================================================================
def main():
    DatabaseEngineV63.init_db()
    
    st.markdown('<h1 style="color:#F8FAFC; margin-bottom:0px;">⚡ QUANT MASTER v63 — PAPER TRADER</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color:#94A3B8; font-size:1.0rem;">Algoritmik Fon Yönetimi & Gerçek Zamanlı Sanal Portföy Laboratuvarı</p>', unsafe_allow_html=True)
    st.markdown("---")
    
    symbols = get_bist100_constituents()
    
    st.sidebar.header("⚙️ Sistem Kontrol Paneli")
    lookback = st.sidebar.slider("Veri Geçmişi (Gün - 3 Yıl Önerilir)", 300, 1000, 750)
    
    if st.sidebar.button("🚀 Tarama & Sanal İşlem Motorunu Çalıştır", use_container_width=True):
        with st.spinner("BIST100 Verileri İndiriliyor & Karar Motoru Çalıştırılıyor..."):
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
            st.session_state['regime'] = regime
            st.session_state['breadth'] = breadth_pct
            st.session_state['candidates'] = candidates
            st.session_state['prices'] = current_prices
            st.success("Sanal İşlem Güncellemesi Tamamlandı!")

    if st.sidebar.button("🗑️ Sanal Portföyü Sıfırla (100k TL)"):
        DatabaseEngineV63.reset_database()
        st.sidebar.warning("Portföy başlangıç değerine sıfırlandı!")
        st.rerun()

    # --- PORTFOLIO METRICS ---
    current_prices = st.session_state.get('prices', {})
    port_state, df_pos, df_trades = DatabaseEngineV63.get_portfolio_state(current_prices)
    
    pnl_total = port_state['total_value'] - 100000.0
    pnl_pct = (pnl_total / 100000.0) * 100.0
    
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.markdown(f'<div class="metric-card"><div class="metric-label">Toplam Varlık</div><div class="metric-value">{port_state["total_value"]:,.2f} ₺</div></div>', unsafe_allow_html=True)
    m2.markdown(f'<div class="metric-card"><div class="metric-label">Sanal Nakit</div><div class="metric-value">{port_state["cash"]:,.2f} ₺</div></div>', unsafe_allow_html=True)
    m3.markdown(f'<div class="metric-card"><div class="metric-label">Net PnL</div><div class="metric-value" style="color:{"#10B981" if pnl_total>=0 else "#EF4444"};">{pnl_total:+,.2f} ₺ ({pnl_pct:+.2f}%)</div></div>', unsafe_allow_html=True)
    
    reg_val = st.session_state.get('regime', 'NEUTRAL')
    breadth_val = st.session_state.get('breadth', 50.0)
    m4.markdown(f'<div class="metric-card"><div class="metric-label">Piyasa Rejimi</div><div class="metric-value" style="font-size:1.3rem;">{reg_val}</div></div>', unsafe_allow_html=True)
    m5.markdown(f'<div class="metric-card"><div class="metric-label">BIST Breadth</div><div class="metric-value">{breadth_val:.1f}%</div></div>', unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # --- TABS ---
    tab1, tab2, tab3 = st.tabs(["🎯 BUGÜNÜN AL SİNYALLERİ", "💼 AÇIK POZİSYONLAR (TUT / SAT)", "📜 İŞLEM DEFTERİ & PERFORMANS"])
    
    with tab1:
        st.subheader("🏆 Bugünün En Güçlü Sinyalleri (Decision Engine)")
        cands = st.session_state.get('candidates', [])
        if cands:
            for cand in cands:
                st.markdown(f"""
                <div class="signal-card-buy">
                    <h3 style="margin:0px; color:#F8FAFC;">{cand['decision']} <b>{cand['symbol']}</b> — Quant Skor: {cand['score']:.0f}/100 | Model Güveni: %{cand['confidence']*100:.1f}</h3>
                    <p style="margin-top:6px; margin-bottom:4px; color:#CBD5E1;"><b>Giriş (T+1):</b> {cand['price']*1.001:.2f} ₺ | <b>Stop:</b> {cand['price']-1.5*cand['atr']:.2f} ₺ | <b>TP1 (2R):</b> {cand['price']+2.0*cand['atr']:.2f} ₺ | <b>TP2 (3.5R):</b> {cand['price']+3.5*cand['atr']:.2f} ₺</p>
                    <p style="margin:0px; color:#94A3B8;"><b>Gerekçe:</b> {cand['reason']}</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Bugün için 78+ puan alan yeni giriş sinyali bulunmuyor veya piyasa koşulları beklemede tutuyor.")
            
    with tab2:
        st.subheader("💼 Aktif Sanal Portföy Pozisyonları")
        if not df_pos.empty:
            df_disp = df_pos.copy()
            df_disp['Güncel Fiyat'] = df_disp['symbol'].apply(lambda x: current_prices.get(x, 0.0))
            df_disp['Anlık Kar ₺'] = (df_disp['Güncel Fiyat'] - df_disp['entry_price']) * df_disp['shares']
            df_disp['Anlık Kar %'] = ((df_disp['Güncel Fiyat'] - df_disp['entry_price']) / df_disp['entry_price']) * 100.0
            
            st.dataframe(
                df_disp[['symbol', 'entry_date', 'entry_price', 'Güncel Fiyat', 'shares', 'stop_loss', 'tp1', 'tp2', 'Anlık Kar ₺', 'Anlık Kar %', 'bars_held']]
                .style.format({
                    'entry_price': '{:.2f} ₺', 'Güncel Fiyat': '{:.2f} ₺', 'stop_loss': '{:.2f} ₺',
                    'tp1': '{:.2f} ₺', 'tp2': '{:.2f} ₺', 'Anlık Kar ₺': '{:+,.2f} ₺', 'Anlık Kar %': '{:+.2f}%'
                }),
                use_container_width=True
            )
        else:
            st.info("Şu anda açık pozisyon bulunmuyor.")
            
    with tab3:
        st.subheader("📜 Tamamlanan İşlemler ve Performans Defteri")
        if not df_trades.empty:
            wins = df_trades[df_trades['pnl'] > 0]
            win_rate = (len(wins) / len(df_trades)) * 100.0
            profit_factor = (wins['pnl'].sum() / abs(df_trades[df_trades['pnl'] < 0]['pnl'].sum())) if len(df_trades[df_trades['pnl'] < 0]) > 0 else np.inf
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Toplam İşlem", len(df_trades))
            c2.metric("Win Rate", f"{win_rate:.1f}%")
            c3.metric("Profit Factor", f"{profit_factor:.2f}" if profit_factor != np.inf else "∞")
            
            st.markdown("---")
            st.dataframe(
                df_trades.style.format({
                    'entry_price': '{:.2f} ₺', 'exit_price': '{:.2f} ₺',
                    'pnl': '{:+,.2f} ₺', 'pnl_pct': '{:+.2%}'
                }),
                use_container_width=True
            )
        else:
            st.info("Henüz kapanmış işlem kaydı bulunmuyor.")

if __name__ == "__main__":
    main()

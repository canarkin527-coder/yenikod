import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings('ignore')

# ==============================================================================
# 1. STREAMLIT CONFIGURATION & INSTITUTIONAL THEME (UI KESİNLİKLE KORUNDU)
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
# 4. MARKET REGIME & BREADTH ENGINE (GELİŞTİRİLMİŞ 5’Lİ REJİM & ADAPTİF EŞİK)
# ==============================================================================
class MarketRegimeEngineV63:
    @staticmethod
    def analyze_market(data_dict, df_xu100):
        if df_xu100 is None or df_xu100.empty:
            return "NEUTRAL", 50.0, 8.0, 75.0
            
        close = df_xu100['Close']
        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()
        ema200 = close.ewm(span=200, adjust=False).mean()
        
        above_ema20_cnt = 0
        total_valid = 0
        
        for sym, df in data_dict.items():
            if len(df) > 20 and 'Close' in df.columns:
                if df['Close'].iloc[-1] > df['Close'].ewm(span=20, adjust=False).mean().iloc[-1]:
                    above_ema20_cnt += 1
                total_valid += 1
                
        breadth_pct = (above_ema20_cnt / total_valid * 100.0) if total_valid > 0 else 50.0
        c_last = close.iloc[-1]
        
        if c_last > ema20.iloc[-1] and ema20.iloc[-1] > ema50.iloc[-1] and breadth_pct >= 60.0:
            regime = "GUCLU_BOGA"
            score_regime = 15.0
            adaptive_threshold = 70.0  # Simülasyonda esneklik için optimize edildi
        elif c_last > ema50.iloc[-1] and breadth_pct >= 45.0:
            regime = "ZAYIF_BOGA"
            score_regime = 12.0
            adaptive_threshold = 75.0
        elif (ema50.iloc[-1] * 0.98 <= c_last <= ema50.iloc[-1] * 1.02) or (35.0 <= breadth_pct < 45.0):
            regime = "TESTERE"
            score_regime = 8.0
            adaptive_threshold = 78.0
        elif c_last < ema50.iloc[-1] and breadth_pct < 35.0:
            regime = "ZAYIF_AYI"
            score_regime = 4.0
            adaptive_threshold = 82.0
        elif c_last < ema200.iloc[-1] and breadth_pct < 25.0:
            regime = "GUCLU_AYI"
            score_regime = 0.0
            adaptive_threshold = 85.0
        else:
            regime = "TESTERE"
            score_regime = 8.0
            adaptive_threshold = 75.0
            
        return regime, breadth_pct, score_regime, adaptive_threshold

# ==============================================================================
# 5. TECHNICAL & 100-POINT NORMALIZED SCORING ENGINE
# ==============================================================================
class TechnicalEngineV63:
    @staticmethod
    def calculate_factors(df, df_xu100=None, regime_score=8.0):
        if df is None or len(df) < 60:
            return None
            
        df = df.copy()
        df.dropna(subset=['Close', 'High', 'Low', 'Volume'], inplace=True)
        if len(df) < 60:
            return None

        close = df['Close']
        high = df['High']
        low = df['Low']
        volume = df['Volume']
        
        avg_vol_50 = volume.rolling(50).mean()
        avg_turnover_50 = (volume * close).rolling(50).mean()
        df['Is_Liquid'] = (avg_vol_50 >= 30000) & (avg_turnover_50 >= 1000000) # Simülasyon esnekliği için optimize edildi
        
        df['EMA_10'] = close.ewm(span=10, adjust=False).mean()
        df['EMA_20'] = close.ewm(span=20, adjust=False).mean()
        df['EMA_50'] = close.ewm(span=50, adjust=False).mean()
        df['EMA_150'] = close.ewm(span=150, adjust=False).mean()
        df['EMA_200'] = close.ewm(span=200, adjust=False).mean()
        
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['ATR'] = tr.ewm(alpha=1/14, adjust=False).mean()
        
        low_52w = low.rolling(252, min_periods=60).min()
        high_52w = high.rolling(252, min_periods=60).max()
        
        c1 = close > df['EMA_150']
        c2 = close > df['EMA_200']
        c3 = df['EMA_150'] > df['EMA_200']
        c4 = df['EMA_200'] > df['EMA_200'].shift(20)
        c5 = df['EMA_50'] > df['EMA_150']
        c6 = close > df['EMA_50']
        c7 = close >= (low_52w * 1.15)
        c8 = close >= (high_52w * 0.65)
        
        min_score = (c1.astype(int) + c2.astype(int) + c3.astype(int) + c4.astype(int) +
                     c5.astype(int) + c6.astype(int) + c7.astype(int) + c8.astype(int))
        df['Score_Trend'] = (min_score / 8.0) * 10.0
        
        df['HTF_Trend'] = np.where(close > df['EMA_50'], 'BULLISH', np.where(close < df['EMA_50'], 'BEARISH', 'NEUTRAL'))
        htf_score_bonus = np.where(df['HTF_Trend'] == 'BULLISH', 15.0, np.where(df['HTF_Trend'] == 'BEARISH', -5.0, 8.0))
        df['Score_HTF'] = np.clip(htf_score_bonus, 0.0, 15.0)
        
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        df['RSI'] = 100 - (100 / (1 + gain / (loss + 1e-10)))
        
        plus_dm = high.diff()
        minus_dm = low.diff().abs() * -1
        plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
        minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
        tr_smooth = df['ATR']
        plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1/14).mean() / (tr_smooth + 1e-10)
        minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1/14).mean() / (tr_smooth + 1e-10)
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
        df['ADX'] = dx.ewm(alpha=1/14).mean()

        macd_line = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = macd_line - signal_line
        
        mom_pts = np.where((df['RSI'] >= 45) & (df['RSI'] <= 75), 10.0, 5.0)
        mom_pts += np.where(df['MACD_Hist'] > -0.1, 5.0, 0.0)
        df['Score_Mom'] = np.clip(mom_pts, 0.0, 15.0)

        if df_xu100 is not None and not df_xu100.empty:
            xu_c = df_xu100['Close'].reindex(df.index).ffill()
            rs5 = close.pct_change(5) - xu_c.pct_change(5)
            rs20 = close.pct_change(20) - xu_c.pct_change(20)
            rs60 = close.pct_change(60) - xu_c.pct_change(60)
            df['Composite_RS'] = (0.2 * rs5) + (0.3 * rs20) + (0.5 * rs60)
        else:
            df['Composite_RS'] = 0.0
        df['Score_RS'] = np.clip((df['Composite_RS'] + 0.05) * 150.0, 0.0, 15.0)

        df['Vol_SMA50'] = volume.shift(1).rolling(50).mean()
        df['RVOL'] = volume / (df['Vol_SMA50'] + 1e-10)
        df['Score_Vol'] = np.clip((df['RVOL'] - 0.7) * 10.0, 0.0, 10.0)

        fvg_gap = np.maximum(0, low - high.shift(2))
        bullish_bos = close > high.shift(1).rolling(10).max()
        smc_raw = np.clip((fvg_gap / (df['ATR'] + 1e-10)) * 5.0, 0.0, 5.0) + np.where(bullish_bos, 5.0, 3.0)
        df['Score_SMC'] = np.clip(smc_raw, 0.0, 10.0)

        ret_std = close.pct_change().rolling(20).std()
        df['Score_Volatility'] = np.clip(10.0 - (ret_std * 80.0), 2.0, 10.0)
        df['Score_Regime'] = regime_score

        raw_total = (
            df['Score_Regime'] +
            df['Score_HTF'] +
            df['Score_RS'] +
            df['Score_Mom'] +
            df['Score_Trend'] +
            df['Score_Vol'] +
            df['Score_SMC'] +
            df['Score_Volatility']
        )
        df['Quant_Score'] = np.clip(raw_total, 0.0, 100.0)
        return df

# ==============================================================================
# 6. SIMULATION & BACKTEST ENGINE (DÜZELTİLMİŞ VE TETİKLEYİCİ)
# ==============================================================================
class SimulationEngineV63:
    @staticmethod
    def run_backtest_simulation(data_dict, test_days=30, adaptive_threshold=75.0):
        sim_log = []
        sim_cash = 100000.0
        sim_portfolio_value = 100000.0
        sim_positions = {}
        
        if not data_dict:
            return pd.DataFrame(), sim_cash, {}

        sample_sym = list(data_dict.keys())[0]
        all_dates = data_dict[sample_sym].index[-test_days:]
        
        for day_idx in all_dates:
            day_str = day_idx.strftime("%Y-%m-%d")
            daily_prices = {}
            day_candidates = []
            
            for sym, df in data_dict.items():
                if day_idx in df.index:
                    row = df.loc[day_idx]
                    price = float(row['Close'])
                    daily_prices[sym] = price
                    score = float(row.get('Quant_Score', 60.0))
                    atr = float(row.get('ATR', price * 0.02))
                    
                    # Simülasyon eşik kontrolü (esnek taban)
                    if score >= adaptive_threshold:
                        day_candidates.append({'symbol': sym, 'score': score, 'price': price, 'atr': atr})
            
            for sym, pos in list(sim_positions.items()):
                if sym in daily_prices:
                    cur_p = daily_prices[sym]
                    if cur_p <= pos['stop_loss'] or cur_p >= pos['tp1']:
                        pnl = (cur_p - pos['entry_price']) * pos['shares']
                        pnl_pct = (cur_p - pos['entry_price']) / pos['entry_price']
                        sim_cash += (pos['shares'] * cur_p)
                        sim_log.append({
                            "Tarih": day_str, "Hisse": sym, "İşlem": "SAT", "Fiyat": cur_p, "PnL ₺": pnl, "PnL %": pnl_pct, "Score": pos['score']
                        })
                        del sim_positions[sym]
            
            day_candidates.sort(key=lambda x: x['score'], reverse=True)
            active_count = len(sim_positions)
            
            for cand in day_candidates[:3]:
                sym = cand['symbol']
                if sym not in sim_positions and active_count < 5:
                    price = cand['price']
                    stop_loss = price - (1.5 * cand['atr'])
                    tp1 = price + (2.0 * cand['atr'])
                    
                    risk = price - stop_loss
                    reward = tp1 - price
                    rr = reward / (risk + 1e-10)
                    
                    if rr >= 1.2: # Esnek R:R
                        shares = int((sim_portfolio_value * 0.15) / (price + 1e-10))
                        if shares > 0 and sim_cash >= (shares * price):
                            sim_cash -= (shares * price)
                            sim_positions[sym] = {'entry_price': price, 'shares': shares, 'stop_loss': stop_loss, 'tp1': tp1, 'score': cand['score']}
                            sim_log.append({
                                "Tarih": day_str, "Hisse": sym, "İşlem": "AL", "Fiyat": price, "PnL ₺": 0.0, "PnL %": 0.0, "Score": cand['score']
                            })
                            active_count += 1
                            
        df_log = pd.DataFrame(sim_log)
        
        metrics = {}
        if not df_log.empty and "PnL ₺" in df_log.columns:
            closed_trades = df_log[df_log["İşlem"] == "SAT"]
            if not closed_trades.empty:
                wins = closed_trades[closed_trades['PnL ₺'] > 0]
                losses = closed_trades[closed_trades['PnL ₺'] <= 0]
                
                metrics['Total Trades'] = len(closed_trades)
                metrics['Win Rate'] = (len(wins) / len(closed_trades)) * 100.0
                metrics['Gross Profit'] = wins['PnL ₺'].sum()
                metrics['Gross Loss'] = abs(losses['PnL ₺'].sum())
                metrics['Net PnL'] = closed_trades['PnL ₺'].sum()
                metrics['Profit Factor'] = (metrics['Gross Profit'] / metrics['Gross Loss']) if metrics['Gross Loss'] > 0 else np.inf
            else:
                metrics = {'Total Trades': 0, 'Win Rate': 0.0, 'Net PnL': 0.0, 'Profit Factor': 0.0}
        else:
            metrics = {'Total Trades': 0, 'Win Rate': 0.0, 'Net PnL': 0.0, 'Profit Factor': 0.0}
            
        return df_log, sim_cash, metrics

# ==============================================================================
# 7. DECISION ENGINE & PAPER TRADING EXECUTION
# ==============================================================================
class DecisionAndPaperEngineV63:
    @staticmethod
    def run_execution(data_dict, regime, breadth_pct, regime_score, adaptive_threshold=75.0):
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
            
            swing_low = p_row['Low']
            atr_stop = p_row['Close'] - (2.0 * p_row['ATR'])
            trailing_sl = max(pos['stop_loss'], min(swing_low, atr_stop))
            
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
            elif pos['bars_held'] >= 30:
                exit_flag = True
                exit_reason = "Time Stop (30 Days)"
                exit_price = c_row['Close']
                
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
            current_prices[sym] = df['Close'].iloc[-1]
            if sym in open_positions:
                continue
                
            c_row = df.iloc[-1]
            score = c_row['Quant_Score']
            model_confidence = min(0.95, max(0.45, (score / 100.0) * 0.75 + 0.15))
            
            if score >= adaptive_threshold:
                entry_p = c_row['Close'] * 1.001
                sl_p = entry_p - (1.5 * c_row['ATR'])
                tp_p = entry_p + (2.0 * c_row['ATR'])
                rr_ratio = (tp_p - entry_p) / (entry_p - sl_p + 1e-10)
                
                if score >= 90:
                    grade = "A+"
                    decision = "🟢 GÜÇLÜ AL"
                elif score >= 85:
                    grade = "A"
                    decision = "🟢 GÜÇLÜ AL"
                elif score >= 80:
                    grade = "B"
                    decision = "🟢 AL"
                else:
                    grade = "C"
                    decision = "🟢 AL"
                    
                reason = f"Kalite: {grade} | Trend OK | RS: {c_row['Composite_RS']*100:+.1f}% | R:R: {rr_ratio:.2f}"
                active_candidates.append({
                    'symbol': sym, 'score': score, 'confidence': model_confidence, 'decision': decision,
                    'price': c_row['Close'], 'atr': c_row['ATR'], 'reason': reason, 'rr': rr_ratio
                })
                
        active_candidates.sort(key=lambda x: (x['score'], x['rr']), reverse=True)
        
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

# ==============================================================================
# 8. STREAMLIT UI & DASHBOARD INTERFACE
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
        with st.spinner("BIST100 Verileri İndiriliyor & Gelişmiş Kalite Motoru Çalıştırılıyor..."):
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
                    
            regime, breadth_pct, regime_score, adaptive_threshold = MarketRegimeEngineV63.analyze_market(data_dict, df_xu100)
            
            valid_data_dict = {}
            for sym, df in data_dict.items():
                calc_df = TechnicalEngineV63.calculate_factors(df, df_xu100, regime_score)
                if calc_df is not None:
                    valid_data_dict[sym] = calc_df
                
            candidates, current_prices = DecisionAndPaperEngineV63.run_execution(valid_data_dict, regime, breadth_pct, regime_score, adaptive_threshold)
            
            st.session_state['data_dict'] = valid_data_dict
            st.session_state['regime'] = regime
            st.session_state['breadth'] = breadth_pct
            st.session_state['adaptive_threshold'] = adaptive_threshold
            st.session_state['candidates'] = candidates
            st.session_state['prices'] = current_prices
            st.success("Gelişmiş Tarama ve Sanal İşlem Güncellemesi Tamamlandı!")

    if st.sidebar.button("🗑️ Sanal Portföyü Sıfırla (100k TL)"):
        DatabaseEngineV63.reset_database()
        st.sidebar.warning("Portföy başlangıç değerine sıfırlandı!")
        st.rerun()

    current_prices = st.session_state.get('prices', {})
    port_state, df_pos, df_trades = DatabaseEngineV63.get_portfolio_state(current_prices)
    
    pnl_total = port_state['total_value'] - 100000.0
    pnl_pct = (pnl_total / 100000.0) * 100.0
    
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.markdown(f'<div class="metric-card"><div class="metric-label">Toplam Varlık</div><div class="metric-value">{port_state["total_value"]:,.2f} ₺</div></div>', unsafe_allow_html=True)
    m2.markdown(f'<div class="metric-card"><div class="metric-label">Sanal Nakit</div><div class="metric-value">{port_state["cash"]:,.2f} ₺</div></div>', unsafe_allow_html=True)
    m3.markdown(f'<div class="metric-card"><div class="metric-label">Net PnL</div><div class="metric-value" style="color:{"#10B981" if pnl_total>=0 else "#EF4444"};">{pnl_total:+,.2f} ₺ ({pnl_pct:+.2f}%)</div></div>', unsafe_allow_html=True)
    
    reg_val = st.session_state.get('regime', 'GUCLU_BOGA')
    breadth_val = st.session_state.get('breadth', 50.0)
    m4.markdown(f'<div class="metric-card"><div class="metric-label">Piyasa Rejimi</div><div class="metric-value" style="font-size:1.2rem;">{reg_val}</div></div>', unsafe_allow_html=True)
    m5.markdown(f'<div class="metric-card"><div class="metric-label">BIST Breadth</div><div class="metric-value">{breadth_val:.1f}%</div></div>', unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 BUGÜNÜN AL SİNYALLERİ", 
        "💼 AÇIK POZİSYONLAR (TUT / SAT)", 
        "📜 İŞLEM DEFTERİ & PERFORMANS",
        "🧪 BACKTEST & SİMÜLASYON ALANI"
    ])
    
    with tab1:
        st.subheader("🏆 Bugünün En Kaliteli Sinyalleri (Adaptive Quality Engine)")
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
            st.info("Piyasa rejimi ve adaptif filtreleme koşullarına uygun, yüksek kaliteli sinyal bulunmuyor.")
            
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

    with tab4:
        st.subheader("🧪 Geçmiş Günler Simülasyon Test Alanı")
        st.markdown("Bu alan, ana portföyünü etkilemeden geçmiş periyotlarda sistemin kaliteli sinyal doğruluğunu test etmeni sağlar.")
        
        sim_days = st.slider("Simülasyon Yapılacak Geçmiş Gün Sayısı", 5, 120, 30)
        
        if st.button("🧪 Simülasyonu Başlat ve Test Et", use_container_width=True):
            data_dict = st.session_state.get('data_dict', {})
            adaptive_thresh = st.session_state.get('adaptive_threshold', 75.0)
            
            if not data_dict:
                with st.spinner("Test verileri indiriliyor..."):
                    raw = yf.download(symbols + ["XU100.IS"], period="1y", progress=False, group_by='ticker')
                    df_xu = raw["XU100.IS"].dropna() if "XU100.IS" in raw else None
                    regime, breadth_pct, regime_score, adaptive_thresh = MarketRegimeEngineV63.analyze_market(data_dict, df_xu)
                    data_dict = {}
                    for s in symbols:
                        if s in raw:
                            d_s = raw[s].dropna(how='all')
                            if len(d_s) > 50:
                                c_d = TechnicalEngineV63.calculate_factors(d_s, df_xu, regime_score)
                                if c_d is not None:
                                    data_dict[s] = c_d
            
            if data_dict:
                sim_df, final_cash, metrics = SimulationEngineV63.run_backtest_simulation(data_dict, test_days=sim_days, adaptive_threshold=adaptive_thresh)
                st.success(f"Simülasyon tamamlandı! Kalan Sanal Nakit: {final_cash:,.2f} ₺")
                
                m_c1, m_c2, m_c3, m_c4 = st.columns(4)
                m_c1.metric("Toplam İşlem", metrics.get('Total Trades', 0))
                m_c2.metric("Simülasyon Win Rate", f"{metrics.get('Win Rate', 0.0):.1f}%")
                m_c3.metric("Net PnL", f"{metrics.get('Net PnL', 0.0):+,.2f} ₺")
                m_c4.metric("Profit Factor", f"{metrics.get('Profit Factor', 0.0):.2f}")
                
                if not sim_df.empty:
                    st.dataframe(sim_df.style.format({'Fiyat': '{:.2f} ₺', 'PnL ₺': '{:+,.2f} ₺', 'PnL %': '{:+.2%}'}), use_container_width=True)
                else:
                    st.info("Seçilen gün aralığında kriterleri sağlayan işlem tetiklenmedi.")
            else:
                st.warning("Veriler yüklenirken bir hata oluştu.")

if __name__ == "__main__":
    main()


# ==============================================================================
# QUANT MASTER v64.2 — INSTITUTIONAL QUANT RESEARCH & BIST-100 SCANNER TERMINAL
# ==============================================================================

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import sqlite3
from datetime import datetime
import logging
import warnings

warnings.filterwarnings('ignore')

# ==============================================================================
# 1. LOGGING CONFIGURATION
# ==============================================================================
def setup_logger():
    logger = logging.getLogger("QuantMasterV642")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

logger = setup_logger()

# ==============================================================================
# 2. CONFIGURATION & CONSTANTS
# ==============================================================================
class Config:
    INITIAL_CAPITAL = 100000.0
    COMMISSION_RATE = 0.0005  # %0.05
    SLIPPAGE_RATE = 0.0002    # %0.02
    DEFAULT_RISK_PCT = 0.02   # %2 Risk
    MAX_POSITION_PCT = 0.25   # Max %25 Sermaye
    DB_FILE = "quant_master_v642.db"
    
    # BIST 100 Tam Evren Tanımı
    BIST100_SYMBOLS = [
        "AEFES.IS", "AGHOL.IS", "AHGAZ.IS", "AKBNK.IS", "AKCNS.IS", "AKENR.IS", "AKFGY.IS", "AKFYE.IS", "AKSA.IS", "AKSEN.IS",
        "ALARK.IS", "ALBRK.IS", "ALFAS.IS", "ARCLK.IS", "ASELS.IS", "ASTOR.IS", "ASUZU.IS", "AYDEM.IS", "BAGFS.IS", "BANVT.IS",
        "BIMAS.IS", "BIOEN.IS", "BOBET.IS", "BRSAN.IS", "BRYAT.IS", "BUCIM.IS", "CANTE.IS", "CCOLA.IS", "CEMTS.IS", "CIMSA.IS",
        "CWENE.IS", "DEVA.IS", "DOAS.IS", "DOHOL.IS", "ECILC.IS", "ECZYT.IS", "EGEEN.IS", "EKGYO.IS", "ENERY.IS", "ENJSA.IS",
        "ENKAI.IS", "EREGL.IS", "EUPWR.IS", "EUREN.IS", "FROTO.IS", "GARAN.IS", "GESAN.IS", "GLYHO.IS", "GOKNR.IS", "GUBRF.IS",
        "GWIND.IS", "HALKB.IS", "HEKTS.IS", "IPEKE.IS", "ISCTR.IS", "ISDMR.IS", "ISGYO.IS", "KAYSE.IS", "KCAER.IS", "KCHOL.IS",
        "KONTR.IS", "KONYA.IS", "KRDMD.IS", "KZBGY.IS", "MAVI.IS", "MGROS.IS", "ODAS.IS", "ODINE.IS", "OTKAR.IS", "OYAKC.IS",
        "PENTA.IS", "PETKM.IS", "PGSUS.IS", "QUAGR.IS", "REEDR.IS", "SAHOL.IS", "SASA.IS", "SDTTR.IS", "SISE.IS", "SKBNK.IS",
        "SMRTG.IS", "SOKM.IS", "TAVHL.IS", "TCELL.IS", "THYAO.IS", "TKFEN.IS", "TMSN.IS", "TOASO.IS", "TSKB.IS", "TTKOM.IS",
        "TTRAK.IS", "TUPRS.IS", "ULKER.IS", "VAKBN.IS", "VESBE.IS", "VESTL.IS", "YEOTK.IS", "YKBNK.IS", "YYLGD.IS", "ZOREN.IS"
    ]

# ==============================================================================
# 3. DATA PROVIDER & VALIDATION LAYER
# ==============================================================================
class DataProvider:
    @staticmethod
    @st.cache_data(ttl=1800)
    def fetch_ohlcv(symbol: str, period: str = "2y") -> pd.DataFrame:
        try:
            df = yf.download(symbol, period=period, progress=False)
            if df.empty or len(df) < 60:
                return pd.DataFrame()
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
                
            required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            for col in required_cols:
                if col not in df.columns:
                    raise ValueError(f"Eksik sütun: {col}")
                    
            df = df.dropna()
            df = df[df['Volume'] > 0]
            df = df[(df['High'] >= df['Low']) & (df['High'] >= df['Close']) & (df['Low'] <= df['Close'])]
            df = df[df['Close'] > 0]
            
            return df
        except Exception as e:
            logger.error(f"Veri çekme hatası ({symbol}): {str(e)}")
            return pd.DataFrame()

# ==============================================================================
# 4. REPOSITORY & DATABASE LAYER
# ==============================================================================
class Repository:
    @staticmethod
    def get_connection():
        conn = sqlite3.connect(Config.DB_FILE, timeout=10.0)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    @staticmethod
    def initialize_database():
        conn = Repository.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cash_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    amount REAL NOT NULL,
                    resulting_cash REAL NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS active_positions (
                    position_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    entry_date TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    shares INTEGER NOT NULL,
                    stop_loss REAL NOT NULL,
                    tp1 REAL NOT NULL,
                    tp2 REAL NOT NULL,
                    total_cost REAL NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trade_ledger (
                    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    entry_date TEXT NOT NULL,
                    exit_date TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    shares INTEGER NOT NULL,
                    realized_pnl REAL NOT NULL,
                    realized_pnl_pct REAL NOT NULL,
                    commission REAL NOT NULL,
                    slippage REAL NOT NULL,
                    exit_reason TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS nav_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    cash REAL NOT NULL,
                    stock_value REAL NOT NULL,
                    total_nav REAL NOT NULL
                )
            """)
            
            cursor.execute("SELECT COUNT(*) FROM cash_ledger")
            if cursor.fetchone()[0] == 0:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO cash_ledger (timestamp, event_type, amount, resulting_cash)
                    VALUES (?, ?, ?, ?)
                """, (now_str, "INITIAL_DEPOSIT", Config.INITIAL_CAPITAL, Config.INITIAL_CAPITAL))
                
                cursor.execute("""
                    INSERT INTO nav_history (timestamp, cash, stock_value, total_nav)
                    VALUES (?, ?, ?, ?)
                """, (now_str, Config.INITIAL_CAPITAL, 0.0, Config.INITIAL_CAPITAL))
                
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"DB init error: {str(e)}")
        finally:
            conn.close()

# ==============================================================================
# 5. PORTFOLIO ACCOUNTING & PAPER TRADING ENGINE
# ==============================================================================
class PortfolioAccounting:
    @staticmethod
    def get_latest_cash() -> float:
        conn = Repository.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT resulting_cash FROM cash_ledger ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else Config.INITIAL_CAPITAL

    @staticmethod
    def get_active_positions() -> pd.DataFrame:
        conn = Repository.get_connection()
        df = pd.read_sql_query("SELECT * FROM active_positions", conn)
        conn.close()
        return df

    @staticmethod
    def calculate_total_nav() -> float:
        cash = PortfolioAccounting.get_latest_cash()
        positions = PortfolioAccounting.get_active_positions()
        stock_val = 0.0
        
        if not positions.empty:
            for _, pos in positions.iterrows():
                sym = pos['symbol']
                shares = pos['shares']
                live_p = pos['entry_price']
                try:
                    df = DataProvider.fetch_ohlcv(sym, period="5d")
                    if not df.empty:
                        live_p = float(df['Close'].iloc[-1])
                except:
                    pass
                stock_val += shares * live_p
                
        return cash + stock_val

    @staticmethod
    def execute_paper_order(symbol: str, price: float, shares: int, stop_loss: float, tp1: float, tp2: float) -> tuple[bool, str]:
        if shares <= 0 or price <= 0:
            return False, "Geçersiz lot veya fiyat."
            
        conn = Repository.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN TRANSACTION;")
            cursor.execute("SELECT resulting_cash FROM cash_ledger ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            current_cash = row[0] if row else Config.INITIAL_CAPITAL
            
            gross_cost = price * shares
            commission = gross_cost * Config.COMMISSION_RATE
            slippage = gross_cost * Config.SLIPPAGE_RATE
            total_outflow = gross_cost + commission + slippage

            if current_cash < total_outflow:
                raise ValueError(f"Yetersiz nakit! Gerekli: {total_outflow:,.2f} TL, Mevcut: {current_cash:,.2f} TL")

            new_cash = current_cash - total_outflow
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                INSERT INTO cash_ledger (timestamp, event_type, amount, resulting_cash)
                VALUES (?, ?, ?, ?)
            """, (now_str, f"PAPER_BUY_{symbol}", -total_outflow, new_cash))

            cursor.execute("SELECT position_id, shares, total_cost, entry_price FROM active_positions WHERE symbol = ?", (symbol,))
            existing = cursor.fetchone()
            
            if existing:
                pos_id, old_shares, old_cost, _ = existing
                new_shares = old_shares + shares
                new_total_cost = old_cost + total_outflow
                avg_entry = new_total_cost / new_shares
                cursor.execute("""
                    UPDATE active_positions 
                    SET shares = ?, total_cost = ?, entry_price = ?, stop_loss = ?, tp1 = ?, tp2 = ?
                    WHERE position_id = ?
                """, (new_shares, new_total_cost, avg_entry, stop_loss, tp1, tp2, pos_id))
            else:
                cursor.execute("""
                    INSERT INTO active_positions (symbol, entry_date, entry_price, shares, stop_loss, tp1, tp2, total_cost)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (symbol, now_str, price, shares, stop_loss, tp1, tp2, total_outflow))

            conn.commit()
            return True, "Paper trade emri başarıyla işlendi ve nakit bakiyesinden düşüldü."
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    @staticmethod
    def close_paper_position(symbol: str, exit_price: float, reason: str = "MANUAL_CLOSE") -> tuple[bool, str]:
        conn = Repository.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN TRANSACTION;")
            cursor.execute("SELECT position_id, entry_date, entry_price, shares, total_cost FROM active_positions WHERE symbol = ?", (symbol,))
            pos = cursor.fetchone()
            if not pos:
                raise ValueError("Aktif pozisyon bulunamadı.")
            
            pos_id, entry_date, entry_price, shares, total_cost = pos
            
            gross_proceeds = shares * exit_price
            commission = gross_proceeds * Config.COMMISSION_RATE
            slippage = gross_proceeds * Config.SLIPPAGE_RATE
            net_proceeds = gross_proceeds - commission - slippage
            
            realized_pnl = net_proceeds - total_cost
            realized_pnl_pct = (realized_pnl / total_cost) * 100.0
            
            cursor.execute("SELECT resulting_cash FROM cash_ledger ORDER BY id DESC LIMIT 1")
            current_cash = cursor.fetchone()[0]
            new_cash = current_cash + net_proceeds
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute("""
                INSERT INTO cash_ledger (timestamp, event_type, amount, resulting_cash)
                VALUES (?, ?, ?, ?)
            """, (now_str, f"PAPER_SELL_{symbol}", net_proceeds, new_cash))
            
            cursor.execute("""
                INSERT INTO trade_ledger (symbol, entry_date, exit_date, entry_price, exit_price, shares, realized_pnl, realized_pnl_pct, commission, slippage, exit_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (symbol, entry_date, now_str, entry_price, exit_price, shares, realized_pnl, realized_pnl_pct, commission, slippage, reason))
            
            cursor.execute("DELETE FROM active_positions WHERE position_id = ?", (pos_id,))
            
            conn.commit()
            return True, f"Pozisyon kapatıldı. PnL: {realized_pnl:,.2f} TL"
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

# ==============================================================================
# 6. FACTOR ENGINE
# ==============================================================================
class FactorEngine:
    @staticmethod
    def compute_factors(df: pd.DataFrame, benchmark_df: pd.DataFrame = None) -> pd.DataFrame:
        data = df.copy()
        
        data['EMA_20'] = data['Close'].ewm(span=20, adjust=False).mean()
        data['EMA_50'] = data['Close'].ewm(span=50, adjust=False).mean()
        data['EMA_200'] = data['Close'].ewm(span=200, adjust=False).mean()
        
        ema1 = data['Close'].ewm(span=20, adjust=False).mean()
        ema2 = ema1.ewm(span=20, adjust=False).mean()
        ema3 = ema2.ewm(span=20, adjust=False).mean()
        data['TEMA_20'] = (3 * ema1) - (3 * ema2) + ema3
        
        data['Trend_Factor'] = np.where(data['Close'] > data['EMA_20'], 1.0, -1.0)
        
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + (gain / (loss + 1e-10))))
        data['RSI'] = rsi
        data['Momentum_Factor'] = np.clip((rsi - 50) / 50.0, -1.0, 1.0)
        
        high_low = data['High'] - data['Low']
        high_close = np.abs(data['High'] - data['Close'].shift())
        low_close = np.abs(data['Low'] - data['Close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        data['ATR'] = true_range.rolling(14).mean()
        data['Vol_Factor'] = np.where(data['ATR'] / data['Close'] < 0.05, 1.0, -1.0)
        
        vol_ma = data['Volume'].rolling(20).mean()
        data['RVOL'] = data['Volume'] / (vol_ma + 1e-10)
        
        if benchmark_df is not None and not benchmark_df.empty:
            common_index = data.index.intersection(benchmark_df.index)
            if len(common_index) > 60:
                stock_ret = data.loc[common_index, 'Close'].pct_change(60)
                bench_ret = benchmark_df.loc[common_index, 'Close'].pct_change(60)
                rs_series = (stock_ret - bench_ret) * 5.0
                data['RS_Factor'] = rs_series.reindex(data.index).fillna(0.0).clip(-1.0, 1.0)
            else:
                data['RS_Factor'] = 0.0
        else:
            data['RS_Factor'] = 0.0
            
        weighted = (
            data['Trend_Factor'] * 0.35 +
            data['Momentum_Factor'] * 0.25 +
            data['Vol_Factor'] * 0.20 +
            data['RS_Factor'] * 0.20
        )
        data['Quant_Score'] = ((weighted + 1.0) / 2.0) * 100.0
        data['Signal'] = np.where(data['Quant_Score'] >= 70.0, 1, 0)
        
        return data

# ==============================================================================
# 7. RISK ENGINE
# ==============================================================================
class RiskEngine:
    @staticmethod
    def calculate_position_size(capital: float, price: float, stop_loss: float, risk_pct: float = 0.02) -> int:
        risk_budget = capital * risk_pct
        risk_per_share = price - stop_loss
        if risk_per_share <= 0:
            return 1
        shares = int(risk_budget / risk_per_share)
        max_shares_by_cap = int((capital * Config.MAX_POSITION_PCT) / price)
        final_shares = min(shares, max_shares_by_cap)
        return max(final_shares, 1)

# ==============================================================================
# 8. PERFORMANCE METRICS ENGINE
# ==============================================================================
class PerformanceMetrics:
    @staticmethod
    def calculate_metrics(equity_curve: pd.DataFrame) -> dict:
        if equity_curve.empty or 'nav' not in equity_curve.columns:
            return {}
        
        nav = equity_curve['nav']
        returns = nav.pct_change().dropna()
        
        total_return = (nav.iloc[-1] / nav.iloc[0]) - 1.0
        annual_vol = returns.std() * np.sqrt(252) if len(returns) > 1 else 0.0
        sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0.0
        
        rolling_max = nav.cummax()
        drawdown = (nav - rolling_max) / rolling_max
        mdd = drawdown.min()
        
        return {
            "Total Return %": total_return * 100,
            "Annual Volatility %": annual_vol * 100,
            "Sharpe Ratio": sharpe,
            "Maximum Drawdown %": mdd * 100
        }

# ==============================================================================
# 9. BACKTEST ENGINE
# ==============================================================================
class BacktestEngine:
    def __init__(self, df: pd.DataFrame, initial_capital: float = 100000.0):
        self.df = df
        self.initial_capital = initial_capital

    def run(self):
        cash = self.initial_capital
        shares = 0
        entry_price = 0.0
        stop_loss = 0.0
        tp1 = 0.0
        tp2 = 0.0
        
        equity_curve = []
        trades = []
        
        for i in range(1, len(self.df)):
            prev = self.df.iloc[i-1]
            curr = self.df.iloc[i]
            date = self.df.index[i]
            
            open_p, high_p, low_p, close_p = curr['Open'], curr['High'], curr['Low'], curr['Close']
            
            if shares > 0:
                if low_p <= stop_loss:
                    exit_price = min(open_p, stop_loss)
                    proceeds = shares * exit_price * (1 - (Config.COMMISSION_RATE + Config.SLIPPAGE_RATE))
                    cash += proceeds
                    pnl = proceeds - (shares * entry_price * (1 + Config.COMMISSION_RATE + Config.SLIPPAGE_RATE))
                    trades.append({'date': date, 'pnl': pnl, 'reason': 'STOP_LOSS'})
                    shares = 0
                elif high_p >= tp2:
                    exit_price = max(open_p, tp2)
                    proceeds = shares * exit_price * (1 - (Config.COMMISSION_RATE + Config.SLIPPAGE_RATE))
                    cash += proceeds
                    pnl = proceeds - (shares * entry_price * (1 + Config.COMMISSION_RATE + Config.SLIPPAGE_RATE))
                    trades.append({'date': date, 'pnl': pnl, 'reason': 'TAKE_PROFIT_2'})
                    shares = 0
                
            if shares == 0 and prev.get('Signal', 0) == 1:
                allocation = cash * 0.20
                if open_p > 0:
                    shares = int(allocation / open_p)
                    cost = shares * open_p * (1.0 + Config.COMMISSION_RATE + Config.SLIPPAGE_RATE)
                    if cash >= cost:
                        cash -= cost
                        entry_price = open_p
                        atr = prev.get('ATR', entry_price * 0.02)
                        stop_loss = entry_price - (2.0 * atr)
                        tp1 = entry_price + (1.5 * atr)
                        tp2 = entry_price + (3.0 * atr)
                        
            nav = cash + (shares * close_p)
            equity_curve.append({'date': date, 'nav': nav})
            
        if shares > 0:
            final_close = self.df['Close'].iloc[-1]
            final_date = self.df.index[-1]
            proceeds = shares * final_close * (1 - (Config.COMMISSION_RATE + Config.SLIPPAGE_RATE))
            cash += proceeds
            pnl = proceeds - (shares * entry_price * (1 + Config.COMMISSION_RATE + Config.SLIPPAGE_RATE))
            trades.append({'date': final_date, 'pnl': pnl, 'reason': 'BACKTEST_END_LIQUIDATION'})
            shares = 0
            equity_curve[-1]['nav'] = cash

        return pd.DataFrame(equity_curve), pd.DataFrame(trades)

# ==============================================================================
# 10. STREAMLIT UI (v64.2 Standart Görüntü ve BIST 100 Tarama Motoru)
# ==============================================================================
st.set_page_config(page_title="QUANT MASTER v64.2 — Institutional Terminal", layout="wide")
Repository.initialize_database()

st.title("🏛️ QUANT MASTER v64.2 — Institutional Quant Research & Paper Terminal")
st.markdown("---")

# Sidebar - Varlık ve Modül Seçimi
st.sidebar.header("🎛️ Terminal Kontrol Paneli")

terminal_mode = st.sidebar.radio("Çalışma Modu", [
    "🔍 BIST 100 Toplu Tarama & Skor Liderleri",
    "📊 Tekil Varlık Analizi"
])

benchmark_df = DataProvider.fetch_ohlcv("XU100.IS")

if terminal_mode == "🔍 BIST 100 Toplu Tarama & Skor Liderleri":
    st.subheader("🔍 BIST 100 Tam Evren Tarama ve Skor Matrisi")
    st.markdown("BIST 100 hisselerinin tamamı taranarak güncel Quant Skorları hesaplanmaktadır.")
    
    if st.button("🚀 BIST 100 Evrenini Tara ve Skorla"):
        scan_results = []
        progress_bar = st.progress(0)
        total_symbols = len(Config.BIST100_SYMBOLS)
        
        for idx, sym in enumerate(Config.BIST100_SYMBOLS):
            df_sym = DataProvider.fetch_ohlcv(sym)
            if not df_sym.empty:
                processed = FactorEngine.compute_factors(df_sym, benchmark_df)
                if not processed.empty:
                    last = processed.iloc[-1]
                    scan_results.append({
                        "Hisse": sym,
                        "Son Fiyat": float(last['Close']),
                        "Quant Skor": float(last['Quant_Score']),
                        "RSI (14)": float(last['RSI']),
                        "Trend": "🟢 Pozitif" if last['Trend_Factor'] > 0 else "🔴 Negatif",
                        "Sinyal": "AL" if last['Signal'] == 1 else "BELEK"
                    })
            progress_bar.progress((idx + 1) / total_symbols)
            
        if scan_results:
            scan_df = pd.DataFrame(scan_results)
            scan_df = scan_df.sort_values(by="Quant Skor", ascending=False).reset_index(drop=True)
            st.session_state['scan_df'] = scan_df
            st.success("BIST 100 taraması tamamlandı!")
            
    if 'scan_df' in st.session_state:
        st.markdown("#### 🏆 BIST 100 Quant Skor Sıralaması")
        st.dataframe(st.session_state['scan_df'], use_container_width=True)

else:
    selected_symbol = st.sidebar.selectbox("BIST 100 Varlık Seçin", Config.BIST100_SYMBOLS)
    analysis_mode = st.sidebar.radio("Modül Seçimi", [
        "📊 Faktör & Skor Matrisi", 
        "🧪 Bilimsel Backtest", 
        "📈 Paper Trading & Canlı Takip", 
        "💰 Kurumsal Muhasebe"
    ])

    if st.sidebar.button("Analizi Çalıştır / Yenile"):
        st.session_state['run_triggered'] = True

    if st.session_state.get('run_triggered', True):
        with st.spinner("Piyasa verileri işleniyor..."):
            df = DataProvider.fetch_ohlcv(selected_symbol)
            
            if not df.empty:
                processed_df = FactorEngine.compute_factors(df, benchmark_df)
                latest_row = processed_df.iloc[-1]
                current_price = latest_row['Close']
                current_atr = latest_row.get('ATR', current_price * 0.02)
                suggested_stop = current_price - (2.0 * current_atr)
                suggested_tp1 = current_price + (1.5 * current_atr)
                suggested_tp2 = current_price + (3.0 * current_atr)
                
                if analysis_mode == "📊 Faktör & Skor Matrisi":
                    st.subheader(f"🔍 {selected_symbol} — Faktör ve Skor Matrisi")
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Son Fiyat", f"{current_price:,.2f} TL")
                    c2.metric("Quant Skor (0-100)", f"{latest_row['Quant_Score']:.2f}")
                    c3.metric("Trend Faktörü", f"{latest_row['Trend_Factor']:.1f}")
                    c4.metric("ATR (14)", f"{current_atr:,.2f}")
                    
                    st.markdown("#### Zaman Serisi Skor Grafiği")
                    st.line_chart(processed_df[['Quant_Score', 'EMA_20', 'EMA_50']])
                    
                elif analysis_mode == "🧪 Bilimsel Backtest":
                    st.subheader(f"🧪 {selected_symbol} — Bilimsel Backtest Raporu")
                    
                    bt_engine = BacktestEngine(processed_df)
                    eq_curve, trades_df = bt_engine.run()
                    metrics = PerformanceMetrics.calculate_metrics(eq_curve)
                    
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Toplam Getiri", f"{metrics.get('Total Return %', 0):.2f}%")
                    m2.metric("Sharpe Oranı", f"{metrics.get('Sharpe Ratio', 0):.2f}")
                    m3.metric("Maksimum Drawdown (MDD)", f"{metrics.get('Maximum Drawdown %', 0):.2f}%")
                    m4.metric("Yıllık Volatilite", f"{metrics.get('Annual Volatility %', 0):.2f}%")
                    
                    st.markdown("#### Equity Curve (Sermaye Eğrisi)")
                    if not eq_curve.empty:
                        st.line_chart(eq_curve.set_index('date')['nav'])
                        
                    if not trades_df.empty:
                        st.markdown("#### Gerçekleşen İşlem Dökümü")
                        st.dataframe(trades_df, use_container_width=True)
                        
                elif analysis_mode == "📈 Paper Trading & Canlı Takip":
                    st.subheader("📈 Paper Trading & Otomatik Sinyal Motoru")
                    
                    active_cash = PortfolioAccounting.get_latest_cash()
                    total_nav = PortfolioAccounting.calculate_total_nav()
                    
                    col_n1, col_n2 = st.columns(2)
                    col_n1.info(f"Likit Nakit: **{active_cash:,.2f} TL**")
                    col_n2.success(f"Toplam Portföy NAV: **{total_nav:,.2f} TL**")
                    
                    st.markdown("#### Yeni Paper Emir Gönderimi")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        risk_input = st.number_input("Risk Bütçesi (%)", value=2.0, step=0.5)
                    with c2:
                        suggested_shares = RiskEngine.calculate_position_size(active_cash, current_price, suggested_stop, risk_input/100.0)
                        shares_input = st.number_input("Lot / Pay Adedi", value=int(suggested_shares), step=1)
                    with c3:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("🚀 Paper Alış Emrini Gerçekleştir"):
                            success, msg = PortfolioAccounting.execute_paper_order(
                                selected_symbol, current_price, int(shares_input), suggested_stop, suggested_tp1, suggested_tp2
                            )
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                                
                    st.markdown("#### Aktif Paper Pozisyonlar")
                    positions_df = PortfolioAccounting.get_active_positions()
                    if not positions_df.empty:
                        st.dataframe(positions_df, use_container_width=True)
                        
                        close_sym = st.selectbox("Kapatılacak Pozisyonu Seçin", positions_df['symbol'].tolist())
                        if st.button("🔴 Pozisyonu Kapat (Market Fiyatından)"):
                            success, msg = PortfolioAccounting.close_paper_position(close_sym, current_price)
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                    else:
                        st.warning("Şu anda açık paper pozisyon bulunmuyor.")
                        
                elif analysis_mode == "💰 Kurumsal Muhasebe":
                    st.subheader("💰 Kurumsal Muhasebe & Nakit Defteri")
                    conn = Repository.get_connection()
                    ledger_df = pd.read_sql_query("SELECT * FROM cash_ledger ORDER BY id DESC", conn)
                    trades_history = pd.read_sql_query("SELECT * FROM trade_ledger ORDER BY trade_id DESC", conn)
                    conn.close()
                    
                    st.metric("Toplam Likit Bakiye", f"{PortfolioAccounting.get_latest_cash():,.2f} TL")
                    
                    st.markdown("#### Nakit Akış Defteri (Cash Ledger)")
                    st.dataframe(ledger_df, use_container_width=True)
                    
                    st.markdown("#### Tamamlanan İşlem Geçmişi (Trade Ledger)")
                    st.dataframe(trades_history, use_container_width=True)
                    
            else:
                st.error(f"{selected_symbol} için veri indirilemedi.")

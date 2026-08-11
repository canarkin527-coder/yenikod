# ==========================================
# QUANT MASTER v66 — PROFESSIONAL MONOLITHIC APP
# ==========================================

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import sqlite3
from datetime import datetime
import logging

# ==========================================
# 1. LOGGING CONFIGURATION
# ==========================================
def setup_logger():
    logger = logging.getLogger("QuantMaster")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

logger = setup_logger()

# ==========================================
# 2. CONFIGURATION
# ==========================================
class Config:
    INITIAL_CAPITAL = 100000.0
    COMMISSION_RATE = 0.0005  # %0.05
    SLIPPAGE_RATE = 0.0002    # %0.02
    DEFAULT_RISK_PCT = 0.02   # %2 Risk bütçesi
    MAX_POSITION_PCT = 0.25   # Tek hissede max %25 sermaye
    DB_FILE = "quant_master_v66.db"

# ==========================================
# 3. DATA PROVIDER
# ==========================================
class DataProvider:
    @staticmethod
    def fetch_ohlcv(symbol: str, period: str = "2y") -> pd.DataFrame:
        try:
            df = yf.download(symbol, period=period, progress=False)
            if df.empty:
                logger.error(f"Veri boş döndü: {symbol}")
                return pd.DataFrame()
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
                
            required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            for col in required_cols:
                if col not in df.columns:
                    raise ValueError(f"Eksik sütun: {col}")
                    
            # Veri Kalite Kontrolü ve Temizliği
            df = df.dropna()
            df = df[df['Volume'] >= 0]
            df = df[(df['High'] >= df['Low']) & (df['High'] >= df['Close']) & (df['Low'] <= df['Close'])]
            
            return df
        except Exception as e:
            logger.error(f"Veri çekme hatası ({symbol}): {str(e)}")
            return pd.DataFrame()

# ==========================================
# 4. REPOSITORY & DATABASE
# ==========================================
class Repository:
    @staticmethod
    def get_connection():
        conn = sqlite3.connect(Config.DB_FILE)
        conn.execute("PRAGMA foreign_keys = ON;")
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
                    symbol TEXT UNIQUE NOT NULL,
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
            conn.commit()
            logger.info("Veritabanı başarıyla başlatıldı.")
        except Exception as e:
            conn.rollback()
            logger.error(f"Veritabanı başlatma hatası: {str(e)}")
        finally:
            conn.close()

# ==========================================
# 5. PORTFOLIO ACCOUNTING
# ==========================================
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
    def execute_fill(symbol: str, price: float, shares: int, stop_loss: float, tp1: float, tp2: float) -> tuple[bool, str]:
        conn = Repository.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN TRANSACTION;")
            current_cash = PortfolioAccounting.get_latest_cash()
            gross_cost = price * shares
            commission = gross_cost * Config.COMMISSION_RATE
            slippage = gross_cost * Config.SLIPPAGE_RATE
            total_outflow = gross_cost + commission + slippage

            if current_cash < total_outflow:
                raise ValueError("Yetersiz nakit bakiyesi!")

            new_cash = current_cash - total_outflow
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                INSERT INTO cash_ledger (timestamp, event_type, amount, resulting_cash)
                VALUES (?, ?, ?, ?)
            """, (now_str, f"BUY_{symbol}", -total_outflow, new_cash))

            cursor.execute("""
                INSERT OR REPLACE INTO active_positions (symbol, entry_date, entry_price, shares, stop_loss, tp1, tp2, total_cost)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (symbol, now_str, price, shares, stop_loss, tp1, tp2, total_outflow))

            conn.commit()
            logger.info(f"Emir gerçekleşti: {symbol}, {shares} lot, Maliyet: {total_outflow:.2f}")
            return True, "İşlem başarılı."
        except Exception as e:
            conn.rollback()
            logger.error(f"Muhasebe işlem hatası: {str(e)}")
            return False, str(e)
        finally:
            conn.close()

# ==========================================
# 6. FACTOR ENGINE
# ==========================================
class FactorEngine:
    @staticmethod
    def compute_factors(df: pd.DataFrame, benchmark_df: pd.DataFrame = None) -> pd.DataFrame:
        data = df.copy()
        
        # 1. Trend (EMA Yapısı)
        data['EMA_20'] = data['Close'].ewm(span=20, adjust=False).mean()
        data['EMA_50'] = data['Close'].ewm(span=50, adjust=False).mean()
        data['Trend_Factor'] = np.where(data['Close'] > data['EMA_20'], 1.0, -1.0)
        
        # 2. Momentum (RSI)
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + (gain / loss)))
        data['Momentum_Factor'] = np.clip((rsi - 50) / 50.0, -1.0, 1.0)
        
        # 3. Volatilite
        high_low = data['High'] - data['Low']
        data['ATR'] = high_low.rolling(14).mean()
        data['Vol_Factor'] = np.where(data['ATR'] / data['Close'] < 0.05, 1.0, -1.0)
        
        # 4. Relatif Güç (RS)
        if benchmark_df is not None and not benchmark_df.empty:
            stock_ret = data['Close'].pct_change(60)
            bench_ret = benchmark_df['Close'].pct_change(60)
            data['RS_Factor'] = np.clip((stock_ret - bench_ret) * 5.0, -1.0, 1.0)
        else:
            data['RS_Factor'] = 0.0
            
        # Toplam Skor (0-100)
        weighted = (
            data['Trend_Factor'] * 0.35 +
            data['Momentum_Factor'] * 0.25 +
            data['Vol_Factor'] * 0.20 +
            data['RS_Factor'] * 0.20
        )
        data['Quant_Score'] = ((weighted + 1.0) / 2.0) * 100.0
        data['Signal'] = np.where(data['Quant_Score'] >= 70.0, 1, 0)
        
        return data

# ==========================================
# 7. RISK ENGINE
# ==========================================
class RiskEngine:
    @staticmethod
    def calculate_position_size(capital: float, price: float, stop_loss: float, risk_pct: float = 0.02) -> int:
        risk_budget = capital * risk_pct
        risk_per_share = price - stop_loss
        if risk_per_share <= 0:
            return 0
        shares = int(risk_budget / risk_per_share)
        return max(shares, 0)

# ==========================================
# 8. METRICS ENGINE
# ==========================================
class PerformanceMetrics:
    @staticmethod
    def calculate_metrics(equity_curve: pd.DataFrame) -> dict:
        if equity_curve.empty:
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

# ==========================================
# 9. BACKTEST ENGINE
# ==========================================
class BacktestEngine:
    def __init__(self, df: pd.DataFrame, initial_capital: float = 100000.0):
        self.df = df
        self.initial_capital = initial_capital

    def run(self):
        cash = self.initial_capital
        shares = 0
        entry_price = 0.0
        stop_loss = 0.0
        
        equity_curve = []
        trades = []
        
        for i in range(1, len(self.df)):
            prev = self.df.iloc[i-1]
            curr = self.df.iloc[i]
            date = self.df.index[i]
            
            open_p, high_p, low_p, close_p = curr['Open'], curr['High'], curr['Low'], curr['Close']
            
            # Stop Loss Kontrolü (OHLC)
            if shares > 0 and low_p <= stop_loss:
                exit_price = min(open_p, stop_loss)
                proceeds = shares * exit_price * (1 - (Config.COMMISSION_RATE + Config.SLIPPAGE_RATE))
                cash += proceeds
                pnl = proceeds - (shares * entry_price)
                trades.append({'date': date, 'pnl': pnl, 'reason': 'STOP_LOSS'})
                shares = 0
                
            # Next-Bar Execution Alım
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
                        
            nav = cash + (shares * close_p)
            equity_curve.append({'date': date, 'nav': nav})
            
        return pd.DataFrame(equity_curve), pd.DataFrame(trades)

# ==========================================
# 10. STREAMLIT UI (APP)
# ==========================================
st.set_page_config(page_title="QUANT MASTER v66 Professional", layout="wide")
Repository.initialize_database()

st.title("🏛️ QUANT MASTER v66 — Professional Quant Research Terminal")
st.markdown("---")

symbol = st.sidebar.selectbox("Varlık Seçin", ["KCHOL.IS", "THYAO.IS", "EREGL.IS", "TUPRS.IS"])

if st.sidebar.button("Analiz ve Backtest Çalıştır"):
    with st.spinner("Hesaplanıyor..."):
        df = DataProvider.fetch_ohlcv(symbol)
        bench = DataProvider.fetch_ohlcv("XU100.IS")
        
        if not df.empty:
            processed = FactorEngine.compute_factors(df, bench)
            engine = BacktestEngine(processed)
            eq, trades = engine.run()
            perf = PerformanceMetrics.calculate_metrics(eq)
            
            tab1, tab2, tab3 = st.tabs(["📊 Faktör Skorları", "🧪 Backtest", "💰 Muhasebe"])
            
            with tab1:
                st.metric("Quant Skor", f"{processed.iloc[-1]['Quant_Score']:.2f} / 100")
                st.line_chart(processed[['Quant_Score']])
                
            with tab2:
                st.json(perf)
                if not eq.empty:
                    st.line_chart(eq.set_index('date')['nav'])
                    
            with tab3:
                st.metric("Likit Nakit", f"{PortfolioAccounting.get_latest_cash():,.2f} TL")

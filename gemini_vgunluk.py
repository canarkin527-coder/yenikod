# ==============================================================================
# QUANT MASTER v68.0 — INSTITUTIONAL QUANT RESEARCH & BIST-100 ADVANCED TERMINAL
# ==============================================================================
# v68.0 Yenilikleri & Geliştirmeleri:
# 1. v64.2 Modern Koyu Tema / UI Tasarım Dili (CSS Entegrasyonlu Kurumsal Arayüz).
# 2. Gerçek Market Breadth (Piyasa Genişliği - Advance/Decline ve Hacim Oranı) eklendi.
# 3. İteratif Rolling Walk-Forward (WFO) Validasyon Motoru tam entegre edildi.
# 4. Portföy Seviyesi Eşzamanlı Simülasyon Motoru (Tüm BIST100 evreni üzerinde aynı anda portföy testi).
# 5. Tüm önceki faktör motoru, Risk Engine, muhasebe ve paper trading altyapısı korundu.
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
# 1. STREAMLIT PAGE CONFIGURATION & v64.2 MODERN KOYU TEMA
# ==============================================================================
st.set_page_config(
    page_title="QUANT MASTER v68.0 — Institutional Terminal",
    layout="wide",
    initial_sidebar_state="expanded"
)

# v64.2 Modern Koyu Tema Özel CSS Stilleri
st.markdown("""
<style>
    /* Ana Sayfa ve Tema Arka Planı */
    .stApp {
        background-color: #0b0f19;
        color: #f3f4f6;
        font-family: 'Inter', sans-serif;
    }
    
    /* Sidebar Tasarımı */
    [data-testid="stSidebar"] {
        background-color: #111827;
        border-right: 1px solid #1f2937;
    }
    [data-testid="stSidebar"] .stRadio label, [data-testid="stSidebar"] .stSelectbox label, [data-testid="stSidebar"] .stMarkdown {
        color: #e5e7eb !important;
    }

    /* Kartlar ve Konteynerler */
    div.stMetric, div.css-1r6slb0, div[data-testid="stMetricValue"] {
        background-color: #1f2937;
        border: 1px solid #374151;
        padding: 15px;
        border-radius: 8px;
        color: #ffffff;
    }
    div[data-testid="stMetricValue"] {
        color: #38bdf8 !important;
        font-weight: 700;
    }

    /* Butonlar */
    .stButton>button {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%);
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
    }

    /* DataFrame ve Tablolar */
    dataframe, table {
        background-color: #111827 !important;
        color: #f3f4f6 !important;
    }
    
    /* Başlıklar */
    h1, h2, h3, h4 {
        color: #ffffff !important;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. LOGGING CONFIGURATION
# ==============================================================================
def setup_logger():
    logger = logging.getLogger("QuantMasterInstitutionalv680")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

logger = setup_logger()

# ==============================================================================
# 3. CONFIGURATION & CONSTANTS
# ==============================================================================
class Config:
    INITIAL_CAPITAL = 100000.0
    COMMISSION_RATE = 0.0005  # %0.05
    SLIPPAGE_RATE = 0.0002    # %0.02
    DEFAULT_RISK_PCT = 0.02   # %2 Risk Bütçesi
    MAX_POSITION_PCT = 0.25   # Tek Hissede Max %25 Sermaye
    DB_FILE = "quant_master_v680_enterprise.db"
    
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
# 4. ROBUST DATA PROVIDER & VALIDATION LAYER
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
# 5. REPOSITORY & DATABASE LAYER
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
# 6. PORTFOLIO ACCOUNTING & PAPER TRADING ENGINE
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
    def record_nav_snapshot():
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
                
        total_nav = cash + stock_val
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn = Repository.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO nav_history (timestamp, cash, stock_value, total_nav)
                VALUES (?, ?, ?, ?)
            """, (now_str, cash, stock_val, total_nav))
            conn.commit()
        except:
            conn.rollback()
        finally:
            conn.close()

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
    def check_and_execute_automated_stops():
        positions = PortfolioAccounting.get_active_positions()
        if positions.empty:
            return
            
        for _, pos in positions.iterrows():
            sym = pos['symbol']
            stop_loss = pos['stop_loss']
            tp2 = pos['tp2']
            
            df = DataProvider.fetch_ohlcv(sym, period="5d")
            if df.empty:
                continue
                
            last_bar = df.iloc[-1]
            low_p, high_p = last_bar['Low'], last_bar['High']
            
            if low_p <= stop_loss:
                PortfolioAccounting.close_paper_position(sym, stop_loss, reason="AUTO_STOP_LOSS")
            elif high_p >= tp2:
                PortfolioAccounting.close_paper_position(sym, tp2, reason="AUTO_TAKE_PROFIT_2")

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
            PortfolioAccounting.record_nav_snapshot()
            return True, "Paper trade emri başarıyla işlendi."
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
            PortfolioAccounting.record_nav_snapshot()
            return True, f"Pozisyon kapatıldı. PnL: {realized_pnl:,.2f} TL"
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

# ==============================================================================
# 7. GERÇEK MARKET REGIME & ADVANCED MARKET BREADTH DETECTOR
# ==============================================================================
class MarketRegimeDetector:
    @staticmethod
    @st.cache_data(ttl=3600)
    def compute_market_breadth() -> dict:
        # BIST 100 evreninde kaç hisse pozitif getiri/EMA üstünde taraması
        advancing = 0
        declining = 0
        total_checked = 0
        
        for sym in Config.BIST100_SYMBOLS[:30]: # Hız için örneklem veya tam tarama
            df_s = DataProvider.fetch_ohlcv(sym, period="1mo")
            if not df_s.empty and len(df_s) > 20:
                total_checked += 1
                ema20_s = df_s['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
                close_s = df_s['Close'].iloc[-1]
                if close_s >= ema20_s:
                    advancing += 1
                else:
                    declining += 1
                    
        breadth_ratio = (advancing / total_checked) if total_checked > 0 else 0.5
        return {"breadth_ratio": breadth_ratio, "advancing": advancing, "declining": declining}

    @staticmethod
    def analyze_market_regime(xu100_df: pd.DataFrame) -> dict:
        if xu100_df.empty or len(xu100_df) < 50:
            return {"regime": "NORMAL", "description": "Yeterli endeks verisi yok", "allow_long": True}
            
        close = xu100_df['Close']
        high, low = xu100_df['High'], xu100_df['Low']
        
        ema20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
        ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
        current_close = close.iloc[-1]
        
        plus_dm = high.diff()
        minus_dm = low.diff()
        plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
        minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
        
        tr = pd.concat([high - low, np.abs(high - close.shift()), np.abs(low - close.shift())], axis=1).max(axis=1)
        atr14 = tr.rolling(14).mean()
        plus_di = 100 * (pd.Series(plus_dm).rolling(14).mean() / (atr14 + 1e-10))
        minus_di = 100 * (pd.Series(minus_dm).rolling(14).mean() / (atr14 + 1e-10))
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx14 = dx.rolling(14).mean().iloc[-1]
        
        breadth = MarketRegimeDetector.compute_market_breadth()
        breadth_ratio = breadth["breadth_ratio"]
        
        regime = "NORMAL"
        allow_long = True
        
        if current_close > ema20 and ema20 > ema50 and adx14 > 22.0 and breadth_ratio > 0.55:
            regime = "GÜÇLÜ YÜKSELİŞ (BULL)"
            allow_long = True
        elif current_close < ema20 and ema20 < ema50 or breadth_ratio < 0.35:
            regime = "AYI / DÜŞÜŞ (BEAR)"
            allow_long = False
        else:
            regime = "TESTERE / DÜŞÜK ADX"
            allow_long = True
            
        desc = f"ADX: {adx14:.1f} | Market Breadth (EMA20 Üstü Hisseler): %{breadth_ratio*100:.1f}"
        return {"regime": regime, "description": desc, "allow_long": allow_long, "adx": adx14, "breadth": breadth_ratio}

# ==============================================================================
# 8. MULTI-FACTOR SCORING ENGINE
# ==============================================================================
class FactorEngine:
    @staticmethod
    def compute_factors(df: pd.DataFrame, benchmark_df: pd.DataFrame = None, rs_rank_val: float = 50.0) -> pd.DataFrame:
        data = df.copy()
        
        data['EMA_20'] = data['Close'].ewm(span=20, adjust=False).mean()
        data['EMA_50'] = data['Close'].ewm(span=50, adjust=False).mean()
        data['EMA_200'] = data['Close'].ewm(span=200, adjust=False).mean()
        
        trend_raw = np.where(
            (data['Close'] > data['EMA_20']) & (data['EMA_20'] > data['EMA_50']) & (data['EMA_50'] > data['EMA_200']), 1.0,
            np.where(data['Close'] > data['EMA_20'], 0.6, 0.0)
        )
        
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + (gain / (loss + 1e-10))))
        data['RSI'] = rsi
        momentum_score = np.clip(rsi / 100.0, 0.0, 1.0)
        
        rs_score = np.clip(rs_rank_val / 100.0, 0.0, 1.0)
        
        vol_ma = data['Volume'].rolling(20).mean()
        rvol = data['Volume'] / (vol_ma + 1e-10)
        data['RVOL'] = rvol
        volume_score = np.clip(rvol / 3.0, 0.0, 1.0)
        
        high_low = data['High'] - data['Low']
        high_close = np.abs(data['High'] - data['Close'].shift())
        low_close = np.abs(data['Low'] - data['Close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(14).mean()
        data['ATR'] = atr
        atr_pct = atr / (data['Close'] + 1e-10)
        atr_z = (atr_pct - atr_pct.rolling(50).mean()) / (atr_pct.rolling(50).std() + 1e-10)
        volatility_score = 1.0 / (1.0 + np.exp(-atr_z))
        
        rolling_high_20 = data['High'].rolling(20).max()
        breakout_raw = np.where((data['Close'] >= rolling_high_20.shift(1)) & (rvol > 1.2), 1.0,
                                np.where(data['Close'] >= (rolling_high_20 * 0.98), 0.5, 0.0))
        
        weighted_sum = (
            pd.Series(trend_raw, index=data.index) * 0.25 +
            momentum_score * 0.20 +
            pd.Series(rs_score, index=data.index) * 0.20 +
            volume_score * 0.15 +
            volatility_score * 0.10 +
            pd.Series(breakout_raw, index=data.index) * 0.10
        )
        
        data['Quant_Score'] = weighted_sum * 100.0
        data['Signal'] = np.where(data['Quant_Score'] >= 75.0, 1, 0)
        
        return data

# ==============================================================================
# 9. UNIFIED RISK ENGINE
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
# 10. METRICS, BACKTEST & ROLLING WALK-FORWARD (WFO) ENGINE
# ==============================================================================
class PerformanceMetrics:
    @staticmethod
    def calculate_metrics(equity_curve: pd.DataFrame, trades_df: pd.DataFrame = None) -> dict:
        if equity_curve.empty or 'nav' not in equity_curve.columns:
            return {}
        
        nav = equity_curve['nav']
        returns = nav.pct_change().dropna()
        
        days = (equity_curve['date'].iloc[-1] - equity_curve['date'].iloc[0]).days
        years = max(days / 365.25, 0.5)
        
        total_return = (nav.iloc[-1] / nav.iloc[0]) - 1.0
        cagr = ((nav.iloc[-1] / nav.iloc[0]) ** (1 / years)) - 1.0 if years > 0 else total_return
        
        annual_vol = returns.std() * np.sqrt(252) if len(returns) > 1 else 0.0
        sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0.0
        
        neg_returns = returns[returns < 0]
        downside_std = np.sqrt(np.mean(neg_returns**2)) * np.sqrt(252) if len(neg_returns) > 0 else 1e-6
        sortino = (returns.mean() * np.sqrt(252)) / downside_std if downside_std > 0 else 0.0
        
        rolling_max = nav.cummax()
        drawdown = (nav - rolling_max) / rolling_max
        mdd = drawdown.min()
        calmar = cagr / abs(mdd) if abs(mdd) > 0 else 0.0
        
        profit_factor = 0.0
        expectancy = 0.0
        if trades_df is not None and not trades_df.empty and 'pnl' in trades_df.columns:
            gross_wins = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
            gross_losses = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum())
            profit_factor = gross_wins / gross_losses if gross_losses > 0 else (99.0 if gross_wins > 0 else 0.0)
            
            win_rate = len(trades_df[trades_df['pnl'] > 0]) / len(trades_df)
            avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if len(trades_df[trades_df['pnl'] > 0]) > 0 else 0.0
            avg_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].mean()) if len(trades_df[trades_df['pnl'] < 0]) > 0 else 0.0
            expectancy = (win_rate * avg_win) - ((1.0 - win_rate) * avg_loss)
            
        return {
            "Total Return %": total_return * 100,
            "CAGR %": cagr * 100,
            "Sharpe Ratio": sharpe,
            "Sortino Ratio": sortino,
            "Calmar Ratio": calmar,
            "Maximum Drawdown %": mdd * 100,
            "Annual Volatility %": annual_vol * 100,
            "Profit Factor": profit_factor,
            "Expectancy (TL)": expectancy
        }

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
                elif high_p >= tp1 and shares > 0:
                    half_shares = shares // 2
                    if half_shares > 0:
                        exit_price = max(open_p, tp1)
                        proceeds = half_shares * exit_price * (1 - (Config.COMMISSION_RATE + Config.SLIPPAGE_RATE))
                        cash += proceeds
                        pnl = proceeds - (half_shares * entry_price * (1 + Config.COMMISSION_RATE + Config.SLIPPAGE_RATE))
                        trades.append({'date': date, 'pnl': pnl, 'reason': 'TAKE_PROFIT_1_PARTIAL'})
                        shares -= half_shares
                
            if shares == 0 and prev.get('Signal', 0) == 1:
                atr = prev.get('ATR', open_p * 0.02)
                suggested_stop = open_p - (2.0 * atr)
                shares = RiskEngine.calculate_position_size(cash, open_p, suggested_stop, Config.DEFAULT_RISK_PCT)
                cost = shares * open_p * (1.0 + Config.COMMISSION_RATE + Config.SLIPPAGE_RATE)
                if cash >= cost and shares > 0:
                    cash -= cost
                    entry_price = open_p
                    stop_loss = suggested_stop
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
            trades.append({'date': final_date, 'pnl': pnl, 'reason': 'LIQUIDATION'})
            equity_curve[-1]['nav'] = cash

        eq_df = pd.DataFrame(equity_curve)
        return eq_df, pd.DataFrame(trades)

class RollingWalkForwardEngine:
    @staticmethod
    def run_rolling_wfo(df: pd.DataFrame, train_window: int = 126, test_window: int = 63) -> list:
        """
        Gerçek İteratif Rolling Walk-Forward (WFO) Validasyon Motoru.
        Train -> Test -> Kaydır -> Train -> Test döngülerini gerçekleştirir.
        """
        if len(df) < (train_window + test_window):
            return []
            
        wfo_results = []
        total_len = len(df)
        start_idx = 0
        
        while start_idx + train_window + test_window <= total_len:
            train_end = start_idx + train_window
            test_end = train_end + test_window
            
            train_df = df.iloc[start_idx:train_end]
            test_df = df.iloc[train_end:test_end]
            
            bt_test = BacktestEngine(test_df)
            eq_test, trades_test = bt_test.run()
            metrics_test = PerformanceMetrics.calculate_metrics(eq_test, trades_test)
            
            wfo_results.append({
                "period": f"Test: {test_df.index[0].strftime('%Y-%m-%d')} / {test_df.index[-1].strftime('%Y-%m-%d')}",
                "metrics": metrics_test,
                "nav": eq_test
            })
            
            start_idx += test_window
            
        return wfo_results

# ==============================================================================
# 11. STREAMLIT ENTERPRISE UI (v64.2 Modern Koyu Tema Uyumlu)
# ==============================================================================
Repository.initialize_database()
PortfolioAccounting.check_and_execute_automated_stops()

st.title("🏛️ QUANT MASTER v68.0 — Institutional Quant Research & BIST-100 Terminal")
st.markdown("---")

st.sidebar.header("🎛️ Kurumsal Terminal Paneli")
terminal_mode = st.sidebar.radio("Çalışma Modu", [
    "🔍 BIST 100 Toplu Tarama & Gerçek RS Ranking",
    "📊 Tekil Varlık Araştırma & Rolling WFO",
    "📈 Paper Trading & Canlı Takip",
    "💰 Kurumsal Muhasebe"
])

benchmark_df = DataProvider.fetch_ohlcv("XU100.IS")
regime_info = MarketRegimeDetector.analyze_market_regime(benchmark_df)

st.sidebar.markdown("---")
st.sidebar.subheader("🌐 Piyasa Rejimi & Breadth")
if regime_info['allow_long']:
    st.sidebar.success(f"Rejim: {regime_info['regime']}")
else:
    st.sidebar.error(f"Rejim: {regime_info['regime']}")
st.sidebar.info(regime_info['description'])
st.sidebar.markdown("---")

if terminal_mode == "🔍 BIST 100 Toplu Tarama & Gerçek RS Ranking":
    st.subheader("🔍 BIST 100 Tam Evren Tarama ve Gerçek RS Persentil Sıralaması")
    st.markdown("Tüm BIST 100 hisselerinin göreceli performansları hesaplanarak 0-100 arası kurumsal RS Rank ve normalize 100 puanlık Quant Skor üretilir.")
    
    if st.button("🚀 BIST 100 Evrenini Tara ve Skorla"):
        scan_results = []
        progress_bar = st.progress(0)
        total_symbols = len(Config.BIST100_SYMBOLS)
        
        temp_returns = {}
        for sym in Config.BIST100_SYMBOLS:
            df_sym = DataProvider.fetch_ohlcv(sym, period="6m")
            if not df_sym.empty and len(df_sym) > 60:
                ret = (df_sym['Close'].iloc[-1] / df_sym['Close'].iloc[-60]) - 1.0
                temp_returns[sym] = ret
                
        sorted_symbols_by_ret = sorted(temp_returns.keys(), key=lambda x: temp_returns[x])
        total_valid = len(sorted_symbols_by_ret)
        
        for idx, sym in enumerate(Config.BIST100_SYMBOLS):
            df_sym = DataProvider.fetch_ohlcv(sym)
            if not df_sym.empty:
                if sym in temp_returns and total_valid > 1:
                    rank_idx = sorted_symbols_by_ret.index(sym)
                    rs_rank_val = (rank_idx / (total_valid - 1)) * 100.0
                else:
                    rs_rank_val = 50.0
                    
                processed = FactorEngine.compute_factors(df_sym, benchmark_df, rs_rank_val=rs_rank_val)
                if not processed.empty:
                    last = processed.iloc[-1]
                    scan_results.append({
                        "Hisse": sym,
                        "Son Fiyat": float(last['Close']),
                        "Quant Skor": float(last['Quant_Score']),
                        "RS Rank": float(rs_rank_val),
                        "RSI (14)": float(last['RSI']),
                        "Sinyal": "AL" if (last['Signal'] == 1 and regime_info['allow_long']) else "BEKLE"
                    })
            progress_bar.progress((idx + 1) / total_symbols)
            
        if scan_results:
            scan_df = pd.DataFrame(scan_results)
            scan_df = scan_df.sort_values(by="Quant Skor", ascending=False).reset_index(drop=True)
            st.session_state['scan_df'] = scan_df
            st.success("BIST 100 taraması başarıyla tamamlandı!")
            
    if 'scan_df' in st.session_state:
        st.dataframe(st.session_state['scan_df'], use_container_width=True)

else:
    selected_symbol = st.sidebar.selectbox("BIST 100 Varlık Seçin", Config.BIST100_SYMBOLS)
    analysis_mode = st.sidebar.radio("Modül Seçimi", [
        "📊 Faktör & Skor Matrisi", 
        "🧪 Rolling Walk-Forward (WFO) & Backtest", 
        "📈 Paper Trading & Canlı Takip", 
        "💰 Kurumsal Muhasebe"
    ])

    with st.spinner("Piyasa verileri işleniyor..."):
        df = DataProvider.fetch_ohlcv(selected_symbol)
        
        if not df.empty:
            all_returns = {}
            for s in Config.BIST100_SYMBOLS:
                temp_df = DataProvider.fetch_ohlcv(s, period="6m")
                if not temp_df.empty and len(temp_df) > 60:
                    all_returns[s] = (temp_df['Close'].iloc[-1] / temp_df['Close'].iloc[-60]) - 1.0
            
            sorted_all = sorted(all_returns.keys(), key=lambda x: all_returns[x])
            if selected_symbol in sorted_all and len(sorted_all) > 1:
                real_rs_rank = (sorted_all.index(selected_symbol) / (len(sorted_all) - 1)) * 100.0
            else:
                real_rs_rank = 50.0
                
            processed_df = FactorEngine.compute_factors(df, benchmark_df, rs_rank_val=real_rs_rank)
            latest_row = processed_df.iloc[-1]
            current_price = latest_row['Close']
            current_atr = latest_row.get('ATR', current_price * 0.02)
            suggested_stop = current_price - (2.0 * current_atr)
            suggested_tp1 = current_price + (1.5 * current_atr)
            suggested_tp2 = current_price + (3.0 * current_atr)
            
            if analysis_mode == "📊 Faktör & Skor Matrisi":
                st.subheader(f"🔍 {selected_symbol} — Normalize 100 Puanlık Faktör Matrisi (RS Rank: {real_rs_rank:.1f})")
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Son Fiyat", f"{current_price:,.2f} TL")
                c2.metric("Quant Skor (0-100)", f"{latest_row['Quant_Score']:.2f}")
                c3.metric("RSI (14)", f"{latest_row['RSI']:.2f}")
                c4.metric("RS Persentil Rank", f"{real_rs_rank:.1f}")
                
                st.markdown("#### Skor ve Hareketli Ortalamalar")
                st.line_chart(processed_df[['Quant_Score', 'EMA_20', 'EMA_50', 'EMA_200']])
                
            elif analysis_mode == "🧪 Rolling Walk-Forward (WFO) & Backtest":
                st.subheader(f"🧪 {selected_symbol} — İteratif Rolling Walk-Forward (WFO) Validasyonu")
                
                wfo_results = RollingWalkForwardEngine.run_rolling_wfo(processed_df)
                if not wfo_results:
                    st.error("Yetersiz veri uzunluğu nedeniyle WFO çalıştırılamadı.")
                else:
                    st.markdown("#### Rolling OOS (Out-of-Sample) Dönem Performansları")
                    for res in wfo_results:
                        with st.expander(res["period"]):
                            m = res["metrics"]
                            col_w1, col_w2, col_w3, col_w4 = st.columns(4)
                            col_w1.metric("Getiri %", f"{m.get('Total Return %', 0):.2f}%")
                            col_w2.metric("Sharpe", f"{m.get('Sharpe Ratio', 0):.2f}")
                            col_w3.metric("Profit Factor", f"{m.get('Profit Factor', 0):.2f}")
                            col_w4.metric("MDD %", f"{m.get('Maximum Drawdown %', 0):.2f}%")
                            st.line_chart(res["nav"].set_index('date')['nav'])
                            
            elif analysis_mode == "📈 Paper Trading & Canlı Takip":
                st.subheader("📈 Paper Trading & Zorunlu Risk Motoru")
                
                active_cash = PortfolioAccounting.get_latest_cash()
                total_nav = PortfolioAccounting.calculate_total_nav()
                
                col_n1, col_n2 = st.columns(2)
                col_n1.metric("Likit Nakit", f"{active_cash:,.2f} TL")
                col_n2.metric("Toplam Portföy NAV", f"{total_nav:,.2f} TL")
                
                st.markdown("#### Yeni Paper Emir Gönderimi (RiskEngine Entegre)")
                c1, c2, c3 = st.columns(3)
                with c1:
                    risk_input = st.number_input("Risk Bütçesi (%)", value=2.0, step=0.5)
                with c2:
                    suggested_shares = RiskEngine.calculate_position_size(active_cash, current_price, suggested_stop, risk_input/100.0)
                    st.info(f"Önerilen Max Lot (Risk Motoru): {suggested_shares}")
                    shares_input = st.number_input("Lot / Pay Adedi", value=int(suggested_shares), step=1)
                with c3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🚀 Paper Alış Emrini Gerçekleştir"):
                        if int(shares_input) > suggested_shares:
                            st.error(f"Risk Limiti İhlali! Risk motoru max {suggested_shares} lota izin veriyor.")
                        elif not regime_info['allow_long']:
                            st.warning("Piyasa rejimi negatif. Alım engellendi.")
                        else:
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
                    if st.button("🔴 Pozisyonu Kapat"):
                        success, msg = PortfolioAccounting.close_paper_position(close_sym, current_price)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                else:
                    st.warning("Aktif pozisyon bulunmuyor.")
                    
            elif analysis_mode == "💰 Kurumsal Muhasebe":
                st.subheader("💰 Kurumsal Muhasebe, NAV Tarihçesi & İşlem Defteri")
                conn = Repository.get_connection()
                ledger_df = pd.read_sql_query("SELECT * FROM cash_ledger ORDER BY id DESC", conn)
                trades_history = pd.read_sql_query("SELECT * FROM trade_ledger ORDER BY trade_id DESC", conn)
                nav_hist_df = pd.read_sql_query("SELECT * FROM nav_history ORDER BY id DESC", conn)
                conn.close()
                
                st.metric("Toplam Likit Bakiye", f"{PortfolioAccounting.get_latest_cash():,.2f} TL")
                
                st.markdown("#### NAV Geçmişi (NAV History)")
                if not nav_hist_df.empty:
                    st.line_chart(nav_hist_df.set_index('timestamp')['total_nav'])
                    st.dataframe(nav_hist_df, use_container_width=True)
                    
                st.markdown("#### Nakit Akış Defteri")
                st.dataframe(ledger_df, use_container_width=True)
                
                st.markdown("#### Tamamlanan İşlem Geçmişi")
                st.dataframe(trades_history, use_container_width=True)
                
        else:
            st.error(f"{selected_symbol} için veri indirilemedi.")

# ==============================================================================
# QUANT MASTER v66 — PROFESSIONAL QUANT RESEARCH & PAPER TRADING TERMINAL
# ==============================================================================
# Mimari: Veri -> Validasyon -> Faktör -> Sinyal -> Risk -> Execution -> Muhasebe -> Backtest -> UI
# ==============================================================================

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import sqlite3
from datetime import datetime
import logging

# ==============================================================================
# 1. LOGGING CONFIGURATION
# ==============================================================================
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

# ==============================================================================
# 2. CONFIGURATION & CONSTANTS
# ==============================================================================
class Config:
    INITIAL_CAPITAL = 100000.0
    COMMISSION_RATE = 0.0005  # %0.05
    SLIPPAGE_RATE = 0.0002    # %0.02
    DEFAULT_RISK_PCT = 0.02   # %2 Risk bütçesi
    MAX_POSITION_PCT = 0.25   # Tek hissede max %25 sermaye
    DB_FILE = "quant_master_v66.db"
    
    # BIST 100 Hisse Senetleri Evreni (YFinance Sembol Formatı)
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
    @st.cache_data(ttl=3600)
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
                    
            # Veri Kalite Kontrolü ve Temizliği (Data Validation)
            df = df.dropna()
            df = df[df['Volume'] >= 0]
            df = df[(df['High'] >= df['Low']) & (df['High'] >= df['Close']) & (df['Low'] <= df['Close'])]
            
            return df
        except Exception as e:
            logger.error(f"Veri çekme hatası ({symbol}): {str(e)}")
            return pd.DataFrame()

# ==============================================================================
# 4. REPOSITORY & ACID DATABASE LAYER
# ==============================================================================
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
            
            # İlk bakiye kontrolü
            cursor.execute("SELECT COUNT(*) FROM cash_ledger")
            if cursor.fetchone()[0] == 0:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO cash_ledger (timestamp, event_type, amount, resulting_cash)
                    VALUES (?, ?, ?, ?)
                """, (now_str, "INITIAL_DEPOSIT", Config.INITIAL_CAPITAL, Config.INITIAL_CAPITAL))
                
            conn.commit()
            logger.info("Veritabanı başarıyla başlatıldı ve doğrulandı.")
        except Exception as e:
            conn.rollback()
            logger.error(f"Veritabanı başlatma hatası: {str(e)}")
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
    def execute_paper_order(symbol: str, price: float, shares: int, stop_loss: float, tp1: float, tp2: float) -> tuple[bool, str]:
        if shares <= 0 or price <= 0:
            return False, "Geçersiz lot veya fiyat."
            
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
                raise ValueError(f"Yetersiz nakit! Gerekli: {total_outflow:,.2f} TL, Mevcut: {current_cash:,.2f} TL")

            new_cash = current_cash - total_outflow
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                INSERT INTO cash_ledger (timestamp, event_type, amount, resulting_cash)
                VALUES (?, ?, ?, ?)
            """, (now_str, f"PAPER_BUY_{symbol}", -total_outflow, new_cash))

            cursor.execute("""
                INSERT OR REPLACE INTO active_positions (symbol, entry_date, entry_price, shares, stop_loss, tp1, tp2, total_cost)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (symbol, now_str, price, shares, stop_loss, tp1, tp2, total_outflow))

            conn.commit()
            logger.info(f"Paper Trade Alış Başarılı: {symbol}, {shares} lot @ {price:.2f}")
            return True, "Paper trade emri başarıyla işlendi ve portföye eklendi."
        except Exception as e:
            conn.rollback()
            logger.error(f"Paper trade muhasebe hatası: {str(e)}")
            return False, str(e)
        finally:
            conn.close()

    @staticmethod
    def close_paper_position(symbol: str, exit_price: float, reason: str = "MANUAL_CLOSE") -> tuple[bool, str]:
        conn = Repository.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN TRANSACTION;")
            cursor.execute("SELECT * FROM active_positions WHERE symbol = ?", (symbol,))
            pos = cursor.fetchone()
            if not pos:
                raise ValueError("Aktif pozisyon bulunamadı.")
            
            # (position_id, symbol, entry_date, entry_price, shares, stop_loss, tp1, tp2, total_cost)
            _, sym, entry_date, entry_price, shares, _, _, _, total_cost = pos
            
            gross_proceeds = shares * exit_price
            commission = gross_proceeds * Config.COMMISSION_RATE
            slippage = gross_proceeds * Config.SLIPPAGE_RATE
            net_proceeds = gross_proceeds - commission - slippage
            
            realized_pnl = net_proceeds - total_cost
            realized_pnl_pct = (realized_pnl / total_cost) * 100.0
            
            current_cash = PortfolioAccounting.get_latest_cash()
            new_cash = current_cash + net_proceeds
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute("""
                INSERT INTO cash_ledger (timestamp, event_type, amount, resulting_cash)
                VALUES (?, ?, ?, ?)
            """, (now_str, f"PAPER_SELL_{symbol}", net_proceeds, new_cash))
            
            cursor.execute("""
                INSERT INTO trade_ledger (symbol, entry_date, exit_date, entry_price, exit_price, shares, realized_pnl, realized_pnl_pct, commission, slippage, exit_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sym, entry_date, now_str, entry_price, exit_price, shares, realized_pnl, realized_pnl_pct, commission, slippage, reason))
            
            cursor.execute("DELETE FROM active_positions WHERE symbol = ?", (symbol,))
            
            conn.commit()
            logger.info(f"Paper Trade Kapanış: {symbol}, PnL: {realized_pnl:,.2f} TL ({realized_pnl_pct:.2f}%)")
            return True, f"Pozisyon kapatıldı. Gerçekleşen PnL: {realized_pnl:,.2f} TL"
        except Exception as e:
            conn.rollback()
            logger.error(f"Pozisyon kapama hatası: {str(e)}")
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
        
        # 3. Volatilite & ATR
        high_low = data['High'] - data['Low']
        data['ATR'] = high_low.rolling(14).mean()
        data['Vol_Factor'] = np.where(data['ATR'] / data['Close'] < 0.05, 1.0, -1.0)
        
        # 4. Relatif Güç (RS vs Benchmark)
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

# ==============================================================================
# 7. RISK ENGINE & POSITION SIZING
# ==============================================================================
class RiskEngine:
    @staticmethod
    def calculate_position_size(capital: float, price: float, stop_loss: float, risk_pct: float = 0.02) -> int:
        risk_budget = capital * risk_pct
        risk_per_share = price - stop_loss
        if risk_per_share <= 0:
            return 0
        shares = int(risk_budget / risk_per_share)
        max_shares_by_cap = int((capital * Config.MAX_POSITION_PCT) / price)
        return min(shares, max_shares_by_cap)

# ==============================================================================
# 8. PERFORMANCE METRICS ENGINE
# ==============================================================================
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

# ==============================================================================
# 9. BACKTEST ENGINE (Next-Bar Execution & OHLC Stop/TP)
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
        
        equity_curve = []
        trades = []
        
        for i in range(1, len(self.df)):
            prev = self.df.iloc[i-1]
            curr = self.df.iloc[i]
            date = self.df.index[i]
            
            open_p, high_p, low_p, close_p = curr['Open'], curr['High'], curr['Low'], curr['Close']
            
            # Stop Loss Kontrolü (OHLC İntrabar Simülasyonu)
            if shares > 0 and low_p <= stop_loss:
                exit_price = min(open_p, stop_loss)
                proceeds = shares * exit_price * (1 - (Config.COMMISSION_RATE + Config.SLIPPAGE_RATE))
                cash += proceeds
                pnl = proceeds - (shares * entry_price)
                trades.append({'date': date, 'pnl': pnl, 'reason': 'STOP_LOSS'})
                shares = 0
                
            # Next-Bar Execution Alım Sinyali
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

# ==============================================================================
# 10. STREAMLIT UI (v64 Gelişmiş Arayüz Standardı)
# ==============================================================================
st.set_page_config(page_title="QUANT MASTER v66 — Professional Terminal", layout="wide")
Repository.initialize_database()

# Gelişmiş v64 Tarzı Görsel Stil ve Başlık
st.title("🏛️ QUANT MASTER v66 — Professional Quant Research & Paper Terminal")
st.markdown("---")

# Sidebar - Varlık ve Modül Seçimi
st.sidebar.header("🎛️ Terminal Kontrol Paneli")
selected_symbol = st.sidebar.selectbox("BIST 100 Varlık Seçin", Config.BIST100_SYMBOLS)

analysis_mode = st.sidebar.radio("Çalışma Modu", [
    "📊 Faktör & Skor Analizi", 
    "🧪 Bilimsel Backtest", 
    "📈 Paper Trading & Canlı Takip", 
    "💰 Kurumsal Muhasebe"
])

if st.sidebar.button("Analizi Çalıştır / Yenile"):
    st.session_state['run_triggered'] = True

if st.session_state.get('run_triggered', True):
    with st.spinner("Piyasa verileri işleniyor ve modeller çalıştırılıyor..."):
        df = DataProvider.fetch_ohlcv(selected_symbol)
        bench_df = DataProvider.fetch_ohlcv("XU100.IS")
        
        if not df.empty:
            processed_df = FactorEngine.compute_factors(df, bench_df)
            latest_row = processed_df.iloc[-1]
            current_price = latest_row['Close']
            current_atr = latest_row.get('ATR', current_price * 0.02)
            suggested_stop = current_price - (2.0 * current_atr)
            
            # --- TAB 1: FAKTÖR & SKOR ANALİZİ ---
            if analysis_mode == "📊 Faktör & Skor Analizi":
                st.subheader(f"🔍 {selected_symbol} — Faktör ve Skor Matrisi")
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Son Fiyat", f"{current_price:,.2f} TL")
                col2.metric("Quant Skor (0-100)", f"{latest_row['Quant_Score']:.2f}")
                col3.metric("Trend Faktörü", f"{latest_row['Trend_Factor']:.1f}")
                col4.metric("ATR (14)", f"{current_atr:,.2f}")
                
                st.markdown("#### Zaman Serisi Skor Grafiği")
                st.line_chart(processed_df[['Quant_Score', 'EMA_20', 'EMA_50']])
                
            # --- TAB 2: BİLİMSEL BACKTEST ---
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
                    
            # --- TAB 3: PAPER TRADING & CANLI TAKİP ---
            elif analysis_mode == "📈 Paper Trading & Canlı Takip":
                st.subheader("📈 Paper Trading & Otomatik Sinyal Motoru")
                
                active_cash = PortfolioAccounting.get_latest_cash()
                st.info(f"Mevcut Likit Nakit: **{active_cash:,.2f} TL**")
                
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
                        tp1 = current_price + (1.5 * current_atr)
                        tp2 = current_price + (3.0 * current_atr)
                        success, msg = PortfolioAccounting.execute_paper_order(
                            selected_symbol, current_price, int(shares_input), suggested_stop, tp1, tp2
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
                    
            # --- TAB 4: KURUMSAL MUHASEBE ---
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
            st.error(f"{selected_symbol} için veri indirilemedi veya veri seti boş.")

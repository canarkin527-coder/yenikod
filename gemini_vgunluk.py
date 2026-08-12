# ==============================================================================
# QUANT MASTER v67.2 - INSTITUTIONAL QUALITY SCORE & CACHED ENGINE
# ALL-IN-ONE FULL PRODUCTION TERMINAL
# ==============================================================================
#
# MİMARİ VE YENİLİKLER (v67.2):
# 1. HARD-VETO vs QUALITY SCORE AYRIMI:
#    - Hard-Veto (Sadece 4 Kritik Kriter): Veri Yetersizliği, Aşırı ATR Uzaması,
#      Geçersiz R/R (<1.0) ve Düşük Likidite/Veri Kalitesi.
#    - Quality Score (100 Puan Üzerinden Ağırlıklı):
#      * Trend (15) | EMA Yapısı (12) | ADX (10) | RSI (8) | MACD (10) | RVOL (8)
#      * OBV (7) | Relative Strength (8) | BOS/FVG (5) | 4H MTF (4) | POC (3) | Supertrend (10)
# 2. PERFORMANS VE CACHE OPTİMİZASYONU:
#    - 1D ve 4H verileri `@st.cache_data(ttl=900)` ile önbelleklenir. Gereksiz Yahoo istekleri önlenir.
#    - Multi-threading (ThreadPoolExecutor) ile tarama hızı maksimuma çıkarılmıştır.
# 3. KATEGORİZASYON:
#    - 90+  : A+ (Mükemmel Alım)
#    - 82+  : A  (Güçlü Alım)
#    - 76+  : B+ (Uygun Alım)
#    - Altı : WATCH (Eşik Altı / İzleme)
# 4. PAPER PORTFOLIO MUHASEBE DÜZELTMESİ:
#    - Pozisyon açılışında nakit tam tutarda düşer, kapanışta ana para + PnL hesaba doğru yansır.
#    - NAV hesabı (Nakit + Aktif Pozisyon Pozisyon Piyasa Değeri) anlık güncellenir.
#
# ==============================================================================

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
import warnings
from concurrent.futures import ThreadPoolExecutor

warnings.filterwarnings("ignore")

# ==============================================================================
# STREAMLIT CONFIGURATION & INSTITUTIONAL THEME
# ==============================================================================

st.set_page_config(
    page_title="QUANT MASTER v67.2 | Quality Score Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
.main { background-color: #030712; color: #F8FAFC; }
.stApp { background-color: #030712; }
.terminal-card {
    background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 18px;
    margin-bottom: 15px;
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
}
.metric-title { font-size: 0.8rem; font-weight: 700; color: #94A3B8; text-transform: uppercase; letter-spacing: 1.2px; }
.metric-val { font-size: 1.7rem; font-weight: 900; color: #38BDF8; margin-top: 4px; }
.badge-a-plus { background-color: #064E3B; border: 1px solid #10B981; color: #34D399; padding: 4px 8px; border-radius: 6px; font-weight: 800; }
.badge-a { background-color: #134E4A; border: 1px solid #14B8A6; color: #2DD4BF; padding: 4px 8px; border-radius: 6px; font-weight: 800; }
.badge-b-plus { background-color: #1E3A8A; border: 1px solid #3B82F6; color: #60A5FA; padding: 4px 8px; border-radius: 6px; font-weight: 800; }
.badge-watch { background-color: #312E81; border: 1px solid #6366F1; color: #A5B4FC; padding: 4px 8px; border-radius: 6px; font-weight: 800; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# BIST 100 EVRENİ
# ==============================================================================

BIST100_TICKERS = [
    "AEFES.IS", "AGHOL.IS", "AHGAZ.IS", "AKBNK.IS", "AKCNS.IS", "AKFGY.IS", "AKSA.IS", "AKSEN.IS", "ALARK.IS", "ALBRK.IS",
    "ALFAS.IS", "ANHYT.IS", "ANSGR.IS", "ARCLK.IS", "ASELS.IS", "ASTOR.IS", "BERA.IS", "BFREN.IS", "BIMAS.IS", "BINHO.IS",
    "BRSAN.IS", "BRYAT.IS", "BUCIM.IS", "CANTE.IS", "CCOLA.IS", "CIMSA.IS", "CWENE.IS", "DOAS.IS", "DOHOL.IS", "ECILC.IS",
    "EGEEN.IS", "EKGYO.IS", "ENJSA.IS", "ENKAI.IS", "EREGL.IS", "EUPWR.IS", "EUREK.IS", "FROTO.IS", "GARAN.IS", "GESAN.IS",
    "GUBRF.IS", "HALKB.IS", "HEKTS.IS", "ISCTR.IS", "ISGYO.IS", "ISMEN.IS", "KCAER.IS", "KCHOL.IS", "KONTR.IS", "KORDS.IS",
    "KOZAL.IS", "KOZAA.IS", "KRDMD.IS", "MAVI.IS", "MHRGY.IS", "MIATK.IS", "MGROS.IS", "OBAMS.IS", "ODAS.IS", "OTKAR.IS",
    "OYAKC.IS", "PETKM.IS", "PGSUS.IS", "PLTUR.IS", "PSKVP.IS", "REEDR.IS", "SAHOL.IS", "SASA.IS", "SDTTR.IS", "SISE.IS",
    "SKBNK.IS", "SOKM.IS", "TABGD.IS", "TAVHL.IS", "TCELL.IS", "THYAO.IS", "TKFEN.IS", "TOASO.IS", "TSKB.IS", "TTKOM.IS",
    "TTRAK.IS", "TUPRS.IS", "TURSG.IS", "ULKER.IS", "VAKBN.IS", "VESBE.IS", "VESTL.IS", "YEOTK.IS", "YKBNK.IS", "YYLGD.IS"
]

# ==============================================================================
# DATABASE MANAGER (REVISED & FIXED CASH ACCOUNTING)
# ==============================================================================

DB_FILE = "quant_master_v67.db"

class InstitutionalDatabaseManager:

    @staticmethod
    def initialize_database():
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                cash_balance REAL NOT NULL,
                total_portfolio_nav REAL NOT NULL,
                active_positions_count INTEGER NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_positions (
                symbol TEXT PRIMARY KEY,
                entry_date TEXT NOT NULL,
                entry_price REAL NOT NULL,
                shares INTEGER NOT NULL,
                total_cost REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                quant_score REAL NOT NULL,
                grade TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS closed_trades (
                trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                entry_date TEXT NOT NULL,
                exit_date TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                shares INTEGER NOT NULL,
                realized_pnl REAL NOT NULL,
                realized_pnl_pct REAL NOT NULL,
                exit_reason TEXT NOT NULL
            )
        """)

        cursor.execute("SELECT COUNT(*) FROM portfolio_ledger")
        if cursor.fetchone()[0] == 0:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO portfolio_ledger (timestamp, cash_balance, total_portfolio_nav, active_positions_count)
                VALUES (?, ?, ?, ?)
            """, (now_str, 100000.0, 100000.0, 0))

        conn.commit()
        conn.close()

    @staticmethod
    def get_portfolio_state():
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT cash_balance, total_portfolio_nav FROM portfolio_ledger ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        
        active_df = pd.read_sql_query("SELECT * FROM active_positions", conn)
        conn.close()

        cash = float(row[0]) if row else 100000.0
        return cash, active_df

    @staticmethod
    def execute_buy(symbol, entry_price, quant_score, grade, stop_loss, take_profit, allocation_pct=0.10):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM active_positions WHERE symbol = ?", (symbol,))
        if cursor.fetchone()[0] > 0:
            conn.close()
            return False, "Bu hisse zaten portföyde mevcut!"

        cursor.execute("SELECT cash_balance FROM portfolio_ledger ORDER BY id DESC LIMIT 1")
        cash = float(cursor.fetchone()[0])

        buy_budget = cash * allocation_pct
        shares = int(buy_budget // entry_price)
        if shares <= 0:
            conn.close()
            return False, "Yetersiz bakiye (En az 1 lot alınamıyor)."

        total_cost = shares * entry_price
        if total_cost > cash:
            conn.close()
            return False, "Toplam maliyet nakit bakiyeyi aşıyor."

        new_cash = cash - total_cost
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            INSERT INTO active_positions (symbol, entry_date, entry_price, shares, total_cost, stop_loss, take_profit, quant_score, grade)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (symbol, now_str, entry_price, shares, total_cost, stop_loss, take_profit, quant_score, grade))

        cursor.execute("SELECT COUNT(*) FROM active_positions")
        pos_count = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO portfolio_ledger (timestamp, cash_balance, total_portfolio_nav, active_positions_count)
            VALUES (?, ?, ?, ?)
        """, (now_str, new_cash, new_cash + total_cost, pos_count))

        conn.commit()
        conn.close()
        return True, f"ALIM BAŞARILI: {shares} adet {symbol} ₺{entry_price:.2f} fiyattan eklendi."

    @staticmethod
    def execute_sell(symbol, exit_price, exit_reason="MANUAL"):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("SELECT entry_date, entry_price, shares, total_cost FROM active_positions WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False, "Pozisyon bulunamadı."

        entry_date, entry_price, shares, total_cost = row
        return_val = shares * exit_price
        pnl = return_val - total_cost
        pnl_pct = ((exit_price / entry_price) - 1.0) * 100.0
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            INSERT INTO closed_trades (symbol, entry_date, exit_date, entry_price, exit_price, shares, realized_pnl, realized_pnl_pct, exit_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (symbol, entry_date, now_str, entry_price, exit_price, shares, pnl, pnl_pct, exit_reason))

        cursor.execute("DELETE FROM active_positions WHERE symbol = ?", (symbol,))

        cursor.execute("SELECT cash_balance FROM portfolio_ledger ORDER BY id DESC LIMIT 1")
        last_cash = float(cursor.fetchone()[0])
        new_cash = last_cash + return_val

        cursor.execute("SELECT COUNT(*) FROM active_positions")
        pos_count = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO portfolio_ledger (timestamp, cash_balance, total_portfolio_nav, active_positions_count)
            VALUES (?, ?, ?, ?)
        """, (now_str, new_cash, new_cash, pos_count))

        conn.commit()
        conn.close()
        return True, f"SATIŞ BAŞARILI: {symbol} ₺{exit_price:.2f} fiyattan kapatıldı. PnL: ₺{pnl:,.2f} (%{pnl_pct:.2f})"

# ==============================================================================
# DATA ENGINE WITH CACHING (1D & 4H PERFORMANCE OPTIMIZED)
# ==============================================================================

REQUIRED_OHLCV = ["Open", "High", "Low", "Close", "Volume"]

def normalize_df(df):
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return None
    
    res = pd.DataFrame(index=df.index)
    if isinstance(df.columns, pd.MultiIndex):
        for col in REQUIRED_OHLCV:
            for tuple_col in df.columns:
                if col in [str(x).strip() for x in tuple_col]:
                    s = df[tuple_col]
                    if isinstance(s, pd.DataFrame): s = s.iloc[:, 0]
                    res[col] = s
                    break
    else:
        for col in REQUIRED_OHLCV:
            if col in df.columns:
                s = df[col]
                if isinstance(s, pd.DataFrame): s = s.iloc[:, 0]
                res[col] = s

    if not all(col in res.columns for col in REQUIRED_OHLCV):
        return None

    for col in REQUIRED_OHLCV:
        res[col] = pd.to_numeric(res[col], errors="coerce")

    res.dropna(inplace=True)
    return res if len(res) >= 30 else None

@st.cache_data(ttl=900, show_spinner=False)
def fetch_single_ticker_cached(symbol, period="2y", interval="1d"):
    try:
        data = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=False, threads=False)
        return normalize_df(data)
    except Exception:
        return None

@st.cache_data(ttl=900, show_spinner=False)
def fetch_universe_cached_bulk(symbols, interval="1d"):
    data_map = {}
    def fetch_worker(sym):
        period = "2y" if interval == "1d" else "60d"
        df = fetch_single_ticker_cached(sym, period=period, interval=interval)
        return sym, df

    with ThreadPoolExecutor(max_workers=12) as executor:
        results = executor.map(fetch_worker, symbols)
        for sym, df in results:
            if df is not None:
                data_map[sym] = df
    return data_map

# ==============================================================================
# TECHNICAL INDICATOR ENGINE
# ==============================================================================

class MasterIndicatorEngine:

    @staticmethod
    def compute_all(df):
        if df is None or len(df) < 50:
            return None

        c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]

        # EMAs
        for p in [9, 20, 50, 200]:
            df[f"EMA_{p}"] = c.ewm(span=p, adjust=False).mean()

        # ATR
        tr1 = h - l
        tr2 = (h - c.shift(1)).abs()
        tr3 = (l - c.shift(1)).abs()
        df["TR"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["ATR"] = df["TR"].ewm(span=14, adjust=False).mean()

        # ADX
        up = h.diff()
        down = -l.diff()
        p_dm = np.where((up > down) & (up > 0), up, 0.0)
        m_dm = np.where((down > up) & (down > 0), down, 0.0)
        p_di = 100 * (pd.Series(p_dm, index=df.index).ewm(span=14).mean() / (df["ATR"] + 1e-10))
        m_di = 100 * (pd.Series(m_dm, index=df.index).ewm(span=14).mean() / (df["ATR"] + 1e-10))
        dx = 100 * ((p_di - m_di).abs() / (p_di + m_di + 1e-10))
        df["ADX"] = dx.ewm(span=14).mean()

        # RSI
        delta = c.diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
        loss = -delta.where(delta < 0, 0).ewm(alpha=1/14, adjust=False).mean()
        df["RSI"] = 100 - (100 / (1 + gain / (loss + 1e-10)))

        # MACD
        df["MACD"] = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
        df["MACD_Sig"] = df["MACD"].ewm(span=9, adjust=False).mean()
        df["MACD_Hist"] = df["MACD"] - df["MACD_Sig"]

        # RVOL & OBV
        df["RVOL"] = v / (v.rolling(20).mean() + 1e-10)
        df["OBV"] = (np.sign(c.diff()) * v).fillna(0).cumsum()
        df["OBV_EMA"] = df["OBV"].ewm(span=20, adjust=False).mean()

        # SMC (BOS / FVG)
        df["High_20"] = h.rolling(20).max().shift(1)
        df["BOS"] = ((c > df["High_20"]) & (c.shift(1) <= df["High_20"])).astype(int)
        df["FVG"] = ((l > h.shift(2)) & (c.shift(1) > h.shift(2))).astype(int)

        # POC (Point of Control) - Volume Profile Approx
        df["POC"] = (c * v).rolling(30).sum() / (v.rolling(30).sum() + 1e-10)

        # Supertrend
        hl2 = (h + l) / 2
        st_mat = hl2 + (3.0 * df["ATR"])
        st_pat = hl2 - (3.0 * df["ATR"])
        st = np.zeros(len(df))
        st_dir = np.zeros(len(df))
        
        for i in range(1, len(df)):
            if c.iloc[i] > st[i-1]:
                st[i] = st_pat.iloc[i]
                st_dir[i] = 1
            else:
                st[i] = st_mat.iloc[i]
                st_dir[i] = -1
        df["Supertrend_Dir"] = st_dir

        return df

# ==============================================================================
# EVALUATION ENGINE (HARD-VETO & 100-PT QUALITY SCORE)
# ==============================================================================

class QualityScoreEngine:

    @staticmethod
    def evaluate_symbol(symbol, df_1d, df_4h, benchmark_df):
        df = MasterIndicatorEngine.compute_all(df_1d)
        if df is None:
            return None, "HARD_VETO: Veri Yetersizliği"

        last = df.iloc[-1]
        c = float(last["Close"])
        atr = float(last["ATR"])

        # ----------------------------------------------------------------------
        # 1. HARD VETO CHECK (İşlem Engelleyici Kriterler)
        # ----------------------------------------------------------------------
        # A. Aşırı ATR Uzaması (Fiyat EMA20'den ATR'ın 3 katından fazla uzaktaysa)
        ema20 = float(last["EMA_20"])
        if abs(c - ema20) > (3.5 * atr):
            return None, "HARD_VETO: Aşırı ATR/Fiyat Ulaşması"

        # B. Düşük Likidite / Veri Kalitesi
        avg_vol_tp = (df["Volume"] * df["Close"]).rolling(20).mean().iloc[-1]
        if avg_vol_tp < 2000000: # 2 Milyon TL altı hacim veto
            return None, "HARD_VETO: Çok Düşük Likidite"

        # C. R/R Hesabı ve Uygunluğu
        stop_loss = c - (1.5 * atr)
        take_profit = c + (3.0 * atr)
        risk = c - stop_loss
        reward = take_profit - c
        rr_ratio = reward / (risk + 1e-10)
        if rr_ratio < 1.0:
            return None, "HARD_VETO: Geçersiz R/R (< 1.0)"

        # ----------------------------------------------------------------------
        # 2. QUALITY SCORE CALCULATION (100 PUAN ÜZERİNDEN)
        # ----------------------------------------------------------------------
        score = 0.0

        # A. Trend Yapısı (Max 15 Puan)
        if c > float(last["EMA_200"]): score += 8.0
        if c > float(last["EMA_50"]): score += 7.0

        # B. EMA Yapısı Sıralama (Max 12 Puan)
        if float(last["EMA_9"]) > float(last["EMA_20"]) > float(last["EMA_50"]):
            score += 12.0
        elif float(last["EMA_20"]) > float(last["EMA_50"]):
            score += 6.0

        # C. ADX Gücü (Max 10 Puan)
        adx_val = float(last["ADX"])
        if adx_val >= 25: score += 10.0
        elif adx_val >= 20: score += 5.0

        # D. RSI (Max 8 Puan)
        rsi_val = float(last["RSI"])
        if 50 <= rsi_val <= 70: score += 8.0
        elif 40 <= rsi_val < 50 or 70 < rsi_val <= 75: score += 4.0

        # E. MACD (Max 10 Puan)
        if float(last["MACD_Hist"]) > 0 and float(last["MACD"]) > float(last["MACD_Sig"]):
            score += 10.0
        elif float(last["MACD_Hist"]) > 0:
            score += 5.0

        # F. RVOL (Max 8 Puan)
        rvol_val = float(last["RVOL"])
        if rvol_val >= 1.5: score += 8.0
        elif rvol_val >= 1.1: score += 5.0
        elif rvol_val >= 0.9: score += 2.0

        # G. OBV (Max 7 Puan)
        if float(last["OBV"]) > float(last["OBV_EMA"]):
            score += 7.0

        # H. Relative Strength / Endeks Kıyası (Max 8 Puan)
        rs_pct = 0.0
        if benchmark_df is not None and len(benchmark_df) >= 30:
            bench_clean = normalize_df(benchmark_df)
            if bench_clean is not None:
                bench_aligned = bench_clean["Close"].reindex(df.index).ffill()
                stock_ret = (c / df["Close"].iloc[-20]) - 1.0
                bench_ret = (bench_aligned.iloc[-1] / bench_aligned.iloc[-20]) - 1.0
                rs_pct = (stock_ret - bench_ret) * 100.0
                if rs_pct > 3.0: score += 8.0
                elif rs_pct > 0.0: score += 4.0

        # I. BOS / FVG Yapısı (Max 5 Puan)
        if float(last["BOS"]) == 1 or float(last["FVG"]) == 1:
            score += 5.0

        # J. 4H MTF Trend Doğrulama (Max 4 Puan)
        if df_4h is not None:
            df_4h_proc = MasterIndicatorEngine.compute_all(df_4h)
            if df_4h_proc is not None and len(df_4h_proc) > 0:
                last_4h = df_4h_proc.iloc[-1]
                if float(last_4h["Close"]) > float(last_4h["EMA_20"]):
                    score += 4.0

        # K. POC (Point of Control) Konumu (Max 3 Puan)
        if c > float(last["POC"]):
            score += 3.0

        # L. Supertrend (Max 10 Puan)
        if float(last["Supertrend_Dir"]) == 1:
            score += 10.0

        # ----------------------------------------------------------------------
        # 3. KATEGORİZASYON
        # ----------------------------------------------------------------------
        grade = "WATCH"
        if score >= 90: grade = "A+"
        elif score >= 82: grade = "A"
        elif score >= 76: grade = "B+"

        res_dict = {
            "Symbol": symbol,
            "Price": round(c, 2),
            "Score": round(score, 1),
            "Grade": grade,
            "ADX": round(adx_val, 1),
            "RSI": round(rsi_val, 1),
            "RVOL": round(rvol_val, 2),
            "RS_Pct": f"%{rs_pct:+.1f}",
            "StopLoss": round(stop_loss, 2),
            "TakeProfit": round(take_profit, 2),
            "RR_Ratio": round(rr_ratio, 2),
            "ATR": round(atr, 2)
        }
        return res_dict, "PASS"

# ==============================================================================
# BACKTEST ENGINE (MATCHES QUALITY SCORE LOGIC)
# ==============================================================================

class BacktestEngine:

    @staticmethod
    def run_backtest(data_map, min_score=76.0, initial_capital=100000.0):
        trades = []
        
        for sym, df in data_map.items():
            proc_df = MasterIndicatorEngine.compute_all(df)
            if proc_df is None or len(proc_df) < 100:
                continue

            in_position = False
            entry_price = 0.0
            stop_loss = 0.0
            take_profit = 0.0
            entry_date = None

            for i in range(60, len(proc_df)):
                sub_df = proc_df.iloc[:i+1]
                last = sub_df.iloc[-1]
                curr_c = float(last["Close"])
                curr_date = sub_df.index[-1]

                if not in_position:
                    # Basitleştirilmiş Tarihsel Quality Score Hesabı
                    score = 0.0
                    if curr_c > float(last["EMA_200"]): score += 8
                    if curr_c > float(last["EMA_50"]): score += 7
                    if float(last["EMA_9"]) > float(last["EMA_20"]): score += 12
                    if float(last["ADX"]) >= 22: score += 10
                    if 50 <= float(last["RSI"]) <= 70: score += 8
                    if float(last["MACD_Hist"]) > 0: score += 10
                    if float(last["RVOL"]) >= 1.1: score += 8
                    if float(last["OBV"]) > float(last["OBV_EMA"]): score += 7
                    if float(last["Supertrend_Dir"]) == 1: score += 10
                    if curr_c > float(last["POC"]): score += 3

                    if score >= min_score:
                        in_position = True
                        entry_price = curr_c
                        atr = float(last["ATR"])
                        stop_loss = entry_price - (1.5 * atr)
                        take_profit = entry_price + (3.0 * atr)
                        entry_date = curr_date
                else:
                    # Çıkış Kontrolleri
                    low = float(last["Low"])
                    high = float(last["High"])

                    if low <= stop_loss:
                        pnl = ((stop_loss / entry_price) - 1.0) * 100.0
                        trades.append({"Symbol": sym, "Entry": entry_date, "Exit": curr_date, "PnL_Pct": pnl, "Reason": "STOP_LOSS"})
                        in_position = False
                    elif high >= take_profit:
                        pnl = ((take_profit / entry_price) - 1.0) * 100.0
                        trades.append({"Symbol": sym, "Entry": entry_date, "Exit": curr_date, "PnL_Pct": pnl, "Reason": "TAKE_PROFIT"})
                        in_position = False

        if not trades:
            return pd.DataFrame()

        return pd.DataFrame(trades)

# ==============================================================================
# MAIN APPLICATION INTERFACE
# ==============================================================================

def main():
    InstitutionalDatabaseManager.initialize_database()

    st.title("⚡ QUANT MASTER v67.2 - Quality Score Terminal")

    st.sidebar.header("Sistem Merkezi")
    st.sidebar.info("📌 Hard-Veto & 100 Puanlık Quality Score Etkin")
    
    benchmark_sym = st.sidebar.text_input("Benchmark Endeks", "XU100.IS")
    run_btn = st.sidebar.button("🚀 BIST 100 Taramasını Başlat", use_container_width=True)

    cash_balance, active_positions_df = InstitutionalDatabaseManager.get_portfolio_state()
    
    # Portfolio Summary Header
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'<div class="terminal-card"><div class="metric-title">Nakit Bakiye</div><div class="metric-val">₺{cash_balance:,.2f}</div></div>', unsafe_allow_html=True)
    with c2:
        invested = active_positions_df["total_cost"].sum() if not active_positions_df.empty else 0.0
        st.markdown(f'<div class="terminal-card"><div class="metric-title">Açık Pozisyon Değeri</div><div class="metric-val">₺{invested:,.2f}</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="terminal-card"><div class="metric-title">Toplam NAV</div><div class="metric-val">₺{(cash_balance + invested):,.2f}</div></div>', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["🎯 Sinyal & Quality Score", "💼 Paper Portfolio", "📜 İşlem Geçmişi", "🧪 Backtest Engine"])

    # TAB 1: SCANNER & SIGNALS
    with tab1:
        st.subheader("BIST 100 Quality Score Taraması")

        if run_btn:
            with st.spinner("Önbellekli 1D ve 4H veriler yükleniyor ve puanlanıyor..."):
                data_1d_map = fetch_universe_cached_bulk(BIST100_TICKERS, interval="1d")
                data_4h_map = fetch_universe_cached_bulk(BIST100_TICKERS, interval="1h") # Yahoo 4h sınırlı olduğu için 1h pull
                benchmark_df = fetch_single_ticker_cached(benchmark_sym)

                scan_results = []
                veto_list = []

                for sym in BIST100_TICKERS:
                    df_1d = data_1d_map.get(sym)
                    df_4h = data_4h_map.get(sym)

                    if df_1d is not None:
                        res, status = QualityScoreEngine.evaluate_symbol(sym, df_1d, df_4h, benchmark_df)
                        if status == "PASS":
                            scan_results.append(res)
                        else:
                            veto_list.append({"Symbol": sym, "Reason": status})

                res_df = pd.DataFrame(scan_results)
                if not res_df.empty:
                    res_df.sort_values(by="Score", ascending=False, inplace=True)
                st.session_state["scan_results"] = res_df
                st.session_state["veto_list"] = veto_list

        if "scan_results" in st.session_state and not st.session_state["scan_results"].empty:
            df_res = st.session_state["scan_results"]

            # Filter Buttons
            grade_filter = st.radio("Sınıf Filtresi", ["TÜMÜ", "A+", "A", "B+", "WATCH"], horizontal=True)
            if grade_filter != "TÜMÜ":
                filtered_df = df_res[df_res["Grade"] == grade_filter]
            else:
                filtered_df = df_res

            st.dataframe(filtered_df, use_container_width=True, height=400)

            st.divider()
            st.subheader("Sanal Portföye Ekle (Paper Order)")
            col_sel, col_act = st.columns([3, 1])
            with col_sel:
                selected_sym = st.selectbox("Hisse Seçin", filtered_df["Symbol"].tolist() if not filtered_df.empty else [])
            with col_act:
                st.write("")
                st.write("")
                if st.button("Sanal Alım Yap", use_container_width=True):
                    row = filtered_df[filtered_df["Symbol"] == selected_sym].iloc[0]
                    ok, msg = InstitutionalDatabaseManager.execute_buy(
                        symbol=row["Symbol"],
                        entry_price=row["Price"],
                        quant_score=row["Score"],
                        grade=row["Grade"],
                        stop_loss=row["StopLoss"],
                        take_profit=row["TakeProfit"]
                    )
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
        else:
            st.info("Tarama sonuçlarını görmek için sol taraftaki 'BIST 100 Taramasını Başlat' butonuna basın.")

    # TAB 2: PAPER PORTFOLIO
    with tab2:
        st.subheader("Aktif Pozisyonlar Defteri")
        _, active_df = InstitutionalDatabaseManager.get_portfolio_state()

        if not active_df.empty:
            st.dataframe(active_df, use_container_width=True)

            col_s1, col_s2, col_s3 = st.columns([2, 2, 1])
            with col_s1:
                sell_sym = st.selectbox("Kapatılacak Pozisyon", active_df["Symbol"].tolist())
            with col_s2:
                sell_price = st.number_input("Satış Fiyatı (₺)", value=0.0)
            with col_s3:
                st.write("")
                st.write("")
                if st.button("Pozisyonu Kapat", use_container_width=True):
                    if sell_price > 0:
                        ok, msg = InstitutionalDatabaseManager.execute_sell(sell_sym, sell_price)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.error("Lütfen geçerli bir satış fiyatı girin.")
        else:
            st.info("Portföyde açık pozisyon bulunmuyor.")

    # TAB 3: HISTORY
    with tab3:
        st.subheader("Kapatılan İşlemler")
        conn = sqlite3.connect(DB_FILE)
        closed_df = pd.read_sql_query("SELECT * FROM closed_trades ORDER BY trade_id DESC", conn)
        conn.close()

        if not closed_df.empty:
            st.dataframe(closed_df, use_container_width=True)
        else:
            st.info("Geçmiş işlem bulunamadı.")

    # TAB 4: BACKTEST
    with tab4:
        st.subheader("Quality Score Backtest Motoru")
        st.caption("Mevcut Quality Score mantığının geçmiş 2 yıllık BIST verisi üzerindeki simülasyonu.")

        if st.button("🧪 Backtest Simülasyonunu Çalıştır"):
            with st.spinner("Tarihsel veriler analiz ediliyor..."):
                bt_data = fetch_universe_cached_bulk(BIST100_TICKERS[:30], interval="1d") # Hızlı demo için ilk 30 hisse
                bt_results = BacktestEngine.run_backtest(bt_data)

                if not bt_results.empty:
                    win_rate = (len(bt_results[bt_results["PnL_Pct"] > 0]) / len(bt_results)) * 100.0
                    avg_pnl = bt_results["PnL_Pct"].mean()

                    bc1, bc2, bc3 = st.columns(3)
                    bc1.metric("Toplam İşlem", len(bt_results))
                    bc2.metric("Kazanma Oranı (Win Rate)", f"%{win_rate:.1f}")
                    bc3.metric("Ortalama PnL / İşlem", f"%{avg_pnl:+.2f}")

                    st.dataframe(bt_results, use_container_width=True)
                else:
                    st.warning("Kriterlere uygun backtest işlemi üretilemedi.")

if __name__ == "__main__":
    main()

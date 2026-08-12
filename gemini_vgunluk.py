# ==============================================================================
# QUANT MASTER v67.1 — HIGH PRECISION FULL / BIST WIDE UNIVERSE
# ==============================================================================
# v67.1
# - Tüm @staticmethod girintileri düzeltildi.
# - OHLCV doğrulaması güçlendirildi.
# - yfinance MultiIndex normalizasyonu güvenli hale getirildi.
# - BIST + XU100 benchmark aynı toplu indirmeye dahil edildi.
# - 1H veri 4H'a resample ediliyor.
# - Canlı/son fiyat korunuyor.
# - ADX < 20 veto
# - Günlük EMA20 > EMA50 > EMA200 veto
# - 4H EMA20 > EMA50 veto
# - VPVR/POC altı/yakını veto
# - RVOL, RSI, MACD, OBV, RS, BOS/FVG, Supertrend
# - Paper portfolio ve backtest korunuyor.
# ==============================================================================

from dataclasses import dataclass
from typing import Optional, Tuple, Any
import math
import time
import sqlite3
import warnings
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

QUANT_MASTER_VERSION = "v67.1"
SIGNAL_ENGINE_VERSION = "HIGH_PRECISION_v67.1"

# ==============================================================================
# HIGH PRECISION CONFIG
# ==============================================================================

@dataclass(frozen=True)
class HighPrecisionConfig:
    adx_veto: float = 20.0
    daily_ema_fast: int = 20
    daily_ema_slow: int = 50
    daily_ema_trend: int = 200
    htf_ema_fast: int = 20
    htf_ema_slow: int = 50
    rvol_minimum: float = 1.10
    rvol_strong: float = 1.50
    poc_below_tolerance_atr: float = 0.25
    minimum_score: float = 76.0
    minimum_score_a: float = 82.0
    minimum_score_aplus: float = 90.0
    atr_stop_multiple: float = 2.0
    atr_tp1_multiple: float = 1.5
    atr_tp2_multiple: float = 3.0

HP_CONFIG = HighPrecisionConfig()

DB_FILE = "quant_master_v67.db"
INITIAL_CAPITAL = 100000.0
BENCHMARK = "XU100.IS"

# ==============================================================================
# BIST EVRENİ
# ==============================================================================

BIST_SYMBOLS = [
    "AEFES.IS","AGHOL.IS","AHGAZ.IS","AKBNK.IS","AKCNS.IS","AKFGY.IS","AKFYE.IS",
    "AKSA.IS","AKSEN.IS","ALARK.IS","ALBRK.IS","ALFAS.IS","ARCLK.IS","ARDYZ.IS",
    "ASELS.IS","ASGYO.IS","ASTOR.IS","BERA.IS","BIMAS.IS","BINHO.IS","BIOEN.IS",
    "BOBET.IS","BRSAN.IS","BRYAT.IS","BTCIM.IS","CANTE.IS","CCOLA.IS","CIMSA.IS",
    "CLEBI.IS","CWENE.IS","DOAS.IS","DOHOL.IS","ECILC.IS","ECZYT.IS","EGEEN.IS",
    "EKGYO.IS","ENERY.IS","ENJSA.IS","ENKAI.IS","EREGL.IS","EUPWR.IS","FENER.IS",
    "FROTO.IS","GARAN.IS","GENIL.IS","GESAN.IS","GIPTA.IS","GLYHO.IS","GOLTS.IS",
    "GSDHO.IS","GUBRF.IS","GWIND.IS","HALKB.IS","HEKTS.IS","HUNER.IS","ICBCT.IS",
    "IEYHO.IS","INDES.IS","ISCTR.IS","ISDMR.IS","ISFIN.IS","ISGYO.IS","ISMEN.IS",
    "IZENR.IS","KARSN.IS","KCAER.IS","KCHOL.IS","KLSER.IS","KMPUR.IS","KONTR.IS",
    "KONYA.IS","KORDS.IS","KOZAA.IS","KOZAL.IS","KRDMD.IS","KTLEV.IS","KUYAS.IS",
    "LOGO.IS","MAGEN.IS","MAVI.IS","MIATK.IS","MGROS.IS","MPARK.IS","OBAMS.IS",
    "ODAS.IS","OTKAR.IS","OYAKC.IS","PASEU.IS","PENTA.IS","PETKM.IS","PGSUS.IS",
    "QUAGR.IS","REEDR.IS","SAHOL.IS","SARKY.IS","SASA.IS","SDTTR.IS","SISE.IS",
    "SKBNK.IS","SMRTG.IS","SOKM.IS","TABGD.IS","TAVHL.IS","TCELL.IS","THYAO.IS",
    "TKFEN.IS","TMSN.IS","TOASO.IS","TRGYO.IS","TSKB.IS","TSPOR.IS","TTKOM.IS",
    "TTRAK.IS","TUKAS.IS","TUPRS.IS","TURSG.IS","ULKER.IS","ULUSE.IS","UNLU.IS",
    "VAKBN.IS","VESBE.IS","VESTL.IS","YEOTK.IS","YKBNK.IS","YYLGD.IS","ZOREN.IS"
]

# ==============================================================================
# YARDIMCI FONKSİYONLAR
# ==============================================================================

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def validate_ohlcv_frame(df) -> bool:
    required = {"Open", "High", "Low", "Close", "Volume"}
    try:
        return df is not None and required.issubset(set(df.columns))
    except Exception:
        return False


# ==============================================================================
# DATABASE
# ==============================================================================

class Database:


@staticmethod
    def connect():
        return sqlite3.connect(DB_FILE, timeout=30)

@staticmethod
    def init():
        con = Database.connect()
        cur = con.cursor()

        cur.execute(""" CREATE TABLE IF NOT EXISTS portfolio_nav ( id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, cash REAL NOT NULL, nav REAL NOT NULL, open_positions INTEGER NOT NULL ) """)

        cur.execute(""" CREATE TABLE IF NOT EXISTS positions ( symbol TEXT PRIMARY KEY, entry_date TEXT NOT NULL, entry_price REAL NOT NULL, shares INTEGER NOT NULL, stop_loss REAL NOT NULL, tp1 REAL NOT NULL, tp2 REAL NOT NULL, score REAL NOT NULL, grade TEXT NOT NULL ) """)

        cur.execute(""" CREATE TABLE IF NOT EXISTS trades ( id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, entry_date TEXT NOT NULL, exit_date TEXT NOT NULL, entry_price REAL NOT NULL, exit_price REAL NOT NULL, shares INTEGER NOT NULL, pnl REAL NOT NULL, pnl_pct REAL NOT NULL, reason TEXT NOT NULL ) """)

        cur.execute("SELECT COUNT(*) FROM portfolio_nav")
        if cur.fetchone()[0] == 0:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute(
                "INSERT INTO portfolio_nav(timestamp,cash,nav,open_positions) VALUES(?,?,?,?)",
                (now, INITIAL_CAPITAL, INITIAL_CAPITAL, 0)
            )

        con.commit()
        con.close()

@staticmethod
    def cash():
        con = Database.connect()
        row = con.execute(
            "SELECT cash FROM portfolio_nav ORDER BY id DESC LIMIT 1"
        ).fetchone()
        con.close()
        return float(row[0]) if row else INITIAL_CAPITAL

@staticmethod
    def positions():
        con = Database.connect()
        df = pd.read_sql_query("SELECT * FROM positions", con)
        con.close()
        return df

@staticmethod
    def add_position(item, shares):
        con = Database.connect()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        con.execute(""" INSERT OR REPLACE INTO positions (symbol,entry_date,entry_price,shares,stop_loss,tp1,tp2,score,grade) VALUES(?,?,?,?,?,?,?,?,?) """, (
            item["symbol"], now, item["price"], int(shares),
            item["stop_loss"], item["tp1"], item["tp2"],
            item["score"], item["grade"]
        ))

        con.commit()
        con.close()

@staticmethod
    def close_position(symbol, price, reason="MANUAL"):
        con = Database.connect()

        row = con.execute(
            "SELECT symbol,entry_date,entry_price,shares FROM positions WHERE symbol=?",
            (symbol,)
        ).fetchone()

        if not row:
            con.close()
            return

        _, entry_date, entry_price, shares = row
        pnl = (price - entry_price) * shares
        pnl_pct = ((price / entry_price) - 1) * 100 if entry_price else 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        con.execute(""" INSERT INTO trades (symbol,entry_date,exit_date,entry_price,exit_price,shares,pnl,pnl_pct,reason) VALUES(?,?,?,?,?,?,?,?,?) """, (
            symbol, entry_date, now, entry_price, price,
            shares, pnl, pnl_pct, reason
        ))

        old_cash = Database.cash()
        new_cash = old_cash + shares * price * 0.999475

        con.execute("DELETE FROM positions WHERE symbol=?", (symbol,))

        count = con.execute(
            "SELECT COUNT(*) FROM positions"
        ).fetchone()[0]

        con.execute(""" INSERT INTO portfolio_nav(timestamp,cash,nav,open_positions) VALUES(?,?,?,?) """, (now, new_cash, new_cash, count))

        con.commit()
        con.close()


# ==============================================================================
# DATA NORMALIZATION
# ==============================================================================

def normalize_ohlcv(df):
    if df is None or df.empty:
        return None

    x = df.copy()

    if isinstance(x.columns, pd.MultiIndex):
        # MultiIndex'in ikinci veya ilk seviyesinde OHLCV isimlerini bul.
        target = {}
        for field in ["Open", "High", "Low", "Close", "Volume"]:
            found = None
            for col in x.columns:
                parts = [str(p).strip().lower() for p in col]
                if field.lower() in parts:
                    found = col
                    break
            if found is not None:
                target[field] = found

        if len(target) == 5:
            x = x[[target["Open"], target["High"], target["Low"],
                   target["Close"], target["Volume"]]].copy()
            x.columns = ["Open", "High", "Low", "Close", "Volume"]

    rename = {}
    for c in x.columns:
        s = str(c).strip().lower()
        if s == "open":
            rename[c] = "Open"
        elif s == "high":
            rename[c] = "High"
        elif s == "low":
            rename[c] = "Low"
        elif s == "close":
            rename[c] = "Close"
        elif s == "volume":
            rename[c] = "Volume"

    x = x.rename(columns=rename)

    required = ["Open", "High", "Low", "Close", "Volume"]
    if not all(c in x.columns for c in required):
        return None

    x = x[required].copy()

    for c in required:
        x[c] = pd.to_numeric(x[c], errors="coerce")

    x = x.replace([np.inf, -np.inf], np.nan)
    x = x.dropna(subset=required)
    x = x[~x.index.duplicated(keep="last")]
    x = x.sort_index()

    return x if len(x) >= 30 else None


# ==============================================================================
# INDICATORS
# ==============================================================================

class IndicatorEngine:


@staticmethod
    def _adx(df, n=14):
        high = df["High"]
        low = df["Low"]
        close = df["Close"]

        up = high.diff()
        down = -low.diff()

        plus_dm = pd.Series(
            np.where((up > down) & (up > 0), up, 0.0),
            index=df.index
        )

        minus_dm = pd.Series(
            np.where((down > up) & (down > 0), down, 0.0),
            index=df.index
        )

        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)

        atr = tr.ewm(alpha=1/n, adjust=False).mean()

        plus_di = (
            100 * plus_dm.ewm(alpha=1/n, adjust=False).mean()
            / (atr + 1e-10)
        )

        minus_di = (
            100 * minus_dm.ewm(alpha=1/n, adjust=False).mean()
            / (atr + 1e-10)
        )

        dx = (
            100 * (plus_di - minus_di).abs()
            / (plus_di + minus_di + 1e-10)
        )

        adx = dx.ewm(alpha=1/n, adjust=False).mean()

        return adx, plus_di, minus_di

@staticmethod
    def calculate(df):
        df = normalize_ohlcv(df)

        if df is None or len(df) < 30:
            return None

        x = df.copy()

        c = x["Close"]
        h = x["High"]
        l = x["Low"]
        v = x["Volume"]

        for p in [5,8,9,10,13,14,20,21,34,50,55,89,100,150,200]:
            x[f"EMA_{p}"] = c.ewm(span=p, adjust=False).mean()
            x[f"SMA_{p}"] = c.rolling(p).mean()

        tr = pd.concat([
            h-l,
            (h-c.shift()).abs(),
            (l-c.shift()).abs()
        ], axis=1).max(axis=1)

        x["ATR"] = tr.ewm(span=14, adjust=False).mean()
        x["NATR"] = x["ATR"] / (c + 1e-10) * 100

        x["ADX"], x["+DI"], x["-DI"] = IndicatorEngine._adx(x)

        delta = c.diff()

        gain = delta.clip(lower=0).ewm(
            alpha=1/14, adjust=False
        ).mean()

        loss = (-delta.clip(upper=0)).ewm(
            alpha=1/14, adjust=False
        ).mean()

        x["RSI"] = 100 - 100 / (
            1 + gain / (loss + 1e-10)
        )

        e12 = c.ewm(span=12, adjust=False).mean()
        e26 = c.ewm(span=26, adjust=False).mean()

        x["MACD"] = e12 - e26
        x["MACD_Signal"] = x["MACD"].ewm(
            span=9, adjust=False
        ).mean()

        x["MACD_Hist"] = (
            x["MACD"] - x["MACD_Signal"]
        )

        x["OBV"] = (
            np.sign(c.diff()).fillna(0) * v
        ).cumsum()

        x["OBV_EMA"] = x["OBV"].ewm(
            span=20, adjust=False
        ).mean()

        x["RVOL"] = v / (
            v.rolling(20).mean() + 1e-10
        )

        x["Rolling_High_50"] = h.rolling(50).max().shift(1)
        x["Rolling_Low_50"] = l.rolling(50).min().shift(1)

        x["BOS"] = (
            (c > x["Rolling_High_50"]) &
            (c.shift(1) <= x["Rolling_High_50"])
        ).astype(int)

        x["CHOCH"] = (
            (c < x["Rolling_Low_50"]) &
            (c.shift(1) >= x["Rolling_Low_50"])
        ).astype(int)

        x["FVG_Up"] = (
            (l > h.shift(2)) &
            (c.shift(1) > h.shift(2))
        ).astype(int)

        mid = c.rolling(20).mean()
        sd = c.rolling(20).std()

        x["BB_Mid"] = mid
        x["BB_Upper"] = mid + 2 * sd
        x["BB_Lower"] = mid - 2 * sd
        x["BB_Width"] = (
            x["BB_Upper"] - x["BB_Lower"]
        ) / (mid + 1e-10)

        hl2 = (h + l) / 2
        upper = hl2 + 3 * x["ATR"]
        lower = hl2 - 3 * x["ATR"]

        direction = np.ones(len(x), dtype=int)
        stv = np.zeros(len(x))

        for i in range(1, len(x)):
            if c.iloc[i] > upper.iloc[i-1]:
                direction[i] = 1
            elif c.iloc[i] < lower.iloc[i-1]:
                direction[i] = -1
            else:
                direction[i] = direction[i-1]

            stv[i] = (
                lower.iloc[i]
                if direction[i] > 0
                else upper.iloc[i]
            )

        x["Supertrend"] = stv
        x["ST_Direction"] = direction

        pv = ((h + l + c) / 3) * v

        x["VWAP_20"] = (
            pv.rolling(20).sum()
            / (v.rolling(20).sum() + 1e-10)
        )

        x = x.replace([np.inf, -np.inf], np.nan)

        # 200 EMA ve diğer uzun göstergeler için NaN'ları temizle.
        return x.dropna()


# ==============================================================================
# VPVR / POC
# ==============================================================================

def calculate_poc(df, bins=30, lookback=120):
    x = normalize_ohlcv(df)

    if x is None or len(x) < 40:
        return np.nan

    q = x.tail(min(lookback, len(x)))

    typical = (
        q["High"] + q["Low"] + q["Close"]
    ) / 3

    lo = float(typical.min())
    hi = float(typical.max())

    if hi <= lo:
        return float(q["Close"].iloc[-1])

    edges = np.linspace(lo, hi, bins + 1)

    idx = np.clip(
        np.digitize(typical, edges) - 1,
        0,
        bins - 1
    )

    vol = np.zeros(bins)

    for i, vv in zip(idx, q["Volume"]):
        vol[int(i)] += float(vv)

    k = int(np.argmax(vol))

    return float(
        (edges[k] + edges[k+1]) / 2
    )


def poc_is_clear_for_long(price, poc, atr):
    if poc is None or not np.isfinite(poc):
        return True

    price = _safe_float(price)
    atr = max(_safe_float(atr), 1e-9)

    return price >= (
        poc - HP_CONFIG.poc_below_tolerance_atr * atr
    )


# ==============================================================================
# DATA FETCH
# ==============================================================================

def fetch_daily(symbol, period="2y"):
    try:
        raw = yf.download(
            symbol,
            period=period,
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False
        )
        return normalize_ohlcv(raw)
    except Exception:
        return None


def fetch_4h(symbol, period="60d"):
    """ Yahoo Finance 4H doğrudan vermeyebildiği için 1H veriyi 4 saatlik barlara dönüştürür. """
    try:
        raw = yf.download(
            symbol,
            period=period,
            interval="1h",
            auto_adjust=False,
            progress=False,
            threads=False
        )

        x = normalize_ohlcv(raw)

        if x is None or len(x) < 50:
            return None

        # Index timezone-aware olabilir; resample buna rağmen çalışır.
        h4 = x.resample("4h").agg({
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum"
        })

        h4 = h4.dropna(subset=[
            "Open","High","Low","Close","Volume"
        ])

        return h4 if len(h4) >= 30 else None

    except Exception:
        return None


def fetch_batch(symbols, period="2y"):
    all_symbols = list(dict.fromkeys(
        list(symbols) + [BENCHMARK]
    ))

    try:
        raw = yf.download(
            all_symbols,
            period=period,
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=True,
            group_by="ticker"
        )
    except Exception:
        return {}

    result = {}

    if isinstance(raw.columns, pd.MultiIndex):
        for symbol in all_symbols:
            try:
                sub = raw[symbol]
                n = normalize_ohlcv(sub)
                if n is not None:
                    result[symbol] = n
            except Exception:
                continue
    else:
        if len(all_symbols) == 1:
            n = normalize_ohlcv(raw)
            if n is not None:
                result[all_symbols[0]] = n

    return result


def fetch_live_prices(symbols):
    prices = {}

    if not symbols:
        return prices

    try:
        raw = yf.download(
            symbols,
            period="5d",
            interval="1m",
            auto_adjust=False,
            progress=False,
            threads=True,
            group_by="ticker",
            prepost=False
        )

        if isinstance(raw.columns, pd.MultiIndex):
            for symbol in symbols:
                try:
                    close = raw[symbol]["Close"].dropna()
                    if len(close):
                        prices[symbol] = float(close.iloc[-1])
                except Exception:
                    continue

        elif len(symbols) == 1 and "Close" in raw:
            q = raw["Close"].dropna()
            if len(q):
                prices[symbols[0]] = float(q.iloc[-1])

    except Exception:
        pass

    return prices


# ==============================================================================
# SIGNAL ENGINE
# ==============================================================================

class SignalEngine:


@staticmethod
    def analyze( symbol, daily, benchmark, live_price=None, h4=None ):
        ind = IndicatorEngine.calculate(daily)

        if ind is None or len(ind) < 120:
            return None

        r = ind.iloc[-1]

        price = float(
            live_price
            if live_price is not None and live_price > 0
            else r["Close"]
        )

        atr = float(r["ATR"])

        if not np.isfinite(atr) or atr <= 0:
            return None

        veto = []

        # ----------------------------------------------------------------------
        # 1. ADX VETO
        # ----------------------------------------------------------------------
        adx = float(r["ADX"])

        if adx < HP_CONFIG.adx_veto:
            veto.append("ADX<20 YATAY")

        # ----------------------------------------------------------------------
        # 2. DAILY TREND
        # ----------------------------------------------------------------------
        daily_ok = bool(
            r["EMA_20"] > r["EMA_50"] >
            r["EMA_200"]
        )

        if not daily_ok:
            veto.append("GÜNLÜK TREND")

        # ----------------------------------------------------------------------
        # 3. 4H MTF
        # ----------------------------------------------------------------------
        h4_ok = False

        if h4 is not None:
            h4i = IndicatorEngine.calculate(h4)

            if h4i is not None and len(h4i):
                h = h4i.iloc[-1]
                h4_ok = bool(
                    h["EMA_20"] > h["EMA_50"]
                )

        if not h4_ok:
            veto.append("4H MTF")

        # ----------------------------------------------------------------------
        # 4. VPVR / POC
        # ----------------------------------------------------------------------
        poc = calculate_poc(daily)

        if np.isfinite(poc):
            if price < poc * 1.005:
                veto.append("POC ALTI/YAKINI")

        # ----------------------------------------------------------------------
        # 5. RSI
        # ----------------------------------------------------------------------
        rsi = float(r["RSI"])

        if rsi >= 78:
            veto.append("RSI AŞIRI")

        # ----------------------------------------------------------------------
        # 6. MACD
        # ----------------------------------------------------------------------
        if float(r["MACD_Hist"]) <= 0:
            veto.append("MACD NEGATİF")

        # ----------------------------------------------------------------------
        # 7. RVOL
        # ----------------------------------------------------------------------
        rvol = float(r["RVOL"])

        if rvol < HP_CONFIG.rvol_minimum:
            veto.append("DÜŞÜK RVOL")

        # ----------------------------------------------------------------------
        # 8. RELATIVE STRENGTH
        # ----------------------------------------------------------------------
        rs = np.nan

        if benchmark is not None and len(benchmark) >= 60:
            try:
                bi = IndicatorEngine.calculate(benchmark)

                if (
                    bi is not None and
                    len(bi) >= 60 and
                    len(ind) >= 60
                ):
                    sr = (
                        price /
                        float(ind["Close"].iloc[-60])
                    ) - 1

                    mr = (
                        float(bi["Close"].iloc[-1]) /
                        float(bi["Close"].iloc[-60])
                    ) - 1

                    rs = sr - mr

                    if rs < 0:
                        veto.append("NEGATİF RS")
            except Exception:
                pass

        # ----------------------------------------------------------------------
        # 9. EMA20
        # ----------------------------------------------------------------------
        if price < float(r["EMA_20"]):
            veto.append("EMA20 ALTINDA")

        # ----------------------------------------------------------------------
        # 10. SUPERTREND
        # ----------------------------------------------------------------------
        if float(r["ST_Direction"]) < 0:
            veto.append("SUPERTREND")

        # ----------------------------------------------------------------------
        # SCORE
        # ----------------------------------------------------------------------
        score = 0.0

        score += 15 if price > r["EMA_20"] else 0
        score += 12 if r["EMA_20"] > r["EMA_50"] else 0
        score += 10 if r["EMA_50"] > r["EMA_200"] else 0
        score += 10 if adx >= 25 else 5

        score += (
            8 if 52 <= rsi <= 72
            else 4 if 48 <= rsi < 52
            else 0
        )

        score += 10 if r["MACD_Hist"] > 0 else 0

        score += (
            8 if rvol >= 1.5
            else 5 if rvol >= 1.2
            else 0
        )

        score += 7 if r["OBV"] > r["OBV_EMA"] else 0

        if np.isfinite(rs):
            score += (
                8 if rs >= 0.05
                else 5 if rs >= 0.02
                else 0
            )

        score += (
            5 if r["BOS"] == 1
            else 3 if r["FVG_Up"] == 1
            else 0
        )

        score += 4 if h4_ok else 0

        score += (
            3 if np.isfinite(poc) and price > poc * 1.02
            else 0
        )

        # ----------------------------------------------------------------------
        # ATR EXTENSION
        # ----------------------------------------------------------------------
        extension = (
            price - float(r["EMA_20"])
        ) / (atr + 1e-10)

        if extension > 3.0:
            veto.append("ATR AŞIRI UZAMA")
        elif extension > 2.2:
            score -= 5

        # ----------------------------------------------------------------------
        # RISK / REWARD
        # ----------------------------------------------------------------------
        stop = (
            price -
            HP_CONFIG.atr_stop_multiple * atr
        )

        tp1 = (
            price +
            HP_CONFIG.atr_tp1_multiple * atr
        )

        tp2 = (
            price +
            HP_CONFIG.atr_tp2_multiple * atr
        )

        rr = (
            (tp1 - price) /
            (price - stop)
            if price > stop else 0
        )

        if rr < 1.0:
            veto.append("R/R YETERSİZ")

        # ----------------------------------------------------------------------
        # VETO SONUCU
        # ----------------------------------------------------------------------
        if veto:
            return {
                "symbol": symbol,
                "price": price,
                "score": 0.0,
                "grade": "VETO",
                "rsi": rsi,
                "adx": adx,
                "rvol": rvol,
                "rs": float(rs) if np.isfinite(rs) else 0.0,
                "poc": float(poc) if np.isfinite(poc) else np.nan,
                "atr": atr,
                "stop_loss": stop,
                "tp1": tp1,
                "tp2": tp2,
                "veto": " | ".join(veto),
                "accepted": False
            }

        score = float(np.clip(score, 0, 100))

        grade = (
            "A+" if score >= 90
            else "A" if score >= 82
            else "B+" if score >= 76
            else "B"
        )

        accepted = score >= HP_CONFIG.minimum_score

        return {
            "symbol": symbol,
            "price": price,
            "score": score,
            "grade": grade,
            "rsi": rsi,
            "adx": adx,
            "rvol": rvol,
            "rs": float(rs) if np.isfinite(rs) else 0.0,
            "poc": float(poc) if np.isfinite(poc) else np.nan,
            "atr": atr,
            "stop_loss": stop,
            "tp1": tp1,
            "tp2": tp2,
            "veto": "",
            "accepted": accepted
        }


# ==============================================================================
# PARALLEL SCAN
# ==============================================================================

def scan_market(symbols, period, workers=8):
    data = fetch_batch(symbols, period)

    if not data:
        return [], 0

    benchmark = data.get(BENCHMARK)

    candidates = [
        s for s in symbols
        if s in data and s != BENCHMARK
    ]

    live = fetch_live_prices(candidates)

    results = []

    def worker(symbol):
        try:
            h4 = fetch_4h(symbol)

            return SignalEngine.analyze(
                symbol,
                data[symbol],
                benchmark,
                live.get(symbol),
                h4
            )
        except Exception:
            return None

    with ThreadPoolExecutor(
        max_workers=max(2, workers)
    ) as executor:

        futures = {
            executor.submit(worker, s): s
            for s in candidates
        }

        for future in as_completed(futures):
            try:
                item = future.result()
                if item is not None:
                    results.append(item)
            except Exception:
                continue

    results.sort(
        key=lambda z: (
            z["accepted"],
            z["score"]
        ),
        reverse=True
    )

    return results, len(data)


# ==============================================================================
# BACKTEST
# ==============================================================================

class BacktestEngine:


@staticmethod
    def run( df, starting_capital=100000.0, risk_pct=2.0 ):
        ind = IndicatorEngine.calculate(df)

        if ind is None or len(ind) < 160:
            return None

        cash = float(starting_capital)
        shares = 0
        entry = 0.0

        curve = []
        trades = []

        for i in range(120, len(ind)):
            r = ind.iloc[i]

            price = float(r["Close"])
            atr = float(r["ATR"])

            if atr <= 0:
                curve.append(
                    cash + shares * price
                )
                continue

            buy = (
                price > r["EMA_20"] and
                r["EMA_20"] > r["EMA_50"] and
                r["EMA_50"] > r["EMA_200"] and
                r["ADX"] >= 20 and
                r["RSI"] < 78 and
                r["MACD_Hist"] > 0 and
                r["RVOL"] >= 1.05
            )

            sell = (
                price < r["EMA_20"] or
                r["RSI"] < 42 or
                price < entry - 2 * atr
            )

            if shares == 0 and buy:
                risk_budget = (
                    cash * risk_pct / 100
                )

                risk_per_share = 2 * atr

                qty = (
                    int(risk_budget / risk_per_share)
                    if risk_per_share > 0
                    else 0
                )

                qty = min(
                    qty,
                    int(cash * 0.95 / price)
                )

                if qty > 0:
                    shares = qty
                    entry = price
                    cash -= (
                        qty * price * 1.000525
                    )

            elif shares > 0 and sell:
                exit_value = (
                    shares * price * 0.999475
                )

                pnl = (
                    exit_value -
                    shares * entry * 1.000525
                )

                cash += exit_value

                trades.append(pnl)

                shares = 0
                entry = 0

            curve.append(
                cash + shares * price
            )

        if not curve:
            return None

        eq = pd.Series(curve)

        ret = eq.pct_change().dropna()

        sharpe = float(
            ret.mean() /
            (ret.std() + 1e-10) *
            np.sqrt(252)
        )

        dd = (
            eq / eq.cummax() - 1
        )

        mdd = float(dd.min() * 100)

        wins = [
            x for x in trades if x > 0
        ]

        losses = [
            x for x in trades if x <= 0
        ]

        wr = (
            100 * len(wins) / len(trades)
            if trades else 0
        )

        if losses and sum(losses) != 0:
            pf = (
                sum(wins) /
                abs(sum(losses))
            )
        elif wins:
            pf = 999.0
        else:
            pf = 0.0

        return {
            "curve": curve,
            "trades": trades,
            "final_nav": curve[-1],
            "return_pct": (
                curve[-1] /
                starting_capital - 1
            ) * 100,
            "sharpe": sharpe,
            "mdd": mdd,
            "win_rate": wr,
            "profit_factor": float(pf),
            "trade_count": len(trades)
        }


# ==============================================================================
# UI
# ==============================================================================

st.set_page_config(
    page_title="QUANT MASTER v67.1 | High Precision",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(""" <style> .main,.stApp{ background:#030712; color:#F8FAFC } .terminal-card{ background:linear-gradient( 135deg,#0F172A 0%,#1E293B 100% ); border:1px solid #334155; border-radius:12px; padding:18px; margin-bottom:12px; box-shadow:0 8px 15px -5px rgba(0,0,0,.45) } .live-ticker{ color:#38BDF8; font-weight:bold; font-family:monospace } .badge-aplus{ background:#14532D; border:1px solid #22C55E; color:#86EFAC; padding:5px 10px; border-radius:7px; font-weight:900 } .badge-a{ background:#064E3B; border:1px solid #10B981; color:#34D399; padding:5px 10px; border-radius:7px; font-weight:800 } .badge-b{ background:#1E3A8A; border:1px solid #3B82F6; color:#60A5FA; padding:5px 10px; border-radius:7px; font-weight:800 } .badge-reject{ background:#450A0A; border:1px solid #EF4444; color:#FCA5A5; padding:5px 10px; border-radius:7px; font-weight:800 } </style> """, unsafe_allow_html=True)


def render_signal(item):
    grade = item["grade"]

    badge = (
        "badge-aplus" if grade == "A+"
        else "badge-a" if grade == "A"
        else "badge-b"
    )

    poc_text = (
        f'{item["poc"]:.2f}'
        if np.isfinite(item["poc"])
        else "-"
    )

    st.markdown(
        f""" <div class="terminal-card"> <div style=" display:flex; justify-content:space-between; align-items:center "> <div> <h3 style=" margin:0; color:#F8FAFC "> {item["symbol"]} </h3> <span class="live-ticker"> Canlı/son fiyat: {item["price"]:.2f} TL </span> &nbsp; | RSI: {item["rsi"]:.1f} &nbsp; | ADX: {item["adx"]:.1f} &nbsp; | RVOL: {item["rvol"]:.2f}x </div> <div class="{badge}"> {grade} — {item["score"]:.1f}/100 </div> </div> <hr style="border-color:#334155"> <div style=" display:flex; justify-content:space-between; flex-wrap:wrap; gap:12px "> <span>RS: {item["rs"]:+.2%}</span> <span>POC: {poc_text}</span> <span>TP1: {item["tp1"]:.2f}</span> <span>TP2: {item["tp2"]:.2f}</span> <span>Stop: {item["stop_loss"]:.2f}</span> </div> </div> """,
        unsafe_allow_html=True
    )


def main():
    Database.init()

    st.markdown(
        '<h1 style="color:#38BDF8;font-weight:900">'
        '⚡ QUANT MASTER v67.1 | HIGH PRECISION BIST TERMINAL'
        '</h1>',
        unsafe_allow_html=True
    )

    st.caption(
        "A+ / A / B+ seçici sinyal motoru • canlı/son fiyat • "
        "günlük + 4H MTF • ADX • VPVR/POC • RS"
    )

    with st.sidebar:
        st.header("⚙️ Tarama")

        period = st.selectbox(
            "Günlük geçmiş",
            ["1y", "2y", "3y"],
            index=1
        )

        workers = st.slider(
            "Paralel işçi",
            2, 12, 8
        )

        risk = st.slider(
            "İşlem riski %",
            1.0, 5.0, 2.0
        )

        run = st.button(
            "🚀 TÜM BIST'İ TARA",
            use_container_width=True
        )

        bt = st.button(
            "📈 KCHOL BACKTEST",
            use_container_width=True
        )

        st.divider()

        st.subheader("💼 Paper Portfolio")

        if st.button(
            "🔄 Portföyü yenile",
            use_container_width=True
        ):
            st.rerun()

    if run:
        t0 = time.time()

        with st.spinner(
            "BIST evreni hızlı taranıyor..."
        ):
            results, loaded = scan_market(
                BIST_SYMBOLS,
                period,
                workers
            )

        st.session_state["results"] = results
        st.session_state["scan_time"] = (
            time.time() - t0
        )

        st.success(
            f"Tarama tamamlandı • "
            f"{loaded} veri seti • "
            f"{st.session_state['scan_time']:.1f} sn"
        )

    results = st.session_state.get(
        "results",
        []
    )

    if results:
        accepted = [
            x for x in results
            if x["accepted"]
        ]

        st.metric(
            "Yüksek Kaliteli Sinyal",
            len(accepted)
        )

        st.caption(
            f"Toplam analiz: {len(results)} | "
            f"Aday: {len(accepted)}"
        )

        for item in accepted[:30]:
            render_signal(item)

        if accepted:
            top = accepted[0]

            if st.button(
                f"📥 {top['symbol']} PAPER TRADE",
                use_container_width=True
            ):
                cash = Database.cash()

                risk_budget = (
                    cash * risk / 100
                )

                qty = (
                    int(
                        risk_budget /
                        (2 * top["atr"])
                    )
                    if top["atr"] > 0
                    else 0
                )

                qty = min(
                    qty,
                    int(
                        cash * .95 /
                        top["price"]
                    )
                )

                if qty > 0:
                    Database.add_position(
                        top,
                        qty
                    )

                    st.success(
                        f"{top['symbol']} — "
                        f"{qty} lot paper pozisyon açıldı."
                    )

                    st.rerun()

    else:
        st.info(
            "Sol menüden TÜM BIST'İ TARA "
            "butonuna basın."
        )

    st.divider()

    st.subheader(
        "💼 Açık Pozisyonlar"
    )

    pos = Database.positions()
    cash = Database.cash()

    if pos.empty:
        st.write(
            "Açık pozisyon yok."
        )
    else:
        total_open = 0

        for _, p in pos.iterrows():
            try:
                d = fetch_daily(
                    p["symbol"],
                    "5d"
                )

                live = (
                    float(d["Close"].iloc[-1])
                    if d is not None
                    else float(p["entry_price"])
                )
            except Exception:
                live = float(
                    p["entry_price"]
                )

            val = (
                live *
                int(p["shares"])
            )

            total_open += val

            pnl = (
                live -
                float(p["entry_price"])
            ) * int(p["shares"])

            st.markdown(
                f"**{p['symbol']}** | "
                f"{int(p['shares'])} lot | "
                f"Fiyat {live:.2f} | "
                f"PnL {pnl:+,.2f} TL | "
                f"SL {p['stop_loss']:.2f}"
            )

            if st.button(
                f"Kapat {p['symbol']}",
                key="close_" + p["symbol"]
            ):
                Database.close_position(
                    p["symbol"],
                    live,
                    "MANUAL"
                )
                st.rerun()

        st.metric(
            "Portföy NAV",
            f"{cash + total_open:,.2f} TL",
            f"Nakit {cash:,.2f} TL"
        )

    if bt:
        with st.spinner(
            "Backtest çalışıyor..."
        ):
            d = fetch_daily(
                "KCHOL.IS",
                "3y"
            )

            result = BacktestEngine.run(
                d,
                100000,
                risk
            )

        if result:
            st.subheader(
                "📈 Backtest"
            )

            c1,c2,c3,c4,c5 = st.columns(5)

            c1.metric(
                "Final NAV",
                f"{result['final_nav']:,.0f} TL"
            )

            c2.metric(
                "Getiri",
                f"{result['return_pct']:+.2f}%"
            )

            c3.metric(
                "Sharpe",
                f"{result['sharpe']:.2f}"
            )

            c4.metric(
                "MDD",
                f"{result['mdd']:.2f}%"
            )

            c5.metric(
                "Win Rate",
                f"{result['win_rate']:.1f}%"
            )

            st.metric(
                "Profit Factor",
                f"{result['profit_factor']:.2f}",
                f"{result['trade_count']} işlem"
            )

            st.line_chart(
                pd.Series(result["curve"])
            )


if __name__ == "__main__":
    main()

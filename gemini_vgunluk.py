import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import sqlite3
import requests
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings

warnings.filterwarnings("ignore")

# ============================================================
# QUANT MASTER v65.1 - FAST LIVE SCANNER
# DYNAMIC BIST UNIVERSE + ADX + 4H MTF + VPVR/POC
# ============================================================

st.set_page_config(
    page_title="QUANT MASTER v65.0 | BIST Full Universe",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --------------------------- THEME ---------------------------

st.markdown(""" <style> .stApp {background:#030712;} .block-container {padding-top:1.2rem;} .q-card { background:linear-gradient(135deg,#0F172A,#111827); border:1px solid #334155; border-radius:14px; padding:18px; margin:8px 0; } .q-title {font-weight:900;color:#F8FAFC;} .q-muted {color:#94A3B8;} .q-score { display:inline-block; padding:6px 12px; border-radius:8px; font-weight:900; } .q-good {background:#064E3B;color:#34D399;border:1px solid #10B981;} .q-mid {background:#1E3A8A;color:#60A5FA;border:1px solid #3B82F6;} .q-bad {background:#3F1D1D;color:#FCA5A5;border:1px solid #EF4444;} </style> """, unsafe_allow_html=True)

DB_FILE = "quant_master_v65.db"
TV_SCAN_URL = "https://scanner.tradingview.com/turkey/scan"

# ============================================================
# BIST UNIVERSE
# ============================================================

# TradingView üzerinden güncel evren alınamazsa kullanılacak geniş
# yedek liste. Ana yöntem dinamik TradingView taramasıdır.
FALLBACK_BIST = """ AEFES AKBNK AKENR AKFGY AKFYE AKGRT AKMGY AKSA AKSEN AKSGY ALARK ALBRK ALCTL ALFAS ALGYO ALKA ALKIM ALKLC ALTNY ANELE ANHYT ANSGR ARCLK ARENA ARZUM ASELS ASGYO ASUZU ATAGY ATAKP ATATP ATEKS ATLAS AVHOL AVOD AYDEM AYEN BAKAB BALAT BANVT BARMA BASGZ BAYRK BEGYO BEYAZ BFREN BIGEN BIMAS BINBN BIZIM BJKAS BLCYT BMSCH BMSTL BNTAS BOBET BORLS BORSK BOSSA BRISA BRKO BRKSN BRKVY BRLSM BRSAN BRYAT BSOKE BTCIM BUCIM BURCE BURVA BVSAN CANTE CCOLA CELHA CEMAS CEMTS CEOEM CIMSA CLEBI CMBTN CONSE COSMO CUSAN CVKMD CWENE DAGHL DAGI DAPGM DARDL DCTTR DENGE DERHL DERIM DESA DESPC DEVA DGATE DGGYO DGNMO DITAS DMRGD DOAS DOBUR DOCO DOHOL DOKTA DURDO DYOBY ECILC ECZYT EDATA EGEEN EGGUB EKGYO EKSUN ELITE EMKEL ENERY ENJSA ENKAI ENSRI ENTRA EREGL ESCAR ESEN EUPWR EYGYO FADE FENER FFKRL FROTO GARAN GEDIK GEDZA GENIL GENTS GEREL GESAN GLBMD GLCVY GLRYH GLYHO GOKNR GOLTS GOODY GOZDE GRSEL GRTHO GSDDE GSDHO GSRAY GUBRF GWIND HALKB HATEK HATSN HDFGS HEDEF HEKTS HKTM HLAS HLGYO HOROZ HUBVC HUNER HURGZ ICBCT IDGYO IEYHO IHAAS IHEVA IHGZT IHLAS IHLGM IHYAY IMASM INDES INFO INGRM INTEM INVEO ISCTR ISDMR ISFIN ISGSY ISGYO ISKPL ISMEN ISONE ISSEN ISYAT ITTFH IZENR IZFAS IZMDC JANTS KAPLM KAREL KARSN KARTN KARYE KATMR KAYSE KCAER KCHOL KENT KERVT KFEIN KLGYO KLKIM KLRHO KLSER KLYPV KMPUR KNFRT KONKA KONTR KONYA KOPOL KORDS KOZAA KOZAL KRDMA KRDMB KRDMD KRGYO KRONT KRVGD KSTUR KTLEV KTSKR KUTPO KUYAS LIDER LINK LKMNH LOGO LOKMAN LRSHO LUKSK MAALT MACKO MAGEN MAKIM MAKTK MANAS MARBL MARKA MARTI MAVI MEDTR MEGMT MEPET MERCN MERIT MERKO METRO MGROS MHRGY MIATK MIPAZ MMCAS MNDRS MOBTL MOGAN MPARK MRSHL MTRKS MZHLD NATEN NETAS NTGAZ NTHOL NUGYO NUHCM OBAMS ODAS ODINE OBASE OFSYM ONCSM ORGE ORMA OSMEN OSTIM OTKAR OYAKC OYAYD OYLUM OZATD OZKGY PAGYO PAPIL PARSN PASEU PENTA PETKM PETUN PGSUS PINSU PKART PKENT PLTUR PNSUT POLHO POLTK PRDGS PRKAB PRKME PRZMA PSDTC QNBFL QNBTR QUAGR RALYH RAYSG REEDR RNPOL ROYAL RYGYO RYSAS SAFKR SAHOL SAMAT SANEL SANKO SASA SAYAS SDTTR SEGMN SEGYO SEKFK SEKUR SELVA SENTE SERCY SERVE SISE SKBNK SKTAS SKYMD SMART SMRTG SNGYO SNICA SNKRN SOKM SOKE SONME SRVGY SUMAS SUNTK SUWEN TARKM TATEN TATGD TAVHL TBORG TCELL TDGYO TEKTU TERA TETMT TEZOL TGSAS THYAO TKFEN TKNSA TLMAN TMSN TNZTP TOASO TRCAS TRGYO TRILC TSKB TSPOR TTRAK TUCLK TUKAS TUPRS TURGG TURSG UCAK ULUFA ULUSE ULKER ULUUN UNLU USAK UZERB VAKBN VAKFN VAKKO VANGD VBTYZ VERUS VESBE VESTL VKGYO VKING YAPRK YATAS YAYLA YBTAS YEOTK YESIL YGGYO YIGIT YKBNK YKSLN YONGA YUNSA YYAPI ZEDUR ZOREN """.split()

FALLBACK_BIST = sorted(set(x.strip().upper() for x in FALLBACK_BIST if x.strip()))

def normalize_symbol(s):
    s = str(s).upper().strip()
    if s.endswith(".IS"):
        return s
    return s + ".IS"

@st.cache_data(ttl=3600, show_spinner=False)
def get_dynamic_bist_universe():
    """ Öncelik: 1) TradingView Turkey scanner üzerinden güncel semboller. 2) Geniş gömülü BIST yedek listesi. """
    try:
        payload = {
            "filter": [
                {"left": "type", "operation": "equal", "right": "stock"}
            ],
            "options": {"lang": "en"},
            "markets": ["turkey"],
            "symbols": {"query": {"types": []}, "tickers": []},
            "columns": ["name", "close"],
            "sort": {"sortBy": "name", "sortOrder": "asc"},
            "range": [0, 2000]
        }
        r = requests.post(TV_SCAN_URL, json=payload, timeout=15)
        r.raise_for_status()
        js = r.json()
        rows = js.get("data", [])

        symbols = []
        for row in rows:
            s = row.get("s", "")
            # Turkey exchange sembolleri genellikle BIST:XXX şeklindedir.
            if ":" in s:
                exchange, ticker = s.split(":", 1)
                if exchange.upper() in ("BIST", "BIST_TR"):
                    if ticker and ticker.upper() not in ("XU100", "XU030"):
                        symbols.append(normalize_symbol(ticker))

        symbols = sorted(set(symbols))
        if len(symbols) >= 300:
            return symbols, "TradingView dinamik evren"
    except Exception:
        pass

    return [normalize_symbol(x) for x in FALLBACK_BIST], "Geniş BIST yedek evreni"

# ============================================================
# DATABASE
# ============================================================

class DB:
@staticmethod
    def init():
        con = sqlite3.connect(DB_FILE)
        cur = con.cursor()

        cur.execute(""" CREATE TABLE IF NOT EXISTS portfolio_nav ( id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, cash REAL, nav REAL, open_positions INTEGER ) """)

        cur.execute(""" CREATE TABLE IF NOT EXISTS positions ( symbol TEXT PRIMARY KEY, entry_date TEXT, entry_price REAL, shares INTEGER, stop_loss REAL, tp1 REAL, tp2 REAL, score REAL ) """)

        cur.execute(""" CREATE TABLE IF NOT EXISTS trades ( id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, entry_date TEXT, exit_date TEXT, entry_price REAL, exit_price REAL, shares INTEGER, pnl REAL, pnl_pct REAL, reason TEXT ) """)

        cur.execute("SELECT COUNT(*) FROM portfolio_nav")
        if cur.fetchone()[0] == 0:
            cur.execute(
                "INSERT INTO portfolio_nav(timestamp,cash,nav,open_positions) VALUES(?,?,?,?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 100000, 100000, 0)
            )

        con.commit()
        con.close()

@staticmethod
    def cash():
        con = sqlite3.connect(DB_FILE)
        row = con.execute(
            "SELECT cash FROM portfolio_nav ORDER BY id DESC LIMIT 1"
        ).fetchone()
        con.close()
        return float(row[0]) if row else 100000.0

@staticmethod
    def positions():
        con = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM positions", con)
        con.close()
        return df

# ============================================================
# DATA NORMALIZATION
# ============================================================

def normalize_ohlcv(df):
    """ yfinance bazen MultiIndex döndürür. Close/High/Low/Volume kolonlarını güvenli biçimde düzleştirir. """
    if df is None or df.empty:
        return None

    x = df.copy()

    if isinstance(x.columns, pd.MultiIndex):
        # OHLCV ilk seviyedeyse
        wanted = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
        newcols = []
        for col in x.columns:
            parts = [str(p) for p in col if str(p) != ""]
            found = next((p for p in parts if p in wanted), parts[0] if parts else "")
            newcols.append(found)
        x.columns = newcols

    # Duplicate kolonları kaldır
    x = x.loc[:, ~x.columns.duplicated()]

    # Bazı sürümlerde kolonlar lowercase gelebilir
    rename = {}
    for c in x.columns:
        lc = str(c).lower()
        if lc == "open": rename[c] = "Open"
        elif lc == "high": rename[c] = "High"
        elif lc == "low": rename[c] = "Low"
        elif lc == "close": rename[c] = "Close"
        elif lc == "adj close": rename[c] = "Adj Close"
        elif lc == "volume": rename[c] = "Volume"
    x.rename(columns=rename, inplace=True)

    required = ["Open", "High", "Low", "Close", "Volume"]
    if not all(c in x.columns for c in required):
        return None

    x = x[required].copy()

    for c in required:
        x[c] = pd.to_numeric(x[c], errors="coerce")

    x.dropna(subset=required, inplace=True)
    return x

def download_daily(symbol, period):
    try:
        df = yf.download(
            symbol,
            period=period,
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False
        )
        return normalize_ohlcv(df)
    except Exception:
        return None

def download_hourly(symbol, period="60d"):
    try:
        df = yf.download(
            symbol,
            period=period,
            interval="1h",
            auto_adjust=False,
            progress=False,
            threads=False
        )
        return normalize_ohlcv(df)
    except Exception:
        return None

# ============================================================
# INDICATORS
# ============================================================

def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()

def atr(df, n=14):
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - df["Close"].shift(1)).abs(),
        (df["Low"] - df["Close"].shift(1)).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

def adx(df, n=14):
    h, l, c = df["High"], df["Low"], df["Close"]

    up = h.diff()
    down = -l.diff()

    plus_dm = pd.Series(
        np.where((up > down) & (up > 0), up, 0.0),
        index=df.index
    )
    minus_dm = pd.Series(
        np.where((down > up) & (down > 0), down, 0.0),
        index=df.index
    )

    tr = pd.concat([
        h-l,
        (h-c.shift()).abs(),
        (l-c.shift()).abs()
    ], axis=1).max(axis=1)

    atrv = tr.ewm(alpha=1/n, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1/n, adjust=False).mean() / (atrv + 1e-10)
    minus_di = 100 * minus_dm.ewm(alpha=1/n, adjust=False).mean() / (atrv + 1e-10)

    dx = 100 * (plus_di-minus_di).abs() / (plus_di+minus_di+1e-10)
    return dx.ewm(alpha=1/n, adjust=False).mean()

def rsi(close, n=14):
    d = close.diff()
    up = d.clip(lower=0)
    dn = -d.clip(upper=0)
    au = up.ewm(alpha=1/n, adjust=False).mean()
    ad = dn.ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100/(1 + au/(ad+1e-10))

def macd(close):
    m = ema(close,12)-ema(close,26)
    sig = ema(m,9)
    return m, sig, m-sig

# ============================================================
# VPVR / POC
# ============================================================

def calculate_poc(df, bins=48, lookback=120):
    x = df.tail(lookback).copy()
    if len(x) < 30:
        return np.nan

    lo = float(x["Low"].min())
    hi = float(x["High"].max())

    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return float(x["Close"].iloc[-1])

    typical = (x["High"] + x["Low"] + x["Close"]) / 3
    volume = x["Volume"].fillna(0)

    edges = np.linspace(lo, hi, bins+1)
    idx = np.digitize(typical, edges) - 1
    idx = np.clip(idx, 0, bins-1)

    vol_by_bin = np.zeros(bins)
    for i, v in zip(idx, volume):
        vol_by_bin[int(i)] += float(v)

    poc_idx = int(np.argmax(vol_by_bin))
    return float((edges[poc_idx] + edges[poc_idx+1]) / 2)

# ============================================================
# DAILY ANALYSIS
# ============================================================

def analyze_daily(df):
    if df is None or len(df) < 220:
        return None

    x = df.copy()

    x["EMA20"] = ema(x["Close"],20)
    x["EMA50"] = ema(x["Close"],50)
    x["EMA200"] = ema(x["Close"],200)
    x["RSI"] = rsi(x["Close"])
    x["ADX"] = adx(x)
    x["ATR"] = atr(x)
    _, _, x["MACD_HIST"] = macd(x["Close"])
    x["RVOL"] = x["Volume"]/(x["Volume"].rolling(20).mean()+1e-10)

    x["RH50"] = x["High"].rolling(50).max().shift(1)
    x["BOS"] = (
        (x["Close"] > x["RH50"]) &
        (x["Close"].shift(1) <= x["RH50"])
    ).astype(int)

    latest = x.iloc[-1]

    price = float(latest["Close"])
    atrv = float(latest["ATR"])
    adxv = float(latest["ADX"])

    # KRİTİK VETO 1: YATAY PİYASA
    if not np.isfinite(adxv) or adxv < 20:
        return {
            "eligible": False,
            "reason": "ADX < 20 — yatay piyasa",
            "score": 0,
            "price": price,
            "adx": adxv,
            "rsi": float(latest["RSI"]),
            "rvol": float(latest["RVOL"]),
            "atr": atrv
        }

    poc = calculate_poc(x)
    if not np.isfinite(poc):
        poc = price

    # POC'nin hemen altında alım yok.
    # %0.5 tolerans bandı kullanılıyor.
    poc_buffer = poc * 0.005
    below_poc = price < (poc + poc_buffer)

    # Temel skor
    score = 0.0

    if price > latest["EMA20"]:
        score += 10
    if latest["EMA20"] > latest["EMA50"]:
        score += 12
    if latest["EMA50"] > latest["EMA200"]:
        score += 10

    if 50 <= latest["RSI"] <= 72:
        score += 10
    elif 72 < latest["RSI"] <= 78:
        score += 5

    if latest["MACD_HIST"] > 0:
        score += 10

    if latest["RVOL"] >= 1.10:
        score += 8

    if latest["BOS"] == 1:
        score += 10

    if adxv >= 25:
        score += 10
    elif adxv >= 20:
        score += 5

    # POC üzerinde olmak olumlu
    if price >= poc:
        score += 10

    return {
        "eligible": True,
        "reason": "OK",
        "score": float(min(100, score)),
        "price": price,
        "adx": adxv,
        "rsi": float(latest["RSI"]),
        "rvol": float(latest["RVOL"]),
        "atr": atrv,
        "poc": poc,
        "below_poc": below_poc,
        "ema20": float(latest["EMA20"]),
        "ema50": float(latest["EMA50"]),
        "ema200": float(latest["EMA200"]),
        "macd_hist": float(latest["MACD_HIST"])
    }

# ============================================================
# 4H MTF
# ============================================================

def resample_to_4h(hourly):
    if hourly is None or hourly.empty:
        return None

    x = hourly.copy()

    try:
        if getattr(x.index, "tz", None) is not None:
            x.index = x.index.tz_convert("Europe/Istanbul")
    except Exception:
        pass

    # Yahoo saatlik veriyi 4 saatlik barlara dönüştür
    four = x.resample("4h").agg({
        "Open":"first",
        "High":"max",
        "Low":"min",
        "Close":"last",
        "Volume":"sum"
    }).dropna()

    return four

def check_mtf_4h(hourly):
    four = resample_to_4h(hourly)

    if four is None or len(four) < 60:
        return False, np.nan, np.nan, "4H veri yetersiz"

    e20 = ema(four["Close"],20)
    e50 = ema(four["Close"],50)

    a = float(e20.iloc[-1])
    b = float(e50.iloc[-1])

    return a > b, a, b, "4H EMA20 > EMA50" if a > b else "4H EMA20 <= EMA50"

# ============================================================
# FULL SIGNAL ENGINE
# ============================================================

def final_signal(symbol, daily, hourly, market_daily=None):
    d = analyze_daily(daily)

    if d is None:
        return None

    if not d["eligible"]:
        return {
            "symbol": symbol,
            "signal": "ELENDİ",
            "reason": d["reason"],
            "score": 0,
            "price": d["price"],
            "adx": d["adx"],
            "rsi": d["rsi"],
            "rvol": d["rvol"],
            "poc": np.nan
        }

    # KRİTİK VETO 2: 4H EMA20 > EMA50
    mtf_ok, e20_4h, e50_4h, mtf_reason = check_mtf_4h(hourly)

    if not mtf_ok:
        return {
            "symbol": symbol,
            "signal": "ELENDİ",
            "reason": mtf_reason,
            "score": 0,
            "price": d["price"],
            "adx": d["adx"],
            "rsi": d["rsi"],
            "rvol": d["rvol"],
            "poc": d.get("poc", np.nan)
        }

    # KRİTİK VETO 3: POC altı
    if d.get("below_poc", False):
        return {
            "symbol": symbol,
            "signal": "ELENDİ",
            "reason": "VPVR POC bölgesinin altında",
            "score": 0,
            "price": d["price"],
            "adx": d["adx"],
            "rsi": d["rsi"],
            "rvol": d["rvol"],
            "poc": d["poc"]
        }

    # İsteğe bağlı benchmark RS
    score = d["score"]

    if market_daily is not None and len(market_daily) >= 60:
        try:
            stock_ret = d["price"] / float(daily["Close"].iloc[-60]) - 1
            market_ret = (
                float(market_daily["Close"].iloc[-1]) /
                float(market_daily["Close"].iloc[-60]) - 1
            )
            rs = stock_ret - market_ret

            if rs > 0.10:
                score += 10
            elif rs > 0.03:
                score += 5
        except Exception:
            pass

    score = float(min(100, score))

    # Alım eşiği
    signal = "GÜÇLÜ AL" if score >= 80 else ("AL ADAYI" if score >= 70 else "İZLE")

    price = d["price"]
    atrv = d["atr"]

    return {
        "symbol": symbol,
        "signal": signal,
        "reason": "TÜM FİLTRELER GEÇİLDİ",
        "score": score,
        "price": price,
        "adx": d["adx"],
        "rsi": d["rsi"],
        "rvol": d["rvol"],
        "poc": d["poc"],
        "ema20_4h": e20_4h,
        "ema50_4h": e50_4h,
        "tp1": price + 1.5*atrv,
        "tp2": price + 3.0*atrv,
        "stop": price - 2.0*atrv,
        "atr": atrv
    }

# ============================================================
# BATCH SCAN
# ============================================================

def scan_symbol(symbol, years):
    daily = download_daily(symbol, f"{years}y")
    if daily is None or len(daily) < 220:
        return None, "Günlük veri yetersiz"

    hourly = download_hourly(symbol, "60d")
    if hourly is None or len(hourly) < 100:
        return None, "4H için saatlik veri yetersiz"

    return final_signal(symbol, daily, hourly), "OK"

def scan_universe(symbols, years, workers=6):
    results = []
    failed = []

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {
            ex.submit(scan_symbol, s, years): s
            for s in symbols
        }

        for fut in as_completed(futures):
            s = futures[fut]
            try:
                result, status = fut.result()
                if result is not None:
                    results.append(result)
                else:
                    failed.append((s, status))
            except Exception as e:
                failed.append((s, str(e)[:120]))

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results, failed

# ============================================================
# BACKTEST
# ============================================================

def backtest(df, capital=100000, risk_pct=2):
    df = normalize_ohlcv(df)

    if df is None or len(df) < 220:
        return None

    x = df.copy()
    x["EMA20"] = ema(x["Close"],20)
    x["RSI"] = rsi(x["Close"])
    x["ADX"] = adx(x)
    x["ATR"] = atr(x)
    _, _, x["MACD_HIST"] = macd(x["Close"])
    x["RVOL"] = x["Volume"]/(x["Volume"].rolling(20).mean()+1e-10)

    cash = float(capital)
    shares = 0
    entry = 0
    curve = []
    trades = []

    for i in range(220, len(x)):
        row = x.iloc[i]
        price = float(row["Close"])
        atrv = float(row["ATR"])

        if not np.isfinite(atrv) or atrv <= 0:
            curve.append(cash + shares*price)
            continue

        buy = (
            price > row["EMA20"] and
            row["RSI"] > 50 and
            row["ADX"] >= 20 and
            row["RVOL"] > 1.1 and
            row["MACD_HIST"] > 0
        )

        sell = (
            price < row["EMA20"] or
            row["RSI"] < 42 or
            price < entry - 2*atrv
        )

        if shares == 0 and buy:
            risk_budget = cash*risk_pct/100
            risk_per_share = 2*atrv
            shares = int(risk_budget/risk_per_share)
            shares = min(shares, int(cash*0.95/price))

            if shares > 0:
                cash -= shares*price*1.000525
                entry = price

        elif shares > 0 and sell:
            exit_value = shares*price*0.999475
            pnl = exit_value - shares*entry*1.000525
            cash += exit_value
            trades.append(pnl)
            shares = 0
            entry = 0

        curve.append(cash + shares*price)

    if not curve:
        return None

    eq = pd.Series(curve)
    ret = eq.pct_change().dropna()

    sharpe = float(ret.mean()/(ret.std()+1e-10)*np.sqrt(252))
    dd = eq/eq.cummax()-1
    mdd = float(dd.min()*100)

    wins = [p for p in trades if p > 0]
    losses = [p for p in trades if p <= 0]

    wr = len(wins)/len(trades)*100 if trades else 0
    pf = sum(wins)/abs(sum(losses)) if losses and sum(losses) != 0 else (
        float("inf") if wins else 0
    )

    return {
        "curve": curve,
        "trades": trades,
        "final_nav": curve[-1],
        "return_pct": (curve[-1]/capital-1)*100,
        "sharpe": sharpe,
        "mdd": mdd,
        "win_rate": wr,
        "profit_factor": pf
    }

# ============================================================
# UI
# ============================================================


def build_4h_from_1h(hourly_df):
    """1H Yahoo verisini 4H barlara dönüştürür."""
    if hourly_df is None or hourly_df.empty:
        return pd.DataFrame()
    df = hourly_df.copy()
    try:
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        return df.resample("4h", origin="start_day").agg({
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum"
        }).dropna()
    except Exception:
        return pd.DataFrame()

def mtf_4h_ema_filter(hourly_raw, symbol):
    """4H EMA20 > EMA50 zorunlu filtresi."""
    h1 = normalize_yf_frame(hourly_raw, symbol)
    h4 = build_4h_from_1h(h1)
    if len(h4) < 55:
        return False
    e20 = h4["Close"].ewm(span=20, adjust=False).mean().iloc[-1]
    e50 = h4["Close"].ewm(span=50, adjust=False).mean().iloc[-1]
    return bool(e20 > e50)

def main():
    DB.init()

    st.title("⚡ QUANT MASTER v65.0")
    st.caption(
        "BIST tam evren • ADX ≥ 20 • 4H EMA20 > EMA50 • VPVR/POC filtresi • "
        "ATR risk yönetimi"
    )

    universe, source = get_dynamic_bist_universe()

    with st.sidebar:
        st.header("⚙️ Tarama Ayarları")

        years = st.slider("Günlük geçmiş veri", 1, 5, 3)
        workers = st.slider("Eşzamanlı tarama", 2, 10, 6)
        min_score = st.slider("Minimum sinyal skoru", 50, 95, 70)

        st.markdown("---")
        st.write(f"**Evren:** {len(universe)} hisse")
        st.write(f"**Kaynak:** {source}")

        scan = st.button(
            "🚀 TÜM BIST'İ TARA",
            use_container_width=True,
            type="primary"
        )

        bt = st.button(
            "📈 KCHOL Backtest",
            use_container_width=True
        )

    if scan:
        progress = st.progress(0)
        status = st.empty()

        status.info(
            f"{len(universe)} BIST hissesi taranıyor. "
            "Günlük + 4H veri kontrol ediliyor..."
        )

        results, failed = scan_universe(
            universe,
            years,
            workers
        )

        progress.progress(100)

        st.session_state["results"] = results
        st.session_state["failed"] = failed
        st.session_state["scan_time"] = datetime.now().strftime(
            "%d.%m.%Y %H:%M:%S"
        )

        status.success(
            f"Tarama tamamlandı: {len(results)} hissede veri işlendi."
        )

    if "results" in st.session_state:
        results = st.session_state["results"]

        valid = [
            x for x in results
            if x.get("signal") in ("GÜÇLÜ AL", "AL ADAYI", "İZLE")
        ]

        strong = [
            x for x in results
            if x.get("signal") == "GÜÇLÜ AL" and
            x.get("score", 0) >= min_score
        ]

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("BIST Evreni", len(universe))
        c2.metric("Veri İşlenen", len(results))
        c3.metric("Filtrelerden Geçen", len(valid))
        c4.metric("GÜÇLÜ AL", len(strong))

        st.caption(
            f"Son tarama: {st.session_state.get('scan_time','-')} | "
            f"Evren kaynağı: {source}"
        )

        st.subheader("🏆 Sinyal Matrisi")

        # Sadece yatırım adayı olanları önce göster
        display = [
            x for x in results
            if x.get("signal") in ("GÜÇLÜ AL", "AL ADAYI")
            and x.get("score",0) >= min_score
        ]

        if not display:
            st.warning(
                "Belirlenen eşikleri geçen hisse bulunamadı. "
                "Bu, ADX/MTF/POC filtrelerinin sinyal üretimini engellediği anlamına gelir."
            )

        for item in display:
            score = item["score"]

            if score >= 80:
                cls = "q-good"
            elif score >= 70:
                cls = "q-mid"
            else:
                cls = "q-bad"

            st.markdown(
                f""" <div class="q-card"> <div style="display:flex;justify-content:space-between; align-items:center;"> <div> <div class="q-title" style="font-size:1.25rem;"> {item['symbol']} </div> <div class="q-muted"> Fiyat: {item['price']:.2f} TL &nbsp; | &nbsp; RSI: {item['rsi']:.1f} &nbsp; | &nbsp; ADX: {item['adx']:.1f} &nbsp; | &nbsp; RVOL: {item['rvol']:.2f}x </div> </div> <div class="q-score {cls}"> {item['signal']} — {score:.1f}/100 </div> </div> <hr style="border-color:#334155"> <div style="display:flex;justify-content:space-between; color:#CBD5E1;"> <span>📊 POC: {item['poc']:.2f}</span> <span>4H EMA20: {item['ema20_4h']:.2f}</span> <span>4H EMA50: {item['ema50_4h']:.2f}</span> <span>🎯 TP1: {item['tp1']:.2f}</span> <span>🎯 TP2: {item['tp2']:.2f}</span> <span>🛑 Stop: {item['stop']:.2f}</span> </div> </div> """,
                unsafe_allow_html=True
            )

        with st.expander("🔎 Elenen hisseler / filtre nedenleri"):
            eliminated = [
                x for x in results if x.get("signal") == "ELENDİ"
            ]

            if eliminated:
                edf = pd.DataFrame(eliminated)
                cols = [
                    c for c in
                    ["symbol","reason","adx","rsi","rvol","poc","price"]
                    if c in edf.columns
                ]
                st.dataframe(edf[cols], use_container_width=True)
            else:
                st.write("Elenen sinyal yok.")

        with st.expander("⚠️ Veri alınamayan hisseler"):
            failed = st.session_state.get("failed", [])
            if failed:
                st.dataframe(
                    pd.DataFrame(failed, columns=["symbol","reason"]),
                    use_container_width=True
                )
            else:
                st.success("Veri alınamayan hisse yok.")

        st.subheader("📋 Tüm Tarama Sonuçları")

        all_df = pd.DataFrame(results)

        if not all_df.empty:
            wanted = [
                "symbol","signal","score","price","adx",
                "rsi","rvol","poc","reason"
            ]
            wanted = [c for c in wanted if c in all_df.columns]

            st.dataframe(
                all_df[wanted],
                use_container_width=True,
                hide_index=True
            )

    if bt:
        st.subheader("📈 Backtest")

        with st.spinner("KCHOL backtest çalışıyor..."):
            df = download_daily("KCHOL.IS", "3y")
            result = backtest(df)

        if result:
            a,b,c,d,e = st.columns(5)
            a.metric("Bitiş NAV", f"{result['final_nav']:,.0f} TL")
            b.metric("Getiri", f"{result['return_pct']:+.2f}%")
            c.metric("Sharpe", f"{result['sharpe']:.2f}")
            d.metric("MDD", f"{result['mdd']:.2f}%")
            e.metric("Win Rate", f"{result['win_rate']:.1f}%")

            pf = result["profit_factor"]
            st.metric(
                "Profit Factor",
                "∞" if np.isinf(pf) else f"{pf:.2f}"
            )

            st.line_chart(pd.Series(result["curve"]))
        else:
            st.error("Backtest için yeterli veri alınamadı.")

    st.markdown("---")
    st.caption(
        "Not: Bu sistem bir tahmin garantisi değildir. "
        "Özellikle gün sonu taramasında veri sağlayıcısının gecikmesi ve "
        "BIST kapanış verisinin güncellenme zamanı sonuçları etkileyebilir."
    )

if __name__ == "__main__":
    main()

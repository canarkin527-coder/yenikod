# ==============================================================================
# QUANT MASTER v70 - INSTITUTIONAL SIGNAL ENGINE (REDESIGN)
# ==============================================================================
#
# NEDEN v70 (v67.2'ye göre temel farklar):
#
#  1) TEK KAYNAK SKORLAMA (Single Source of Truth):
#     Tarayıcı ve Backtest AYNI `score_row()` fonksiyonunu çağırır.
#     Böylece backtest'in gösterdiği istatistik, canlıda kullanılan sinyalin
#     tam olarak kendisine aittir. (v67.2'de bu ikisi farklı formüldü.)
#
#  2) ORTOGONAL 5 FAKTÖR BLOĞU (korelasyon azaltıldı):
#     Trend (25) | Momentum (20) | Hacim/Para Akışı (20) |
#     Göreceli Güç RS (20) | Yapı & Çok Zaman Dilimi (15) = 100
#     Aynı "trend var mı" sinyali 5 kez sayılmaz; RS gibi bağımsız ve
#     öngörü gücü yüksek faktöre ağırlık verilir.
#
#  3) GERÇEK 4H TEYİDİ:
#     1H veri çekilir ve 4H'a RESAMPLE edilir (v67.2 sadece 1H'ı 4H sanıyordu).
#
#  4) DOĞRU SUPERTREND:
#     Standart "final band kilitleme" mantığıyla (whipsaw azalır).
#
#  5) ANLAMLI R/R + YAPISAL STOP/HEDEF:
#     Stop = ATR ve son swing low karışımı; Hedef = gerçek direnç seviyesi.
#     R/R artık her hissede değişir; "geçersiz R/R" vetosu gerçekten çalışır.
#
#  6) RİSK BAZLI POZİSYON BOYUTLANDIRMA:
#     Sabit %10 yerine, işlem başına sermayenin %X'i riske edilir
#     (shares = risk_bütçesi / (giriş - stop)), pozisyon ağırlık tavanı ile.
#
#  7) PİYASA REJİM FİLTRESİ:
#     Endeks (XU100) kendi trendinin altındaysa long maruziyeti cezalandırılır
#     / opsiyonel olarak engellenir.
#
#  8) GERÇEKÇİ BACKTEST:
#     Komisyon + slipaj modellenir, look-ahead engellenir (sinyal kapanışta,
#     giriş bir sonraki açılışta), aynı barda stop+hedef çakışırsa kötümser
#     (stop öncelikli) varsayım, tam metrik seti (Profit Factor, Max DD,
#     beklenti/expectancy, Sharpe yaklaşık).
#
#  9) VERİ KALİTESİ:
#     auto_adjust=True (bedelsiz/temettü düzeltmeleri), NaN/az-veri kontrolleri,
#     likidite vetosu.
#
#  UYARI: Bu bir ARAŞTIRMA/EĞİTİM aracıdır. Yatırım tavsiyesi değildir.
#  Geçmiş performans gelecek getiriyi garanti etmez.
# ==============================================================================

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime
import warnings
from concurrent.futures import ThreadPoolExecutor

warnings.filterwarnings("ignore")

# ==============================================================================
# GLOBAL CONFIG
# ==============================================================================

DB_FILE = "quant_master_v70.db"
BENCHMARK_DEFAULT = "XU100.IS"

class CFG:
    # --- Skor eşikleri (grade) ---
    GRADE_A_PLUS = 88.0
    GRADE_A      = 80.0
    GRADE_B_PLUS = 72.0
    SIGNAL_MIN   = 72.0          # Sinyal/backtest giriş eşiği

    # --- Hard veto ---
    MIN_BARS          = 210      # EMA200 için yeterli veri
    MIN_LIQUIDITY_TL  = 5_000_000    # 20g ort. (Close*Volume)
    MAX_EXTENSION_ATR = 4.0      # |fiyat - EMA20| bu kadar ATR'ı aşarsa veto
    MIN_RR            = 1.5      # Min risk/ödül

    # --- Trade planı ---
    ATR_STOP_MULT     = 2.0
    SWING_LOOKBACK    = 10       # yapısal stop için
    RESIST_LOOKBACK   = 20       # hedef (direnç) için
    ATR_TARGET_MULT   = 3.0      # kırılım sonrası ölçülü hedef

    # --- Risk / para yönetimi ---
    INITIAL_CAPITAL   = 100_000.0
    RISK_PER_TRADE    = 0.01     # NAV'ın %1'i riske
    MAX_POSITION_WT   = 0.15     # tek pozisyon NAV'ın max %15'i

    # --- Rejim ---
    REGIME_PENALTY    = 0.85     # kötü rejimde skor çarpanı
    REGIME_HARD_BLOCK = False    # True ise kötü rejimde long engellenir

    # --- Backtest maliyetleri ---
    COMMISSION_PCT    = 0.0015   # işlem başına (tek yön)
    SLIPPAGE_PCT      = 0.0010
    MAX_HOLD_BARS     = 40       # zaman bazlı çıkış (0 = kapalı)


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

REQUIRED_OHLCV = ["Open", "High", "Low", "Close", "Volume"]


# ==============================================================================
# DATA LAYER
# ==============================================================================

def normalize_df(df):
    """yfinance çıktısını temiz OHLCV DataFrame'e indirger (MultiIndex dahil)."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return None

    res = pd.DataFrame(index=df.index)
    if isinstance(df.columns, pd.MultiIndex):
        for col in REQUIRED_OHLCV:
            for tup in df.columns:
                if col in [str(x).strip() for x in tup]:
                    s = df[tup]
                    if isinstance(s, pd.DataFrame):
                        s = s.iloc[:, 0]
                    res[col] = s
                    break
    else:
        for col in REQUIRED_OHLCV:
            if col in df.columns:
                s = df[col]
                if isinstance(s, pd.DataFrame):
                    s = s.iloc[:, 0]
                res[col] = s

    if not all(c in res.columns for c in REQUIRED_OHLCV):
        return None

    for c in REQUIRED_OHLCV:
        res[c] = pd.to_numeric(res[c], errors="coerce")

    res = res[~res.index.duplicated(keep="last")]
    res.dropna(inplace=True)
    return res if len(res) >= 30 else None


@st.cache_data(ttl=900, show_spinner=False)
def fetch_ticker(symbol, period="3y", interval="1d"):
    """auto_adjust=True: bedelsiz/temettü kaynaklı suni sıçramalar düzeltilir."""
    for attempt in range(2):
        try:
            data = yf.download(
                symbol, period=period, interval=interval,
                progress=False, auto_adjust=True, threads=False
            )
            norm = normalize_df(data)
            if norm is not None:
                return norm
        except Exception:
            pass
    return None


def resample_to_4h(df_1h):
    """1H veriyi gerçek 4H mumlarına çevirir."""
    if df_1h is None or df_1h.empty:
        return None
    try:
        agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
        df4 = df_1h.resample("4h").agg(agg).dropna()
        return df4 if len(df4) >= 20 else None
    except Exception:
        return None


@st.cache_data(ttl=900, show_spinner=False)
def fetch_universe(symbols, interval="1d", period="3y"):
    """Çok iş parçacıklı toplu veri çekimi."""
    data_map = {}

    def worker(sym):
        return sym, fetch_ticker(sym, period=period, interval=interval)

    with ThreadPoolExecutor(max_workers=12) as ex:
        for sym, df in ex.map(worker, symbols):
            if df is not None:
                data_map[sym] = df
    return data_map


# ==============================================================================
# INDICATOR ENGINE (Wilder smoothing + doğru Supertrend)
# ==============================================================================

def _wilder(series, period):
    """Wilder RMA (ADX/ATR için doğru smoothing)."""
    return series.ewm(alpha=1.0 / period, adjust=False).mean()


def compute_indicators(df):
    """Tüm indikatörleri hesaplar. Hepsi nedensel (causal) — look-ahead yok."""
    if df is None or len(df) < 50:
        return None
    df = df.copy()
    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]

    # EMA
    for p in (9, 20, 50, 200):
        df[f"EMA_{p}"] = c.ewm(span=p, adjust=False).mean()

    # ATR (Wilder)
    tr = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    df["ATR"] = _wilder(tr, 14)

    # ADX (Wilder)
    up, dn = h.diff(), -l.diff()
    p_dm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    m_dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    atr_w = _wilder(tr, 14) + 1e-10
    p_di = 100 * _wilder(p_dm, 14) / atr_w
    m_di = 100 * _wilder(m_dm, 14) / atr_w
    dx = 100 * (p_di - m_di).abs() / (p_di + m_di + 1e-10)
    df["ADX"] = _wilder(dx, 14)

    # RSI (Wilder)
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    df["RSI"] = 100 - (100 / (1 + gain / (loss + 1e-10)))

    # MACD
    df["MACD"] = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    df["MACD_Sig"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Sig"]

    # RVOL & OBV
    df["RVOL"] = v / (v.rolling(20).mean() + 1e-10)
    df["OBV"] = (np.sign(c.diff()).fillna(0) * v).cumsum()
    df["OBV_EMA"] = df["OBV"].ewm(span=20, adjust=False).mean()
    df["OBV_Rising"] = (df["OBV"] > df["OBV"].shift(3)).astype(int)

    # SMC: BOS / FVG
    df["High_20"] = h.rolling(20).max().shift(1)
    df["BOS"] = ((c > df["High_20"]) & (c.shift(1) <= df["High_20"])).astype(int)
    df["FVG"] = ((l > h.shift(2)) & (c.shift(1) > h.shift(2))).astype(int)

    # POC (volume-weighted value proxy)
    df["POC"] = (c * v).rolling(30).sum() / (v.rolling(30).sum() + 1e-10)

    # Yapısal stop/hedef seviyeleri
    df["SwingLow"] = l.rolling(CFG.SWING_LOOKBACK).min()
    df["Resistance"] = h.rolling(CFG.RESIST_LOOKBACK).max()

    # Likidite
    df["LiqTL"] = (c * v).rolling(20).mean()

    # Supertrend (standart, final-band kilitli)
    df["Supertrend_Dir"] = _supertrend_dir(h, l, c, df["ATR"], mult=3.0)

    return df


def _supertrend_dir(h, l, c, atr, mult=3.0):
    n = len(c)
    hl2 = (h + l) / 2
    upper = (hl2 + mult * atr).values
    lower = (hl2 - mult * atr).values
    cv = c.values
    f_up = np.zeros(n); f_lo = np.zeros(n); direction = np.ones(n)
    f_up[0], f_lo[0] = upper[0], lower[0]
    for i in range(1, n):
        # final lower band kilitle
        f_lo[i] = lower[i] if (lower[i] > f_lo[i-1] or cv[i-1] < f_lo[i-1]) else f_lo[i-1]
        # final upper band kilitle
        f_up[i] = upper[i] if (upper[i] < f_up[i-1] or cv[i-1] > f_up[i-1]) else f_up[i-1]
        # yön
        if cv[i] > f_up[i-1]:
            direction[i] = 1
        elif cv[i] < f_lo[i-1]:
            direction[i] = -1
        else:
            direction[i] = direction[i-1]
    return pd.Series(direction, index=c.index)


# ==============================================================================
# CONTEXT: Relative Strength (RS), 4H MTF teyidi, rejim
# ==============================================================================

def attach_relative_strength(df, benchmark_close):
    """RS_20 / RS_60: hisse getirisi - endeks getirisi (nedensel)."""
    if benchmark_close is None:
        df["RS_20"] = np.nan
        df["RS_60"] = np.nan
        return df
    bench = benchmark_close.reindex(df.index).ffill()
    for w, col in ((20, "RS_20"), (60, "RS_60")):
        stock_ret = df["Close"] / df["Close"].shift(w) - 1.0
        bench_ret = bench / bench.shift(w) - 1.0
        df[col] = (stock_ret - bench_ret) * 100.0
    return df


def attach_mtf(df_daily, df_4h):
    """4H trend (Close>EMA20 ve EMA20 yükseliyor) -> günlük indekse hizala + shift (look-ahead yok)."""
    if df_4h is None:
        df_daily["MTF_Bull"] = 0
        return df_daily
    d4 = df_4h.copy()
    d4["EMA20"] = d4["Close"].ewm(span=20, adjust=False).mean()
    bull4 = ((d4["Close"] > d4["EMA20"]) & (d4["EMA20"] > d4["EMA20"].shift(1))).astype(int)
    # 4H durumunu gün sonuna indir, sonra 1 gün kaydır (o günün intraday'ini kullanma)
    daily_state = bull4.resample("1D").last().ffill()
    aligned = daily_state.reindex(df_daily.index.normalize(), method="ffill")
    aligned.index = df_daily.index
    df_daily["MTF_Bull"] = aligned.shift(1).fillna(0).astype(int)
    return df_daily


def compute_regime(benchmark_df):
    """Endeksin kendi trendi: 1 (boğa) / 0 (nötr) / -1 (ayı). Günlük seri döner."""
    if benchmark_df is None:
        return None
    d = compute_indicators(benchmark_df)
    if d is None:
        return None
    reg = pd.Series(0, index=d.index)
    bull = (d["Close"] > d["EMA50"]) & (d["EMA50"] > d["EMA200"])
    bear = (d["Close"] < d["EMA50"]) & (d["EMA50"] < d["EMA200"])
    reg[bull] = 1
    reg[bear] = -1
    return reg


# ==============================================================================
# SCORING — TEK KAYNAK (tarayıcı VE backtest bunu kullanır)
# ==============================================================================

def build_features(df, benchmark_close, df_4h):
    """Sinyal için gerekli tüm kolonları TEK SEFERDE hesaplar.
       Hem son bar (tarayıcı) hem her bar (backtest) aynı kolonlardan okunur."""
    d = compute_indicators(df)
    if d is None:
        return None
    d = attach_relative_strength(d, benchmark_close)
    d = attach_mtf(d, df_4h)
    return d


def score_row(row, regime_val=1):
    """
    TEK KAYNAK SKORLAMA. Bir indikatör satırından (Series/dict) 0-100 skor üretir.
    5 ortogonal blok. regime_val: -1/0/1 (endeks rejimi).
    Döner: (score, breakdown_dict)
    """
    def g(k):
        v = row[k]
        try:
            return float(v)
        except Exception:
            return np.nan

    c = g("Close")
    bd = {}

    # ---------- 1) TREND & YÖN (25) ----------
    t = 0.0
    if c > g("EMA_200"): t += 8.0
    if g("EMA_50") > g("EMA_200"): t += 7.0
    if g("EMA_9") > g("EMA_20") > g("EMA_50"): t += 6.0
    elif g("EMA_20") > g("EMA_50"): t += 3.0
    if g("Supertrend_Dir") == 1: t += 4.0
    bd["Trend"] = t

    # ---------- 2) MOMENTUM (20) ----------
    m = 0.0
    adx = g("ADX")
    if adx >= 25: m += 8.0
    elif adx >= 20: m += 4.0
    if g("MACD") > g("MACD_Sig") and g("MACD_Hist") > 0: m += 7.0
    elif g("MACD_Hist") > 0: m += 3.0
    rsi = g("RSI")
    if 50 <= rsi <= 65: m += 5.0
    elif (45 <= rsi < 50) or (65 < rsi <= 72): m += 2.0
    bd["Momentum"] = m

    # ---------- 3) HACİM / PARA AKIŞI (20) ----------
    fl = 0.0
    rvol = g("RVOL")
    if rvol >= 1.5: fl += 8.0
    elif rvol >= 1.1: fl += 5.0
    elif rvol >= 0.8: fl += 2.0
    if g("OBV") > g("OBV_EMA"): fl += 7.0
    if g("OBV_Rising") == 1: fl += 5.0
    bd["Flow"] = fl

    # ---------- 4) GÖRECELİ GÜÇ RS (20) — bağımsız, öngörü gücü yüksek ----------
    rs = 0.0
    rs20, rs60 = g("RS_20"), g("RS_60")
    if not np.isnan(rs20):
        if rs20 > 3.0: rs += 8.0
        elif rs20 > 0.0: rs += 4.0
    if not np.isnan(rs60):
        if rs60 > 5.0: rs += 7.0
        elif rs60 > 0.0: rs += 3.0
    if not np.isnan(rs20) and not np.isnan(rs60) and rs20 > rs60: rs += 5.0
    bd["RS"] = rs

    # ---------- 5) YAPI & ÇOK ZAMAN DİLİMİ (15) ----------
    stc = 0.0
    if g("MTF_Bull") == 1: stc += 6.0
    if g("BOS") == 1 or g("FVG") == 1: stc += 5.0
    if c > g("POC"): stc += 4.0
    bd["Structure"] = stc

    score = t + m + fl + rs + stc

    # ---------- REJİM MODİFİKATÖRÜ ----------
    if regime_val == -1:
        score *= CFG.REGIME_PENALTY
    bd["_regime"] = regime_val
    bd["_raw"] = t + m + fl + rs + stc

    return round(score, 1), bd


def grade_of(score):
    if score >= CFG.GRADE_A_PLUS: return "A+"
    if score >= CFG.GRADE_A: return "A"
    if score >= CFG.GRADE_B_PLUS: return "B+"
    return "WATCH"


# ==============================================================================
# TRADE PLAN — yapısal stop / gerçek hedef / anlamlı R-R
# ==============================================================================

def build_trade_plan(row):
    """Stop = ATR ve swing-low karışımı (tighter valid). Hedef = gerçek direnç
       ya da kırılım sonrası ölçülü hareket. R/R gerçekten değişkendir."""
    c = float(row["Close"])
    atr = float(row["ATR"])
    swing_low = float(row["SwingLow"]) if not pd.isna(row["SwingLow"]) else c - 2 * atr
    resist = float(row["Resistance"]) if not pd.isna(row["Resistance"]) else c + 3 * atr

    atr_stop = c - CFG.ATR_STOP_MULT * atr
    struct_stop = swing_low - 0.2 * atr
    # geçerli olan daha yüksek (daha tighter) stop'u seç
    stop = max(atr_stop, struct_stop) if struct_stop < c else atr_stop
    stop = min(stop, c - 0.5 * atr)  # aşırı yakın stop'u engelle

    # hedef: fiyat direnci zaten kırdıysa ölçülü hareket, değilse direnç
    if resist <= c * 1.01:
        tp = c + CFG.ATR_TARGET_MULT * atr
    else:
        tp = resist

    risk = c - stop
    reward = tp - c
    rr = reward / (risk + 1e-10)
    return round(stop, 2), round(tp, 2), round(rr, 2), round(risk, 2)


# ==============================================================================
# EVALUATION (tarayıcı) — hard veto + tek kaynak skor
# ==============================================================================

def evaluate_symbol(symbol, feat_df, regime_series):
    if feat_df is None or len(feat_df) < CFG.MIN_BARS:
        return None, "VETO: Yetersiz Veri"

    row = feat_df.iloc[-1]
    c, atr = float(row["Close"]), float(row["ATR"])
    ema20 = float(row["EMA_20"])

    # --- HARD VETO ---
    if pd.isna(atr) or atr <= 0:
        return None, "VETO: Geçersiz ATR"
    if float(row["LiqTL"]) < CFG.MIN_LIQUIDITY_TL:
        return None, "VETO: Düşük Likidite"
    if abs(c - ema20) > CFG.MAX_EXTENSION_ATR * atr:
        return None, "VETO: Aşırı Uzama (parabolik)"

    stop, tp, rr, risk = build_trade_plan(row)
    if risk <= 0:
        return None, "VETO: Geçersiz Stop"
    if rr < CFG.MIN_RR:
        return None, f"VETO: Yetersiz R/R ({rr})"

    # --- rejim ---
    regime_val = 1
    if regime_series is not None:
        try:
            regime_val = int(regime_series.reindex(feat_df.index, method="ffill").iloc[-1])
        except Exception:
            regime_val = 1
    if CFG.REGIME_HARD_BLOCK and regime_val == -1:
        return None, "VETO: Ayı Rejimi"

    # --- SKOR (tek kaynak) ---
    score, bd = score_row(row, regime_val)
    grade = grade_of(score)

    res = {
        "Symbol": symbol,
        "Price": round(c, 2),
        "Score": score,
        "Grade": grade,
        "Regime": {1: "Boğa", 0: "Nötr", -1: "Ayı"}.get(regime_val, "?"),
        "Trend": bd["Trend"], "Mom": bd["Momentum"], "Flow": bd["Flow"],
        "RS": bd["RS"], "Struct": bd["Structure"],
        "ADX": round(float(row["ADX"]), 1),
        "RSI": round(float(row["RSI"]), 1),
        "RVOL": round(float(row["RVOL"]), 2),
        "RS_20": None if pd.isna(row["RS_20"]) else round(float(row["RS_20"]), 1),
        "Stop": stop, "Target": tp, "RR": rr, "ATR": round(atr, 2),
    }
    return res, "PASS"


# ==============================================================================
# BACKTEST — AYNI score_row() + gerçekçi maliyet/look-ahead
# ==============================================================================

def run_backtest(data_map, benchmark_close, benchmark_df_4h_map=None,
                 min_score=None, regime_series=None):
    min_score = CFG.SIGNAL_MIN if min_score is None else min_score
    trades = []

    for sym, df in data_map.items():
        # 4H yoksa MTF nötr; backtest hızlı kalsın diye 4H opsiyonel
        df4 = benchmark_df_4h_map.get(sym) if benchmark_df_4h_map else None
        feat = build_features(df, benchmark_close, df4)
        if feat is None or len(feat) < CFG.MIN_BARS:
            continue

        # rejim hizalı
        if regime_series is not None:
            reg_aligned = regime_series.reindex(feat.index, method="ffill").fillna(1)
        else:
            reg_aligned = pd.Series(1, index=feat.index)

        in_pos = False
        entry_px = stop = tp = 0.0
        entry_i = entry_date = None
        open_arr = feat["Open"].values
        high_arr = feat["High"].values
        low_arr = feat["Low"].values

        for i in range(CFG.MIN_BARS, len(feat) - 1):  # -1: girişi i+1 açılışında
            row = feat.iloc[i]

            if not in_pos:
                regime_val = int(reg_aligned.iloc[i])
                if CFG.REGIME_HARD_BLOCK and regime_val == -1:
                    continue
                # hard veto (backtest'te de aynı mantık)
                atr = float(row["ATR"])
                if pd.isna(atr) or atr <= 0:
                    continue
                if float(row["LiqTL"]) < CFG.MIN_LIQUIDITY_TL:
                    continue
                if abs(float(row["Close"]) - float(row["EMA_20"])) > CFG.MAX_EXTENSION_ATR * atr:
                    continue
                stp, tgt, rr, risk = build_trade_plan(row)
                if risk <= 0 or rr < CFG.MIN_RR:
                    continue

                score, _ = score_row(row, regime_val)
                if score >= min_score:
                    # GİRİŞ: bir sonraki bar AÇILIŞ (look-ahead yok) + slipaj
                    entry_px = open_arr[i + 1] * (1 + CFG.SLIPPAGE_PCT)
                    stop, tp = stp, tgt
                    entry_i, entry_date = i + 1, feat.index[i + 1]
                    in_pos = True
            else:
                hi, lo = high_arr[i], low_arr[i]
                exit_px = None; reason = None
                # aynı barda ikisi de tetiklenirse KÖTÜMSER: stop öncelikli
                if lo <= stop:
                    exit_px, reason = stop * (1 - CFG.SLIPPAGE_PCT), "STOP"
                elif hi >= tp:
                    exit_px, reason = tp * (1 - CFG.SLIPPAGE_PCT), "TARGET"
                elif CFG.MAX_HOLD_BARS and (i - entry_i) >= CFG.MAX_HOLD_BARS:
                    exit_px, reason = feat["Close"].iloc[i] * (1 - CFG.SLIPPAGE_PCT), "TIME"

                if exit_px is not None:
                    gross = exit_px / entry_px - 1.0
                    net = gross - 2 * CFG.COMMISSION_PCT  # giriş+çıkış komisyonu
                    trades.append({
                        "Symbol": sym, "Entry": entry_date, "Exit": feat.index[i],
                        "Bars": i - entry_i, "PnL_Pct": round(net * 100, 2),
                        "Reason": reason
                    })
                    in_pos = False

    return pd.DataFrame(trades)


def backtest_metrics(trades_df):
    """Profesyonel metrik seti."""
    if trades_df is None or trades_df.empty:
        return {}
    r = trades_df["PnL_Pct"] / 100.0
    wins = r[r > 0]; losses = r[r <= 0]
    n = len(r)
    win_rate = len(wins) / n * 100
    avg_win = wins.mean() * 100 if len(wins) else 0.0
    avg_loss = losses.mean() * 100 if len(losses) else 0.0
    gross_win = wins.sum(); gross_loss = -losses.sum()
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
    expectancy = r.mean() * 100
    # basit bileşik equity eğrisi (her işlem sıralı, eşit ağırlık varsayımı)
    equity = (1 + r).cumprod()
    peak = equity.cummax()
    max_dd = ((equity - peak) / peak).min() * 100
    sharpe = (r.mean() / (r.std() + 1e-10)) * np.sqrt(len(r)) if len(r) > 1 else 0.0
    return {
        "Toplam İşlem": n,
        "Kazanma Oranı %": round(win_rate, 1),
        "Ort. Kazanç %": round(avg_win, 2),
        "Ort. Kayıp %": round(avg_loss, 2),
        "Profit Factor": round(profit_factor, 2) if profit_factor != float("inf") else "∞",
        "Beklenti (Expectancy) %": round(expectancy, 2),
        "Max Drawdown %": round(max_dd, 1),
        "Sharpe (yaklaşık)": round(sharpe, 2),
    }


# ==============================================================================
# DATABASE — risk bazlı pozisyon boyutlandırma
# ==============================================================================

class DB:
    @staticmethod
    def init():
        conn = sqlite3.connect(DB_FILE); cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, cash REAL, nav REAL, positions INTEGER)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS active (
            symbol TEXT PRIMARY KEY, entry_date TEXT, entry_price REAL, shares INTEGER,
            total_cost REAL, stop REAL, target REAL, score REAL, grade TEXT)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS closed (
            id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, entry_date TEXT, exit_date TEXT,
            entry_price REAL, exit_price REAL, shares INTEGER, pnl REAL, pnl_pct REAL, reason TEXT)""")
        cur.execute("SELECT COUNT(*) FROM ledger")
        if cur.fetchone()[0] == 0:
            cur.execute("INSERT INTO ledger (timestamp, cash, nav, positions) VALUES (?,?,?,?)",
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), CFG.INITIAL_CAPITAL, CFG.INITIAL_CAPITAL, 0))
        conn.commit(); conn.close()

    @staticmethod
    def state():
        conn = sqlite3.connect(DB_FILE); cur = conn.cursor()
        cur.execute("SELECT cash FROM ledger ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        active = pd.read_sql_query("SELECT * FROM active", conn)
        conn.close()
        cash = float(row[0]) if row else CFG.INITIAL_CAPITAL
        return cash, active

    @staticmethod
    def nav(cash, active_df):
        invested = active_df["total_cost"].sum() if not active_df.empty else 0.0
        return cash + invested  # paper: maliyet üzerinden (mark-to-cost)

    @staticmethod
    def buy(symbol, price, score, grade, stop, target):
        conn = sqlite3.connect(DB_FILE); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM active WHERE symbol=?", (symbol,))
        if cur.fetchone()[0] > 0:
            conn.close(); return False, "Zaten portföyde."
        cur.execute("SELECT cash FROM ledger ORDER BY id DESC LIMIT 1")
        cash = float(cur.fetchone()[0])
        active = pd.read_sql_query("SELECT * FROM active", conn)
        nav = DB.nav(cash, active)

        risk_per_share = price - stop
        if risk_per_share <= 0:
            conn.close(); return False, "Geçersiz stop (risk<=0)."
        # RİSK BAZLI BOYUT: NAV*%risk / hisse başı risk
        risk_budget = nav * CFG.RISK_PER_TRADE
        shares_by_risk = int(risk_budget // risk_per_share)
        # pozisyon ağırlık tavanı
        max_cost = min(cash, nav * CFG.MAX_POSITION_WT)
        shares_by_cap = int(max_cost // price)
        shares = max(0, min(shares_by_risk, shares_by_cap))
        if shares <= 0:
            conn.close(); return False, "Boyutlandırma 0 lot verdi (risk/tavan sınırı)."

        cost = shares * price
        if cost > cash:
            conn.close(); return False, "Nakit yetersiz."
        new_cash = cash - cost
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""INSERT INTO active VALUES (?,?,?,?,?,?,?,?,?)""",
                    (symbol, now, price, shares, cost, stop, target, score, grade))
        cur.execute("SELECT COUNT(*) FROM active"); pc = cur.fetchone()[0]
        cur.execute("INSERT INTO ledger (timestamp, cash, nav, positions) VALUES (?,?,?,?)",
                    (now, new_cash, new_cash + cost, pc))
        conn.commit(); conn.close()
        return True, f"ALIM: {shares} lot {symbol} @ ₺{price:.2f} (risk ₺{shares*risk_per_share:,.0f})"

    @staticmethod
    def sell(symbol, exit_price, reason="MANUAL"):
        conn = sqlite3.connect(DB_FILE); cur = conn.cursor()
        cur.execute("SELECT entry_date, entry_price, shares, total_cost FROM active WHERE symbol=?", (symbol,))
        row = cur.fetchone()
        if not row:
            conn.close(); return False, "Pozisyon yok."
        entry_date, entry_price, shares, cost = row
        proceeds = shares * exit_price
        pnl = proceeds - cost
        pnl_pct = (exit_price / entry_price - 1) * 100
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""INSERT INTO closed (symbol, entry_date, exit_date, entry_price, exit_price, shares, pnl, pnl_pct, reason)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (symbol, entry_date, now, entry_price, exit_price, shares, pnl, pnl_pct, reason))
        cur.execute("DELETE FROM active WHERE symbol=?", (symbol,))
        cur.execute("SELECT cash FROM ledger ORDER BY id DESC LIMIT 1")
        new_cash = float(cur.fetchone()[0]) + proceeds
        cur.execute("SELECT COUNT(*) FROM active"); pc = cur.fetchone()[0]
        cur.execute("INSERT INTO ledger (timestamp, cash, nav, positions) VALUES (?,?,?,?)",
                    (now, new_cash, new_cash, pc))
        conn.commit(); conn.close()
        return True, f"SATIŞ: {symbol} @ ₺{exit_price:.2f} | PnL ₺{pnl:,.2f} (%{pnl_pct:.2f})"


# ==============================================================================
# STREAMLIT UI
# ==============================================================================

st.set_page_config(page_title="QUANT MASTER v70 | Signal Engine", page_icon="⚡",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
.main,.stApp{background-color:#030712;color:#F8FAFC;}
.card{background:linear-gradient(135deg,#0F172A,#1E293B);border:1px solid #334155;
border-radius:12px;padding:16px;margin-bottom:12px;}
.mt{font-size:.8rem;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:1px;}
.mv{font-size:1.6rem;font-weight:900;color:#38BDF8;margin-top:4px;}
</style>""", unsafe_allow_html=True)


def main():
    DB.init()
    st.title("⚡ QUANT MASTER v70 — Institutional Signal Engine")
    st.caption("Tek kaynak skorlama • Gerçek 4H teyidi • Doğru Supertrend • Risk bazlı boyutlandırma • Gerçekçi backtest")

    st.sidebar.header("Kontrol Merkezi")
    benchmark_sym = st.sidebar.text_input("Benchmark", BENCHMARK_DEFAULT)
    CFG.SIGNAL_MIN = st.sidebar.slider("Sinyal Eşiği (Score)", 60, 95, int(CFG.SIGNAL_MIN))
    CFG.RISK_PER_TRADE = st.sidebar.slider("İşlem Başı Risk %", 0.5, 3.0, CFG.RISK_PER_TRADE * 100, 0.25) / 100
    CFG.REGIME_HARD_BLOCK = st.sidebar.checkbox("Ayı rejiminde long engelle", value=False)
    run_btn = st.sidebar.button("🚀 BIST 100 Tara", use_container_width=True)

    cash, active_df = DB.state()
    nav = DB.nav(cash, active_df)
    invested = active_df["total_cost"].sum() if not active_df.empty else 0.0

    c1, c2, c3 = st.columns(3)
    c1.markdown(f'<div class="card"><div class="mt">Nakit</div><div class="mv">₺{cash:,.0f}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="card"><div class="mt">Pozisyon Değeri</div><div class="mv">₺{invested:,.0f}</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="card"><div class="mt">NAV</div><div class="mv">₺{nav:,.0f}</div></div>', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["🎯 Tarama & Sinyal", "💼 Portföy", "📜 Geçmiş", "🧪 Backtest"])

    # ---- TAB 1 ----
    with tab1:
        if run_btn:
            with st.spinner("1D + 1H veriler çekiliyor, 4H'a resample ediliyor, puanlanıyor..."):
                data_1d = fetch_universe(BIST100_TICKERS, interval="1d", period="3y")
                data_1h = fetch_universe(BIST100_TICKERS, interval="1h", period="180d")
                bench_df = fetch_ticker(benchmark_sym, period="3y", interval="1d")
                bench_close = bench_df["Close"] if bench_df is not None else None
                regime = compute_regime(bench_df)

                results, vetoed = [], []
                for sym in BIST100_TICKERS:
                    df1 = data_1d.get(sym)
                    if df1 is None:
                        continue
                    df4 = resample_to_4h(data_1h.get(sym))
                    feat = build_features(df1, bench_close, df4)
                    res, status = evaluate_symbol(sym, feat, regime)
                    if status == "PASS":
                        results.append(res)
                    else:
                        vetoed.append({"Symbol": sym, "Reason": status})

                rdf = pd.DataFrame(results)
                if not rdf.empty:
                    rdf.sort_values("Score", ascending=False, inplace=True)
                st.session_state["res"] = rdf
                st.session_state["veto"] = pd.DataFrame(vetoed)

        if "res" in st.session_state and not st.session_state["res"].empty:
            rdf = st.session_state["res"]
            gf = st.radio("Sınıf", ["TÜMÜ", "A+", "A", "B+", "WATCH"], horizontal=True)
            fdf = rdf if gf == "TÜMÜ" else rdf[rdf["Grade"] == gf]
            st.dataframe(fdf, use_container_width=True, height=420)

            with st.expander(f"Elenenler ({len(st.session_state.get('veto', []))})"):
                if not st.session_state.get("veto", pd.DataFrame()).empty:
                    st.dataframe(st.session_state["veto"], use_container_width=True)

            st.divider(); st.subheader("Sanal Alım (Risk Bazlı Boyut)")
            cc1, cc2 = st.columns([3, 1])
            with cc1:
                sel = st.selectbox("Hisse", fdf["Symbol"].tolist() if not fdf.empty else [])
            with cc2:
                st.write(""); st.write("")
                if st.button("Alım Yap", use_container_width=True) and sel:
                    r = fdf[fdf["Symbol"] == sel].iloc[0]
                    ok, msg = DB.buy(r["Symbol"], r["Price"], r["Score"], r["Grade"], r["Stop"], r["Target"])
                    (st.success if ok else st.error)(msg)
                    if ok: st.rerun()
        else:
            st.info("Sol menüden taramayı başlatın.")

    # ---- TAB 2 ----
    with tab2:
        st.subheader("Aktif Pozisyonlar")
        _, adf = DB.state()
        if not adf.empty:
            st.dataframe(adf, use_container_width=True)
            s1, s2, s3 = st.columns([2, 2, 1])
            with s1: ssym = st.selectbox("Kapat", adf["symbol"].tolist())
            with s2: sprice = st.number_input("Satış Fiyatı ₺", value=0.0, step=0.5)
            with s3:
                st.write(""); st.write("")
                if st.button("Kapat", use_container_width=True):
                    if sprice > 0:
                        ok, msg = DB.sell(ssym, sprice)
                        (st.success if ok else st.error)(msg)
                        if ok: st.rerun()
                    else:
                        st.error("Geçerli fiyat girin.")
        else:
            st.info("Açık pozisyon yok.")

    # ---- TAB 3 ----
    with tab3:
        st.subheader("Kapanan İşlemler")
        conn = sqlite3.connect(DB_FILE)
        cdf = pd.read_sql_query("SELECT * FROM closed ORDER BY id DESC", conn); conn.close()
        if not cdf.empty:
            st.dataframe(cdf, use_container_width=True)
            wr = (cdf["pnl"] > 0).mean() * 100
            st.metric("Gerçekleşen Kazanma Oranı", f"%{wr:.1f}")
        else:
            st.info("Geçmiş işlem yok.")

    # ---- TAB 4 ----
    with tab4:
        st.subheader("Backtest — canlı sinyalle BİREBİR aynı skorlama")
        st.caption("Komisyon+slipaj dahil • look-ahead engelli • aynı barda stop+hedef çakışması kötümser.")
        n_sym = st.slider("Test edilecek hisse sayısı", 10, len(BIST100_TICKERS), 40)
        use_4h_bt = st.checkbox("Backtest'te 4H teyidi kullan (yavaşlatır)", value=False)
        if st.button("🧪 Backtest Çalıştır"):
            with st.spinner("Tarihsel simülasyon..."):
                syms = BIST100_TICKERS[:n_sym]
                data_bt = fetch_universe(syms, interval="1d", period="3y")
                bench_df = fetch_ticker(benchmark_sym, period="3y", interval="1d")
                bench_close = bench_df["Close"] if bench_df is not None else None
                regime = compute_regime(bench_df)
                bt4 = None
                if use_4h_bt:
                    d1h = fetch_universe(syms, interval="1h", period="180d")
                    bt4 = {s: resample_to_4h(d1h.get(s)) for s in syms}
                trades = run_backtest(data_bt, bench_close, bt4, regime_series=regime)

                if not trades.empty:
                    m = backtest_metrics(trades)
                    cols = st.columns(4)
                    for i, (k, v) in enumerate(m.items()):
                        cols[i % 4].metric(k, v)
                    st.dataframe(trades.sort_values("Exit", ascending=False), use_container_width=True)
                else:
                    st.warning("Kriterlere uyan işlem üretilmedi.")

    st.divider()
    st.caption("⚠️ Eğitim/araştırma amaçlıdır. Yatırım tavsiyesi değildir. "
               "Backtest sonuçları maliyet/slipaj varsayımlarına ve survivorship-bias sınırına tabidir; "
               "geçmiş performans gelecek getiriyi garanti etmez.")


if __name__ == "__main__":
    main()

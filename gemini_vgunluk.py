import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
import time

warnings.filterwarnings("ignore")

# ==============================================================================
# QUANT MASTER v65.2 — HIGH PRECISION FAST LIVE BIST TERMINAL
# ==============================================================================
# Amaç:
# - Tüm BIST evrenini hızlı biçimde taramak
# - Canlı/son piyasa fiyatını korumak
# - ADX < 20 yatay piyasa veto
# - Günlük trend veto
# - 4H EMA20 > EMA50 MTF veto
# - VPVR/POC veto
# - RS / RSI / MACD / RVOL / OBV / BOS / FVG teyidi
# - ATR tabanlı SL / TP
# - Yalnızca yüksek kaliteli A+, A, B+ adayları
# ==============================================================================

st.set_page_config(
    page_title="QUANT MASTER v65.2 | High Precision",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(""" <style> .main,.stApp { background:#030712; color:#F8FAFC; } .terminal-card { background:linear-gradient(135deg,#0F172A 0%,#1E293B 100%); border:1px solid #334155;border-radius:12px;padding:18px;margin-bottom:12px; box-shadow:0 8px 15px -5px rgba(0,0,0,.45); } .metric-title {font-size:.8rem;font-weight:700;color:#94A3B8;text-transform:uppercase;} .metric-val {font-size:1.7rem;font-weight:900;color:#38BDF8;} .live-ticker {color:#38BDF8;font-weight:bold;font-family:monospace;} .badge-a {background:#064E3B;border:1px solid #10B981;color:#34D399;padding:5px 10px;border-radius:7px;font-weight:800;} .badge-aplus {background:#14532D;border:1px solid #22C55E;color:#86EFAC;padding:5px 10px;border-radius:7px;font-weight:900;} .badge-b {background:#1E3A8A;border:1px solid #3B82F6;color:#60A5FA;padding:5px 10px;border-radius:7px;font-weight:800;} </style> """, unsafe_allow_html=True)

DB_FILE = "quant_master_v65_2_pro.db"
INITIAL_CAPITAL = 100000.0

# ==============================================================================
# 1 — DATABASE
# ==============================================================================
class Database:
@staticmethod
    def init():
        con = sqlite3.connect(DB_FILE)
        cur = con.cursor()
        cur.execute(""" CREATE TABLE IF NOT EXISTS portfolio ( id INTEGER PRIMARY KEY CHECK(id=1), cash REAL NOT NULL, updated_at TEXT NOT NULL )""")
        cur.execute(""" CREATE TABLE IF NOT EXISTS positions ( symbol TEXT PRIMARY KEY, entry_date TEXT NOT NULL, entry_price REAL NOT NULL, shares INTEGER NOT NULL, stop_loss REAL NOT NULL, tp1 REAL NOT NULL, tp2 REAL NOT NULL, score REAL NOT NULL, quality TEXT NOT NULL )""")
        cur.execute(""" CREATE TABLE IF NOT EXISTS trades ( id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, entry_date TEXT NOT NULL, exit_date TEXT NOT NULL, entry_price REAL NOT NULL, exit_price REAL NOT NULL, shares INTEGER NOT NULL, pnl REAL NOT NULL, pnl_pct REAL NOT NULL, reason TEXT NOT NULL )""")
        cur.execute("SELECT COUNT(*) FROM portfolio")
        if cur.fetchone()[0] == 0:
            cur.execute(
                "INSERT INTO portfolio(id,cash,updated_at) VALUES(1,?,?)",
                (INITIAL_CAPITAL, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
        con.commit()
        con.close()

@staticmethod
    def cash():
        con = sqlite3.connect(DB_FILE)
        row = con.execute("SELECT cash FROM portfolio WHERE id=1").fetchone()
        con.close()
        return float(row[0]) if row else INITIAL_CAPITAL

@staticmethod
    def positions():
        con = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM positions ORDER BY symbol", con)
        con.close()
        return df

@staticmethod
    def open_position(symbol, price, shares, stop, tp1, tp2, score, quality):
        con = sqlite3.connect(DB_FILE)
        cur = con.cursor()
        cash = Database.cash()
        cost = shares * price * 1.000525
        if cost > cash:
            con.close()
            return False, "Yetersiz nakit."
        cur.execute(""" INSERT OR REPLACE INTO positions VALUES(?,?,?,?,?,?,?,?,?) """, (
            symbol, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            price, int(shares), stop, tp1, tp2, score, quality
        ))
        new_cash = cash - cost
        cur.execute(
            "UPDATE portfolio SET cash=?,updated_at=? WHERE id=1",
            (new_cash, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        con.commit()
        con.close()
        return True, f"{symbol}: {shares} lot paper trade açıldı."

@staticmethod
    def close_position(symbol, price, reason="MANUAL_CLOSE"):
        con = sqlite3.connect(DB_FILE)
        cur = con.cursor()
        row = cur.execute(
            "SELECT * FROM positions WHERE symbol=?", (symbol,)
        ).fetchone()
        if not row:
            con.close()
            return
        _, entry_date, entry, shares, _, _, _, _, _ = row
        pnl = (price-entry) * shares
        pnl_pct = (price/entry-1)*100 if entry else 0
        proceeds = shares * price * 0.999475
        cash = Database.cash() + proceeds
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(""" INSERT INTO trades(symbol,entry_date,exit_date,entry_price,exit_price, shares,pnl,pnl_pct,reason) VALUES(?,?,?,?,?,?,?,?,?) """, (symbol,entry_date,now,entry,price,shares,pnl,pnl_pct,reason))
        cur.execute("DELETE FROM positions WHERE symbol=?", (symbol,))
        cur.execute(
            "UPDATE portfolio SET cash=?,updated_at=? WHERE id=1",
            (cash, now)
        )
        con.commit()
        con.close()

# ==============================================================================
# 2 — DATA LAYER
# ==============================================================================
@st.cache_data(ttl=90, show_spinner=False)
def download_batch(symbols, period="3y", interval="1d"):
    if not symbols:
        return pd.DataFrame()
    return yf.download(
        list(symbols),
        period=period,
        interval=interval,
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=True
    )

def normalize(raw, symbol):
    if raw is None or raw.empty:
        return pd.DataFrame()
    try:
        if isinstance(raw.columns, pd.MultiIndex):
            lv0 = raw.columns.get_level_values(0)
            lv1 = raw.columns.get_level_values(-1)
            if symbol in lv0:
                df = raw[symbol].copy()
            elif symbol in lv1:
                df = raw.xs(symbol, axis=1, level=-1).copy()
            else:
                return pd.DataFrame()
        else:
            df = raw.copy()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [
                c[0] if isinstance(c, tuple) else c for c in df.columns
            ]

        needed = ["Open","High","Low","Close","Volume"]
        if any(c not in df.columns for c in needed):
            return pd.DataFrame()
        return df[needed].dropna(subset=needed).copy()
    except Exception:
        return pd.DataFrame()

def get_live_price(symbol):
    # Canlı fiyat korunur. Yahoo'nun quote endpoint'i mevcutsa kullanılır;
    # başarısız olursa son kapanışa dönülür.
    try:
        t = yf.Ticker(symbol)
        q = getattr(t, "fast_info", None)
        if q:
            for key in ("last_price", "regularMarketPrice"):
                try:
                    v = q.get(key)
                    if v is not None and np.isfinite(float(v)) and float(v) > 0:
                        return float(v)
                except Exception:
                    pass
    except Exception:
        pass
    return 0.0

def live_quotes_parallel(symbols, fallback_data):
    quotes = {}
    # Önce toplu günlük son fiyatını doldur.
    for s in symbols:
        d = normalize(fallback_data, s)
        quotes[s] = float(d["Close"].iloc[-1]) if not d.empty else 0.0

    # Sadece adaylarda gerçek canlı quote çağrısı yapılır.
    return quotes

# ==============================================================================
# 3 — INDICATORS
# ==============================================================================
class Indicators:
@staticmethod
    def calc(df):
        if df is None or len(df) < 220:
            return None
        d = df.copy()
        c,h,l,v = d["Close"],d["High"],d["Low"],d["Volume"]

        for p in (20,50,200):
            d[f"EMA_{p}"] = c.ewm(span=p,adjust=False).mean()

        tr = pd.concat([
            h-l,(h-c.shift(1)).abs(),(l-c.shift(1)).abs()
        ],axis=1).max(axis=1)
        d["ATR"] = tr.ewm(alpha=1/14,adjust=False).mean()

        delta = c.diff()
        up = delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean()
        dn = (-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
        d["RSI"] = 100-(100/(1+up/(dn+1e-10)))

        ef=c.ewm(span=12,adjust=False).mean()
        es=c.ewm(span=26,adjust=False).mean()
        d["MACD"]=ef-es
        d["MACD_Signal"]=d["MACD"].ewm(span=9,adjust=False).mean()
        d["MACD_Hist"]=d["MACD"]-d["MACD_Signal"]

        d["OBV"]=(np.sign(c.diff())*v).fillna(0).cumsum()
        d["OBV_EMA"]=d["OBV"].ewm(span=20,adjust=False).mean()
        d["RVOL"]=v/(v.rolling(20).mean()+1e-10)

        # ADX
        upmove=h.diff()
        downmove=-l.diff()
        plus=pd.Series(
            np.where((upmove>downmove)&(upmove>0),upmove,0.0),
            index=d.index
        )
        minus=pd.Series(
            np.where((downmove>upmove)&(downmove>0),downmove,0.0),
            index=d.index
        )
        atr=d["ATR"]
        pdi=100*plus.ewm(alpha=1/14,adjust=False).mean()/(atr+1e-10)
        mdi=100*minus.ewm(alpha=1/14,adjust=False).mean()/(atr+1e-10)
        dx=100*(pdi-mdi).abs()/(pdi+mdi+1e-10)
        d["ADX"]=dx.ewm(alpha=1/14,adjust=False).mean()

        d["Rolling_High_50"]=h.rolling(50).max().shift(1)
        d["Rolling_Low_50"]=l.rolling(50).min().shift(1)
        d["BOS"]=(
            (c>d["Rolling_High_50"]) &
            (c.shift(1)<=d["Rolling_High_50"])
        ).astype(int)
        d["CHOCH"]=(
            (c<d["Rolling_Low_50"]) &
            (c.shift(1)>=d["Rolling_Low_50"])
        ).astype(int)
        d["FVG_Up"]=(
            (l>h.shift(2)) &
            (c.shift(1)>h.shift(2))
        ).astype(int)
        return d

# ==============================================================================
# 4 — VPVR / 4H / QUANT SCORE
# ==============================================================================
class SignalEngine:
@staticmethod
    def poc(df, bins=48, lookback=120):
        d=df.tail(lookback)
        if len(d)<30:
            return np.nan
        lo,hi=float(d.Low.min()),float(d.High.max())
        if hi<=lo:
            return float(d.Close.iloc[-1])
        typ=((d.High+d.Low+d.Close)/3).values
        vol=d.Volume.fillna(0).astype(float).values
        edges=np.linspace(lo,hi,bins+1)
        ix=np.clip(np.digitize(typ,edges)-1,0,bins-1)
        prof=np.bincount(ix,weights=vol,minlength=bins)
        k=int(np.argmax(prof))
        return float((edges[k]+edges[k+1])/2)

@staticmethod
    def mtf(df):
        try:
            h4=df.resample("4h").agg({
                "Open":"first","High":"max","Low":"min",
                "Close":"last","Volume":"sum"
            }).dropna()
            if len(h4)<55:
                return False,np.nan,np.nan
            e20=h4.Close.ewm(span=20,adjust=False).mean().iloc[-1]
            e50=h4.Close.ewm(span=50,adjust=False).mean().iloc[-1]
            return bool(e20>e50),float(e20),float(e50)
        except Exception:
            return False,np.nan,np.nan

@staticmethod
    def evaluate(data, xu, quotes):
        out=[]
        for symbol,raw in data.items():
            try:
                d=Indicators.calc(raw)
                if d is None: continue
                x=d.iloc[-1]
                price=float(quotes.get(symbol,0) or x.Close)
                adx=float(x.ADX)

                # HARD VETO — yatay piyasa
                if not np.isfinite(adx) or adx<20: continue

                e20,e50,e200=map(float,[x.EMA_20,x.EMA_50,x.EMA_200])
                if not (price>e20>e50>e200): continue

                # HARD VETO — 4H
                mtf,e20h,e50h=SignalEngine.mtf(d)
                if not mtf: continue

                rsi=float(x.RSI)
                macd=float(x.MACD_Hist)
                if rsi<50 or rsi>=78 or macd<=0: continue

                rvol=float(x.RVOL)
                if rvol<0.80: continue

                # Relative strength
                rs=0.0
                if xu is not None and not xu.empty and len(d)>=60:
                    bx=xu["Close"].reindex(d.index).ffill()
                    if len(bx)>=60:
                        rs=(price/float(d.Close.iloc[-60])-1) - (
                            float(bx.iloc[-1])/float(bx.iloc[-60])-1
                        )
                        if rs<0: continue

                obv_ok=float(x.OBV)>float(x.OBV_EMA)
                if not obv_ok and rvol<1.0: continue

                atr=float(x.ATR)
                if atr<=0 or not np.isfinite(atr): continue
                if (price-e20)/atr>3.0: continue

                poc=SignalEngine.poc(d)
                if np.isfinite(poc):
                    buf=max(price*0.003,atr*0.15)
                    if price<=poc+buf: continue

                stop=price-2*atr
                tp1=price+1.5*atr
                tp2=price+3*atr
                rr=(tp2-price)/(price-stop+1e-10)
                if rr<1.40: continue

                score=0.0
                score+=20
                score+=min(8,max(0,(adx-20)*0.8))
                score+=15
                score+=10 if 52<=rsi<=68 else (7 if rsi<74 else 3)
                score+=5
                score+=float(np.clip(8+rs*50,0,12))
                score+=7 if rvol>=1.2 else (5 if rvol>=1 else 2)
                score+=5 if obv_ok else 0
                score+=6 if int(x.BOS)==1 else 0
                score+=4 if int(x.FVG_Up)==1 else 0
                score+=5 if price>poc+0.5*atr else 3
                score+=3 if rr>=1.5 else 2
                score=float(np.clip(score,0,100))

                if score<76: continue

                quality="A+" if score>=88 else ("A" if score>=82 else "B+")
                out.append({
                    "symbol":symbol,"score":score,"quality":quality,
                    "price":price,"rsi":rsi,"rvol":rvol,"adx":adx,
                    "rs":rs,"poc":poc,"atr":atr,"tp1":tp1,"tp2":tp2,
                    "stop_loss":stop,"rr":rr,"mtf_ema20":e20h,
                    "mtf_ema50":e50h,"df":d
                })
            except Exception:
                continue
        out.sort(key=lambda z:(z["score"],z["rvol"],z["rs"]),reverse=True)
        return out

# ==============================================================================
# 5 — BACKTEST
# ==============================================================================
class Backtest:
@staticmethod
    def run(df, capital=100000.0, risk_pct=2.0):
        d=Indicators.calc(df)
        if d is None: return [],[],{}
        cash=capital
        shares=0
        entry=0.0
        curve=[]
        trades=[]

        for i in range(220,len(d)):
            x=d.iloc[i]
            price=float(x.Close)
            atr=float(x.ATR)
            if atr<=0: continue

            buy=(
                price>x.EMA_20>x.EMA_50>x.EMA_200 and
                x.ADX>=20 and 50<=x.RSI<75 and
                x.MACD_Hist>0 and x.RVOL>=1.0
            )
            sell=(
                price<x.EMA_20 or x.RSI<42 or
                price<entry-2*atr
            )

            if shares==0 and buy:
                budget=cash*(risk_pct/100)
                risk_share=2*atr
                shares=int(budget/risk_share) if risk_share>0 else 0
                shares=min(shares,int(cash*.98/price))
                if shares>0:
                    cash-=shares*price*1.000525
                    entry=price

            elif shares>0 and sell:
                exitv=shares*price*.999475
                pnl=exitv-shares*entry*1.000525
                cash+=exitv
                trades.append(pnl)
                shares=0

            curve.append(cash+shares*price)

        if not curve:
            return [],trades,{}

        eq=pd.Series(curve)
        ret=eq.pct_change().dropna()
        sharpe=float(ret.mean()/(ret.std()+1e-10)*np.sqrt(252))
        dd=(eq-eq.cummax())/(eq.cummax()+1e-10)
        mdd=float(dd.min()*100)

        wins=[p for p in trades if p>0]
        losses=[p for p in trades if p<=0]
        wr=100*len(wins)/len(trades) if trades else 0
        pf=sum(wins)/abs(sum(losses)) if losses and sum(losses)!=0 else (
            float("inf") if wins else 0
        )
        return curve,trades,{
            "sharpe":sharpe,"mdd":mdd,
            "win_rate":wr,"profit_factor":pf,
            "trades":len(trades)
        }

# ==============================================================================
# 6 — BIST EVRENİ
# ==============================================================================
# Yahoo Finance sembolleri. Liste geniş tutulmuştur; Yahoo'da bulunmayanlar
# otomatik olarak elenir.
BIST_UNIVERSE = [
"AEFES","AGHOL","AHGAZ","AKBNK","AKCNS","AKENR","AKFGY","AKFYE","AKSA",
"AKSEN","ALARK","ALBRK","ALFAS","ALGYO","ALKIM","ALTNY","ANELE","ARCLK",
"ARDYZ","ASELS","ASTOR","ASUZU","AYDEM","AYGAZ","BAGFS","BAHKM","BALSU",
"BANVT","BASGZ","BAYRK","BERA","BEYAZ","BFREN","BIGEN","BIMAS","BINHO",
"BIOEN","BIZIM","BJKAS","BLCYT","BMSCH","BMSTL","BNTAS","BORSK","BRISA",
"BRLSM","BRSAN","BTCIM","BUCIM","CANTE","CCOLA","CEMAS","CEMTS","CIMSA",
"CLEBI","CMBTN","COSMO","CVKMD","CWENE","DAPGM","DEVA","DOAS","DOHOL",
"DOAS","DSTKF","ECILC","ECZYT","EDATA","EGEEN","EGEPO","EGPRO","EGSER",
"EKGYO","EKOS","ENERY","ENJSA","ENKAI","EREGL","ESCAR","ESCOM","EUPWR",
"FENER","FROTO","GARAN","GENIL","GESAN","GLYHO","GOKNR","GOLTS","GOODY",
"GOZDE","GRSEL","GSDHO","GSRAY","GWIND","HALKB","HEKTS","HLGYO","HOROZ",
"ICBCT","IEYHO","INDES","INVEO","IPEKE","ISCTR","ISDMR","ISFIN","ISGYO",
"ISMEN","IZENR","IZMDC","JANTS","KARSN","KARTN","KCAER","KCHOL","KENT",
"KERVT","KLGYO","KMPUR","KONTR","KONYA","KORDS","KOTON","KOZAA","KOZAL",
"KRDMA","KRDMB","KRDMD","KRGYO","KTLEV","KUYAS","LIDER","LINK","LMKDC",
"LOGO","LYDHO","MACKO","MAGEN","MAKIM","MANAS","MAVI","MEGMT","MEDTR",
"MEPET","MERCN","MGROS","MIATK","MNDRS","MOBTL","MPARK","MRGYO","MTRKS",
"NETAS","NTGAZ","OBAMS","ODAS","ODINE","ONCSM","ORGE","OTKAR","OYAKC",
"OYAKO","OZKGY","PAGYO","PAPIL","PARSN","PASEU","PEKGY","PENTA","PETKM",
"PGSUS","PNLSN","POLHO","PRKAB","QUAGR","RALYH","REEDR","RGYAS","RYSAS",
"SAHOL","SANEL","SARKY","SASA","SDTTR","SEGYO","SELEC","SISE","SKBNK",
"SKTAS","SMART","SMRTG","SNGYO","SOKM","SUWEN","TABGD","TATEN","TATGD",
"TAVHL","TCELL","TEKTU","TEZOL","THYAO","TKFEN","TKNSA","TMSN","TOASO",
"TRCAS","TRGYO","TRILC","TSKB","TSPOR","TTKOM","TTRAK","TUKAS","TUPRS",
"TURSG","ULKER","ULUUN","USAK","VAKBN","VAKKO","VERUS","VESBE","VESTL",
"VKGYO","YAPRK","YATAS","YEOTK","YKBNK","YUNSA","ZOREN"
]
BIST_UNIVERSE = sorted(set(x + ".IS" for x in BIST_UNIVERSE))

# ==============================================================================
# 7 — MAIN
# ==============================================================================
def main():
    Database.init()

    st.markdown(
        '<h1 style="color:#38BDF8;font-weight:900;">⚡ QUANT MASTER v65.2 | HIGH PRECISION TERMINAL</h1>',
        unsafe_allow_html=True
    )
    st.caption(
        "Canlı fiyat + tüm BIST evreni + ADX veto + 4H MTF + VPVR/POC + "
        "RS + momentum + ATR risk yönetimi"
    )

    with st.sidebar:
        st.header("⚙️ Terminal Kontrol")
        years=st.slider("Günlük geçmiş veri (yıl)",1,5,3)
        risk=st.slider("İşlem başına risk (%)",1.0,5.0,2.0,.5)
        scan=st.button("🚀 TÜM BIST'İ TARA",use_container_width=True)
        back=st.button("📈 KCHOL Backtest",use_container_width=True)
        st.markdown("---")
        st.metric("Tarama Evreni",f"{len(BIST_UNIVERSE)} hisse")

        if st.button("🚨 Tüm Pozisyonları Kapat",use_container_width=True):
            pos=Database.positions()
            for _,p in pos.iterrows():
                px=get_live_price(p.symbol)
                if px<=0: px=float(p.entry_price)
                Database.close_position(p.symbol,px,"MANUAL_CLOSE")
            st.success("Pozisyonlar kapatıldı.")
            st.rerun()

    if scan:
        progress=st.progress(0)
        status=st.empty()

        with st.spinner("Tüm BIST verileri toplu indiriliyor..."):
            raw=download_batch(tuple(BIST_UNIVERSE),f"{years}y","1d")

        data={}
        for i,s in enumerate(BIST_UNIVERSE,1):
            d=normalize(raw,s)
            if not d.empty and len(d)>=220:
                data[s]=d
            progress.progress(i/len(BIST_UNIVERSE))

        status.info(f"Ön eleme: {len(data)} hisse.")

        # Canlı fiyatı koru: tüm evrenin son piyasa fiyatları toplu veriden;
        # nihai adaylar için fast_info ile gerçek son fiyat güncellenir.
        quotes=live_quotes_parallel(list(data.keys()),raw)

        xu=normalize(raw,"XU100.IS")
        if xu.empty:
            try:
                xu_raw=download_batch(("XU100.IS",),f"{years}y","1d")
                xu=normalize(xu_raw,"XU100.IS")
            except Exception:
                xu=None

        status.info("Yüksek hassasiyetli filtreler uygulanıyor...")
        signals=SignalEngine.evaluate(data,xu,quotes)

        # Nihai adaylar için canlı fiyatı gerçek quote ile güncelle.
        final_quotes={}
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures={ex.submit(get_live_price,s["symbol"]):s["symbol"] for s in signals[:40]}
            for f in as_completed(futures):
                sym=futures[f]
                try:
                    p=float(f.result())
                    if p>0: final_quotes[sym]=p
                except Exception:
                    pass

        for s in signals:
            if s["symbol"] in final_quotes:
                s["price"]=final_quotes[s["symbol"]]
                s["stop_loss"]=s["price"]-2*s["atr"]
                s["tp1"]=s["price"]+1.5*s["atr"]
                s["tp2"]=s["price"]+3*s["atr"]

        st.session_state["signals"]=signals
        progress.empty()
        status.success(
            f"Tarama tamamlandı — {len(data)} geçerli hisse işlendi, "
            f"{len(signals)} yüksek kaliteli aday bulundu."
        )

    left,right=st.columns([2.25,1])

    with left:
        st.subheader("🏆 Yüksek Hassasiyetli Sinyaller")
        signals=st.session_state.get("signals",[])

        if not signals:
            st.info("Sol menüden TÜM BIST'İ TARA butonuna basın.")
        else:
            for item in signals:
                q=item["quality"]
                badge="badge-aplus" if q=="A+" else ("badge-a" if q=="A" else "badge-b")
                st.markdown(f""" <div class="terminal-card"> <div style="display:flex;justify-content:space-between;align-items:center;"> <div> <h3 style="margin:0;color:#F8FAFC;">{item["symbol"]}</h3> <span class="live-ticker">Canlı Fiyat: {item["price"]:.2f} TL</span> | <span style="color:#94A3B8;">ADX: {item["adx"]:.1f}</span> | <span style="color:#94A3B8;">RSI: {item["rsi"]:.1f}</span> | <span style="color:#94A3B8;">RVOL: {item["rvol"]:.2f}x</span> </div> <div class="{badge}">SİNYAL {q} — {item["score"]:.1f}/100</div> </div> <hr style="border-color:#334155;margin:12px 0;"> <div style="display:flex;justify-content:space-between;font-size:.9rem;color:#CBD5E1;"> <div>📌 <b>POC:</b> {item["poc"]:.2f}</div> <div>🎯 <b>TP1:</b> <span style="color:#34D399;">{item["tp1"]:.2f}</span></div> <div>🎯 <b>TP2:</b> <span style="color:#10B981;">{item["tp2"]:.2f}</span></div> <div>🛑 <b>Stop:</b> <span style="color:#EF4444;">{item["stop_loss"]:.2f}</span></div> <div>⚖️ <b>R/R:</b> {item["rr"]:.2f}</div> </div> </div> """,unsafe_allow_html=True)

            top=signals[0]
            st.markdown("### 📥 En Güçlü Aday")
            if st.button(
                f"Paper Trade Aç: {top['symbol']} | {top['quality']} | {top['score']:.1f}",
                key="paper"
            ):
                cash=Database.cash()
                risk_budget=cash*risk/100
                per_share=2*top["atr"]
                shares=int(risk_budget/per_share) if per_share>0 else 0
                shares=min(shares,int(cash*.95/top["price"]))
                if shares<1:
                    st.warning("Pozisyon boyutu 1 lotun altında.")
                else:
                    ok,msg=Database.open_position(
                        top["symbol"],top["price"],shares,
                        top["stop_loss"],top["tp1"],top["tp2"],
                        top["score"],top["quality"]
                    )
                    (st.success if ok else st.error)(msg)
                    if ok: st.rerun()

    with right:
        st.subheader("💼 Paper Portfolio")
        pos=Database.positions()
        cash=Database.cash()
        market_value=0.0

        if pos.empty:
            st.info("Açık pozisyon yok.")
        else:
            for _,p in pos.iterrows():
                px=get_live_price(p.symbol)
                if px<=0: px=float(p.entry_price)
                val=p.shares*px
                market_value+=val
                pnl=(px-p.entry_price)*p.shares
                st.markdown(f""" <div class="terminal-card"> <b>{p.symbol}</b> — {p.shares} Lot<br> Canlı: <b>{px:.2f} TL</b><br> PnL: <span style="color:{'#34D399' if pnl>=0 else '#EF4444'};"> {pnl:+,.2f} TL</span><br> Stop: {p.stop_loss:.2f} | TP1: {p.tp1:.2f} </div> """,unsafe_allow_html=True)
                if st.button(f"Kapat: {p.symbol}",key=f"close_{p.symbol}"):
                    Database.close_position(p.symbol,px)
                    st.rerun()

        st.metric("Toplam NAV",f"{cash+market_value:,.2f} TL")
        st.metric("Nakit",f"{cash:,.2f} TL")

    if back:
        with st.spinner("Backtest çalışıyor..."):
            raw_bt=download_batch(("KCHOL.IS",),f"{years}y","1d")
            bt=normalize(raw_bt,"KCHOL.IS")
            curve,trades,m=Backtest.run(bt,100000,risk)
            if curve:
                st.subheader("📈 Backtest")
                a,b,c,d,e=st.columns(5)
                a.metric("Final NAV",f"{curve[-1]:,.0f} TL")
                b.metric("Sharpe",f"{m['sharpe']:.2f}")
                c.metric("MDD",f"{m['mdd']:.2f}%")
                d.metric("Win Rate",f"{m['win_rate']:.1f}%")
                e.metric("Profit Factor",f"{m['profit_factor']:.2f}")
                st.line_chart(pd.Series(curve))
                st.caption(f"Gerçekleşen işlem sayısı: {m['trades']}")

if __name__=="__main__":
    main()

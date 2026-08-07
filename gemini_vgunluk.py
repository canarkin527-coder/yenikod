# ==============================================================================
# BİST 100 QUANT TRADING ENGINE & REAL-TIME ANALYTICS DASHBOARD
# ==============================================================================
# Author: Advanced Quant Dev
# Architecture: Single-file Enterprise Streamlit Application
# Modules: Data Engine, Technicals, Quant Scoring, Risk Management, Paper Trading
# ==============================================================================

import os
import sys
import time
import math
import logging
import datetime
import warnings
from typing import Dict, List, Tuple, Optional, Union, Any

import requests
import numpy as np
import pandas as pd
import yfinance as yf
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

warnings.filterwarnings('ignore')

# Logging Yapılandırması
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("QuantEngine")


# ==============================================================================
# 1. TEMEL YAPILANDIRMA VE SABİTLER (CONSTANTS)
# ==============================================================================

APP_TITLE = "BİST 100 Pure Quant Engine & Institutional Screener"
APP_VERSION = "2.4.0-Enterprise"

DEFAULT_CASH = 100000.0
FETCH_TIMEOUT = 10
MAX_RETRIES = 3

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
]

BIST100_LIST = [
    "AEFES.IS", "AGHOL.IS", "AHGAZ.IS", "AKBNK.IS", "AKCNS.IS", "AKFGY.IS", "AKSA.IS", "AKSEN.IS", "ALARK.IS", "ALBRK.IS",
    "ALARK.IS", "ARCLK.IS", "ASELS.IS", "ASTOR.IS", "BERA.IS", "BIMAS.IS", "BRSAN.IS", "BRYAT.IS", "BUCIM.IS", "CANTE.IS",
    "CCOLA.IS", "CEMTS.IS", "CIMSA.IS", "CWENE.IS", "DOAS.IS", "DOHOL.IS", "ECILC.IS", "EGEEN.IS", "EKGYO.IS", "ENJSA.IS",
    "ENKAI.IS", "EREGL.IS", "EUPWR.IS", "FROTO.IS", "GARAN.IS", "GESAN.IS", "GUBRF.IS", "GWIND.IS", "HALKB.IS", "HEKTS.IS",
    "IMASM.IS", "INVEO.IS", "INVES.IS", "ISCTR.IS", "ISGYO.IS", "ISMEN.IS", "IZMDC.IS", "KARSN.IS", "KCAER.IS", "KCHOL.IS",
    "KMPUR.IS", "KONTR.IS", "KORDS.IS", "KOZAL.IS", "KOZAA.IS", "KRDMD.IS", "KZBGY.IS", "MAVI.IS", "MGROS.IS", "MIATK.IS",
    "ODAS.IS", "OTKAR.IS", "OYAKC.IS", "PENTAG.IS", "PETKM.IS", "PGASUS.IS", "PSGYO.IS", "REEDR.IS", "SAHOL.IS", "SASA.IS",
    "SDTTR.IS", "SISE.IS", "SKBNK.IS", "SMRTG.IS", "SOKM.IS", "TABGD.IS", "TAVHL.IS", "TCELL.IS", "THYAO.IS", "TKFEN.IS",
    "TOASO.IS", "TSKB.IS", "TTKOM.IS", "TTRAK.IS", "TUPRS.IS", "ULKER.IS", "VAKBN.IS", "VESBE.IS", "VESTL.IS", "YEOTK.IS",
    "YKBNK.IS", "YYLGD.IS", "ZOREN.IS"
]

SECTOR_MAP = {
    "THYAO": "Ulaştırma", "PGASUS": "Ulaştırma", "TAVHL": "Ulaştırma",
    "GARAN": "Bankacılık", "AKBNK": "Bankacılık", "ISCTR": "Bankacılık", "YKBNK": "Bankacılık", "VAKBN": "Bankacılık", "HALKB": "Bankacılık", "TSKB": "Bankacılık", "SKBNK": "Bankacılık",
    "KCHOL": "Holding", "SAHOL": "Holding", "DOHOL": "Holding", "ALARK": "Holding", "AGHOL": "Holding",
    "EREGL": "Metal Ana", "KRDMD": "Metal Ana", "BRSAN": "Metal Ana", "IZMDC": "Metal Ana",
    "SISE": "Cam & Seramik", "BIMAS": "Perakende", "MGROS": "Perakende", "SOKM": "Perakende",
    "TUPRS": "Kimya & Petrol", "PETKM": "Kimya & Petrol", "SASA": "Kimya & Petrol", "HEKTS": "Kimya & Petrol", "AKSA": "Kimya & Petrol",
    "ASELS": "Savunma", "SDTTR": "Savunma", "KONTR": "Teknoloji & Enerji", "ASTOR": "Enerji", "CWENE": "Enerji", "SMRTG": "Enerji", "YEOTK": "Enerji",
    "FROTO": "Otomotiv", "TOASO": "Otomotiv", "DOAS": "Otomotiv", "OTKAR": "Otomotiv", "TTRAK": "Otomotiv",
    "ENJSA": "Enerji", "AKSEN": "Enerji", "ODAS": "Enerji", "GWIND": "Enerji", "ZOREN": "Enerji", "CANTE": "Enerji",
    "CCOLA": "Gıda & İçecek", "ULKER": "Gıda & İçecek", "AEFES": "Gıda & İçecek", "YYLGD": "Gıda & İçecek",
    "ARCLK": "Dayanıklı Tüketim", "VESTL": "Dayanıklı Tüketim", "VESBE": "Dayanıklı Tüketim",
    "TCELL": "Telekom", "TTKOM": "Telekom",
    "EKGYO": "Gayrimenkul", "AKFGY": "Gayrimenkul", "ISGYO": "Gayrimenkul", "KZBGY": "Gayrimenkul",
    "OYAKC": "Çimento", "CIMSA": "Çimento", "AKCNS": "Çimento", "BUCIM": "Çimento",
    "MIATK": "Bilişim", "REEDR": "Bilişim", "PENTAG": "Bilişim"
}


# ==============================================================================
# 2. ÖZEL ÖRÜNTÜ VE YARDIMCI UTILS (HELPER FUNCTIONS)
# ==============================================================================

class ColorPalette:
    PRIMARY = "#0D6EFD"
    SUCCESS = "#198754"
    DANGER = "#DC3545"
    WARNING = "#FFC107"
    INFO = "#0D6EFD"
    BG_LIGHT = "#F8F9FA"
    CARD_BG = "#FFFFFF"
    TEXT_MAIN = "#212529"
    TEXT_MUTED = "#6C757D"
    BORDER = "#E9ECEF"


def get_random_user_agent() -> str:
    return USER_AGENTS[np.random.randint(0, len(USER_AGENTS))]


def format_currency(value: float, symbol: str = "TL") -> str:
    return f"{value:,.2f} {symbol}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_percent(value: float) -> str:
    prefix = "+" if value > 0 else ""
    return f"{prefix}{value:.2f}%"


# ==============================================================================
# 3. VERİ ÇEKME MOTORU (RESILIENT DATA ENGINE)
# ==============================================================================

class DataEngine:
    @staticmethod
    def create_session() -> requests.Session:
        session = requests.Session()
        session.headers.update({
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        })
        return session

    @classmethod
    def fetch_history(cls, symbol: str, period: str = "1y", interval: str = "1d") -> Optional[pd.DataFrame]:
        session = cls.create_session()
        ticker_str = symbol if symbol.endswith(".IS") else f"{symbol}.IS"
        
        for attempt in range(MAX_RETRIES):
            try:
                t = yf.Ticker(ticker_str, session=session)
                df = t.history(period=period, interval=interval)
                
                if df.empty:
                    df = yf.download(ticker_str, period=period, interval=interval, progress=False, ignore_tz=True)
                
                if not df.empty:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    
                    df = df.dropna(subset=['Close'])
                    if len(df) >= 10:
                        return df
            except Exception as e:
                logger.warning(f"Bağlantı hatası [{symbol}] Deneme {attempt+1}/{MAX_RETRIES}: {str(e)}")
                time.sleep(0.5)
                
        return None

    @classmethod
    def fetch_fundamental_ratios(cls, symbol: str) -> Dict[str, Any]:
        session = cls.create_session()
        ticker_str = symbol if symbol.endswith(".IS") else f"{symbol}.IS"
        default_ratios = {"FK": "N/A", "PD_DD": "N/A", "FD_FAVOK": "N/A", "Piyasa_Degeri": "N/A", "Bilanço_Para": "TRY"}
        
        try:
            t = yf.Ticker(ticker_str, session=session)
            info = t.info
            if info:
                default_ratios["FK"] = round(info.get("forwardPE", info.get("trailingPE", 0.0)), 2) or "N/A"
                default_ratios["PD_DD"] = round(info.get("priceToBook", 0.0), 2) or "N/A"
                default_ratios["FD_FAVOK"] = round(info.get("enterpriseToEbitda", 0.0), 2) or "N/A"
                m_cap = info.get("marketCap", 0)
                if m_cap:
                    default_ratios["Piyasa_Degeri"] = f"{m_cap / 1e9:.2f} Milyar TL"
        except Exception as e:
            logger.error(f"Temel rasyo hatası [{symbol}]: {str(e)}")
            
        return default_ratios


# ==============================================================================
# 4. TEKNİK ANALİZ İNDİKATÖR KÜTÜPHANESİ (QUANT MATH)
# ==============================================================================

class TechnicalIndicators:
    @staticmethod
    def SMA(series: pd.Series, window: int) -> pd.Series:
        return series.rolling(window=window).mean()

    @staticmethod
    def EMA(series: pd.Series, span: int) -> pd.Series:
        return series.ewm(span=span, adjust=False).mean()

    @staticmethod
    def RSI(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-9)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50.0)

    @staticmethod
    def MACD(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        fast_ema = TechnicalIndicators.EMA(series, fast)
        slow_ema = TechnicalIndicators.EMA(series, slow)
        macd_line = fast_ema - slow_ema
        signal_line = TechnicalIndicators.EMA(macd_line, signal)
        histogram = macd_line - signal_line
        return macd_line.fillna(0), signal_line.fillna(0), histogram.fillna(0)

    @staticmethod
    def BollingerBands(series: pd.Series, period: int = 20, std_dev: int = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
        middle = TechnicalIndicators.SMA(series, period)
        std = series.rolling(window=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        return upper, middle, lower

    @staticmethod
    def ATR(df: pd.DataFrame, period: int = 14) -> pd.Series:
        high_low = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift()).abs()
        low_close = (df['Low'] - df['Close'].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr.fillna(0)

    @staticmethod
    def StochasticOscillator(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> Tuple[pd.Series, pd.Series]:
        low_min = df['Low'].rolling(window=k_period).min()
        high_max = df['High'].rolling(window=k_period).max()
        k = 100 * ((df['Close'] - low_min) / (high_max - low_min + 1e-9))
        d = k.rolling(window=d_period).mean()
        return k.fillna(50), d.fillna(50)

    @staticmethod
    def SuperTrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> Tuple[pd.Series, pd.Series]:
        atr = TechnicalIndicators.ATR(df, period)
        hl2 = (df['High'] + df['Low']) / 2
        basic_upper = hl2 + (multiplier * atr)
        basic_lower = hl2 - (multiplier * atr)
        
        final_upper = pd.Series(0.0, index=df.index)
        final_lower = pd.Series(0.0, index=df.index)
        trend = pd.Series(1, index=df.index)

        for i in range(1, len(df)):
            if basic_upper.iloc[i] < final_upper.iloc[i-1] or df['Close'].iloc[i-1] > final_upper.iloc[i-1]:
                final_upper.iloc[i] = basic_upper.iloc[i]
            else:
                final_upper.iloc[i] = final_upper.iloc[i-1]

            if basic_lower.iloc[i] > final_lower.iloc[i-1] or df['Close'].iloc[i-1] < final_lower.iloc[i-1]:
                final_lower.iloc[i] = basic_lower.iloc[i]
            else:
                final_lower.iloc[i] = final_lower.iloc[i-1]

            if df['Close'].iloc[i] > final_upper.iloc[i-1]:
                trend.iloc[i] = 1
            elif df['Close'].iloc[i] < final_lower.iloc[i-1]:
                trend.iloc[i] = -1
            else:
                trend.iloc[i] = trend.iloc[i-1]

        st_line = np.where(trend == 1, final_lower, final_upper)
        return pd.Series(st_line, index=df.index), trend


# ==============================================================================
# 5. QUANT HESAPLAMA VE SİNYAL ÜRETİM MOTORU
# ==============================================================================

class QuantAnalyzer:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self._calculate_all()

    def _calculate_all(self):
        self.df['EMA10'] = TechnicalIndicators.EMA(self.df['Close'], 10)
        self.df['EMA20'] = TechnicalIndicators.EMA(self.df['Close'], 20)
        self.df['EMA50'] = TechnicalIndicators.EMA(self.df['Close'], 50)
        self.df['EMA200'] = TechnicalIndicators.EMA(self.df['Close'], 200)
        self.df['RSI'] = TechnicalIndicators.RSI(self.df['Close'], 14)
        self.df['MACD'], self.df['MACD_Signal'], self.df['MACD_Hist'] = TechnicalIndicators.MACD(self.df['Close'])
        self.df['UpperBB'], self.df['MidBB'], self.df['LowerBB'] = TechnicalIndicators.BollingerBands(self.df['Close'])
        self.df['ATR'] = TechnicalIndicators.ATR(self.df, 14)
        self.df['Stoch_K'], self.df['Stoch_D'] = TechnicalIndicators.StochasticOscillator(self.df)
        self.df['SuperTrend'], self.df['ST_Direction'] = TechnicalIndicators.SuperTrend(self.df)
        
        # Relative Volume (RVOL)
        vol_sma = TechnicalIndicators.SMA(self.df['Volume'], 20)
        self.df['RVOL'] = self.df['Volume'] / (vol_sma + 1e-9)

    def evaluate_quant_score(self) -> Dict[str, Any]:
        if len(self.df) < 20:
            return None

        curr = self.df.iloc[-1]
        prev = self.df.iloc[-2]
        
        score = 0
        details = []

        # 1. Trend Katmanı (Max 35 Puan)
        if curr['Close'] > curr['EMA20']:
            score += 10
            details.append("Fiyat > EMA20 (+10)")
        if curr['EMA20'] > curr['EMA50']:
            score += 10
            details.append("EMA20 > EMA50 (Altın Kesişim Yakın) (+10)")
        if curr['Close'] > curr['EMA200']:
            score += 10
            details.append("Makro Boğa Trendi (Fiyat > EMA200) (+10)")
        if curr['ST_Direction'] == 1:
            score += 5
            details.append("SuperTrend AL Pozisyonunda (+5)")

        # 2. Momentum & Osilatör Katmanı (Max 35 Puan)
        rsi = curr['RSI']
        if 40 <= rsi <= 60:
            score += 15
            details.append("RSI İdeal İvme Bölgesinde (40-60) (+15)")
        elif 30 <= rsi < 40:
            score += 10
            details.append("RSI Aşırı Satıma Yakın (+10)")
        elif rsi > 70:
            score -= 5
            details.append("RSI Aşırı Alımda (-5)")

        if curr['MACD'] > curr['MACD_Signal']:
            score += 10
            details.append("MACD Boğa Kesişimi (+10)")
        if curr['Stoch_K'] > curr['Stoch_D'] and curr['Stoch_K'] < 80:
            score += 10
            details.append("Stokastik Pozitif Sinyal (+10)")

        # 3. Hacim & Likidite Katmanı (Max 30 Puan)
        rvol = curr['RVOL']
        if rvol >= 2.0:
            score += 30
            details.append("Olağanüstü Hacim Patlaması (RVOL >= 2.0) (+30)")
        elif rvol >= 1.3:
            score += 20
            details.append("Güçlü Hacim Desteği (RVOL >= 1.3) (+20)")
        elif rvol >= 1.0:
            score += 10
            details.append("Ortalama Üstü Hacim (+10)")

        # Skor Sınıflandırma
        score = max(0, min(100, score))
        if score >= 75:
            signal = "🚀 GÜÇLÜ AL"
            color = ColorPalette.SUCCESS
        elif score >= 55:
            signal = "🟢 AL"
            color = ColorPalette.INFO
        elif score >= 40:
            signal = "👀 NÖTR / İZLE"
            color = ColorPalette.WARNING
        else:
            signal = "❌ SAT / UZAK DUR"
            color = ColorPalette.DANGER

        price_change = ((curr['Close'] - prev['Close']) / prev['Close']) * 100

        return {
            "score": score,
            "signal": signal,
            "color": color,
            "price": round(curr['Close'], 2),
            "change_pct": round(price_change, 2),
            "rsi": round(rsi, 1),
            "rvol": round(rvol, 2),
            "atr": round(curr['ATR'], 2),
            "macd_status": "POZİTİF" if curr['MACD'] > curr['MACD_Signal'] else "NEGATİF",
            "supertrend": "YUKARI" if curr['ST_Direction'] == 1 else "AŞAĞI",
            "details": details
        }


# ==============================================================================
# 6. STREAMLIT SESSION STATE MANAGEMENT
# ==============================================================================

def initialize_session_state():
    if 'cash' not in st.session_state:
        st.session_state.cash = DEFAULT_CASH
    if 'portfolio' not in st.session_state:
        st.session_state.portfolio = {}  # Format: {"THYAO": {"shares": 100, "avg_cost": 250.0}}
    if 'history' not in st.session_state:
        st.session_state.history = []
    if 'scan_data' not in st.session_state:
        st.session_state.scan_data = None
    if 'last_scan_time' not in st.session_state:
        st.session_state.last_scan_time = None


# ==============================================================================
# 7. ARAYÜZ BİLEŞENLERİ VE GÖRSELLEŞTİRME (DASHBOARD & CHARTS)
# ==============================================================================

def inject_custom_css():
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        html, body, [class*="css"] {{
            font-family: 'Inter', sans-serif;
            background-color: {ColorPalette.BG_LIGHT};
            color: {ColorPalette.TEXT_MAIN};
        }}
        .metric-card {{
            background-color: {ColorPalette.CARD_BG};
            border-radius: 10px;
            padding: 15px 20px;
            border: 1px solid {ColorPalette.BORDER};
            box-shadow: 0 2px 4px rgba(0,0,0,0.02);
            margin-bottom: 10px;
        }}
        .metric-title {{
            font-size: 13px;
            color: {ColorPalette.TEXT_MUTED};
            font-weight: 500;
        }}
        .metric-value {{
            font-size: 22px;
            font-weight: 700;
            color: {ColorPalette.TEXT_MAIN};
        }}
        .badge-success {{
            background-color: #D1E7DD;
            color: #0F5132;
            padding: 4px 8px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 12px;
        }}
        .badge-danger {{
            background-color: #F8D7DA;
            color: #842029;
            padding: 4px 8px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 12px;
        }}
        </style>
    """, unsafe_allow_html=True)


def plot_advanced_candlestick(df: pd.DataFrame, title: str) -> go.Figure:
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=(f'{title} Fiyat ve İndikatörler', 'Hacim ve RVOL', 'MACD & RSI')
    )

    # Mum Grafiği
    fig.add_trace(
        go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
            name='Fiyat',
            increasing_line_color='#198754', decreasing_line_color='#DC3545'
        ),
        row=1, col=1
    )

    # Hareketli Ortalamalar
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], mode='lines', name='EMA 20', line=dict(color='#0D6EFD', width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA50'], mode='lines', name='EMA 50', line=dict(color='#FFC107', width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA200'], mode='lines', name='EMA 200', line=dict(color='#6C757D', width=1.5)), row=1, col=1)

    # Hacim
    colors = ['#198754' if c >= o else '#DC3545' for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Hacim', marker_color=colors), row=2, col=1)

    # MACD
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], mode='lines', name='MACD', line=dict(color='#0D6EFD', width=1)), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD_Signal'], mode='lines', name='Sinyal', line=dict(color='#DC3545', width=1)), row=3, col=1)

    fig.update_layout(
        height=700,
        template='plotly_white',
        xaxis_rangeslider_visible=False,
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    return fig


# ==============================================================================
# 8. ANA UYGULAMA MANTIĞI VE SEKMELER (TAB CONTROLLERS)
# ==============================================================================

def render_sidebar():
    st.sidebar.title("⚡ Quant Kontrol Paneli")
    st.sidebar.markdown("---")
    
    st.sidebar.subheader("🎯 Taramayı Filtrele")
    min_score = st.sidebar.slider("Minimum Quant Skor", 0, 100, 40, step=5)
    min_rvol = st.sidebar.slider("Minimum Hacim Katı (RVOL)", 0.0, 5.0, 0.8, step=0.1)
    selected_sector = st.sidebar.selectbox("Sektör Seçimi", ["Tüm Sektörler"] + sorted(list(set(SECTOR_MAP.values()))))

    st.sidebar.markdown("---")
    st.sidebar.subheader("💼 Portföy Özeti")
    
    total_portfolio_val = st.session_state.cash
    portfolio_items = []
    
    for sym, details in st.session_state.portfolio.items():
        hist = DataEngine.fetch_history(sym, period="5d")
        if hist is not None and not hist.empty:
            c_price = hist['Close'].iloc[-1]
            val = c_price * details['shares']
            total_portfolio_val += val
            pnl = (c_price - details['avg_cost']) * details['shares']
            portfolio_items.append((sym, details['shares'], c_price, pnl))

    st.sidebar.metric("Toplam Varlık", format_currency(total_portfolio_val))
    st.sidebar.metric("Kullanılabilir Nakit", format_currency(st.session_state.cash))

    return min_score, min_rvol, selected_sector


def render_tab_radar(min_score: int, min_rvol: float, selected_sector: str):
    st.header("🔍 BİST 100 Canlı Algoritmik Quant Taraması")
    col_btn, col_info = st.columns([1, 3])

    if col_btn.button("🚀 Taramayı Başlat", use_container_width=True):
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()

        for idx, symbol in enumerate(BIST100_LIST):
            clean_sym = symbol.replace(".IS", "")
            status_text.text(f"Analiz Ediliyor ({idx+1}/{len(BIST100_LIST)}): {clean_sym}")

            df = DataEngine.fetch_history(symbol, period="1y")
            if df is not None:
                analyzer = QuantAnalyzer(df)
                q_res = analyzer.evaluate_quant_score()

                if q_res:
                    results.append({
                        "Hisse": clean_sym,
                        "Sektör": SECTOR_MAP.get(clean_sym, "Diğer"),
                        "Fiyat": q_res["price"],
                        "Günlük Değişim (%)": q_res["change_pct"],
                        "Quant Skor": q_res["score"],
                        "Sinyal": q_res["signal"],
                        "RSI": q_res["rsi"],
                        "RVOL": q_res["rvol"],
                        "MACD": q_res["macd_status"],
                        "SuperTrend": q_res["supertrend"],
                        "ATR": q_res["atr"]
                    })
            progress_bar.progress((idx + 1) / len(BIST100_LIST))

        status_text.empty()
        progress_bar.empty()

        st.session_state.scan_data = pd.DataFrame(results)
        st.session_state.last_scan_time = datetime.datetime.now().strftime("%H:%M:%S")

    if st.session_state.scan_data is not None and not st.session_state.scan_data.empty:
        st.caption(f"Son Güncelleme: {st.session_state.last_scan_time}")
        df_res = st.session_state.scan_data.copy()

        # Filtreleme İşlemleri
        df_filtered = df_res[
            (df_res["Quant Skor"] >= min_score) &
            (df_res["RVOL"] >= min_rvol)
        ]

        if selected_sector != "Tüm Sektörler":
            df_filtered = df_filtered[df_filtered["Sektör"] == selected_sector]

        # Metrikler
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Filtrelenen Hisse", len(df_filtered))
        c2.metric("Ortalama Skor", round(df_filtered["Quant Skor"].mean(), 1) if not df_filtered.empty else 0)
        c3.metric("Güçlü AL Sayısı", len(df_filtered[df_filtered["Quant Skor"] >= 75]))
        c4.metric("Yüksek Hacimliler (RVOL>1.5)", len(df_filtered[df_filtered["RVOL"] >= 1.5]))

        st.markdown("---")

        st.dataframe(
            df_filtered.sort_values(by="Quant Skor", ascending=False),
            column_config={
                "Quant Skor": st.column_config.ProgressColumn("Quant Skor", min_value=0, max_value=100, format="%d"),
                "Fiyat": st.column_config.NumberColumn(format="%.2f TL"),
                "Günlük Değişim (%)": st.column_config.NumberColumn(format="%+.2f %%"),
                "RVOL": st.column_config.NumberColumn(format="%.2fx"),
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Algoritmik taramayı başlatmak için yukarıdaki **'Taramayı Başlat'** butonuna basın.")


def render_tab_chart():
    st.header("📈 Teknik & Algoritmik Grafik Detayı")

    selected_symbol = st.selectbox("İncelenecek Hisseyi Seçin", [s.replace(".IS", "") for s in BIST100_LIST])
    
    col_chart, col_details = st.columns([3, 1])

    df = DataEngine.fetch_history(selected_symbol, period="1y")

    if df is not None and not df.empty:
        analyzer = QuantAnalyzer(df)
        q_res = analyzer.evaluate_quant_score()
        ratios = DataEngine.fetch_fundamental_ratios(selected_symbol)

        with col_chart:
            fig = plot_advanced_candlestick(analyzer.df, selected_symbol)
            st.plotly_chart(fig, use_container_width=True)

        with col_details:
            st.markdown(f"### {selected_symbol} Skorkart")
            st.metric("Quant Skor", f"{q_res['score']} / 100", delta=q_res['signal'])
            st.metric("Son Fiyat", f"{q_res['price']} TL", delta=f"{q_res['change_pct']}%")
            
            st.markdown("---")
            st.markdown("**Temel Rasyolar**")
            st.write(f"**F/K:** {ratios['FK']}")
            st.write(f"**PD/DD:** {ratios['PD_DD']}")
            st.write(f"**FD/FAVÖK:** {ratios['FD_FAVOK']}")
            st.write(f"**Piyasa Değeri:** {ratios['Piyasa_Degeri']}")

            st.markdown("---")
            st.markdown("**Sinyal Detayları**")
            for d in q_res["details"]:
                st.caption(f"• {d}")


def render_tab_portfolio():
    st.header("💸 Sanal Portföy ve Alım-Satım Simülasyonu")

    col_trade, col_view = st.columns([1, 2])

    with col_trade:
        st.subheader("Emir Girişi")
        trade_symbol = st.selectbox("Hisse", [s.replace(".IS", "") for s in BIST100_LIST], key="trade_sym")
        action = st.radio("İşlem Tipi", ["AL", "SAT"], horizontal=True)
        quantity = st.number_input("Adet", min_value=1, value=10, step=1)

        df_curr = DataEngine.fetch_history(trade_symbol, period="5d")
        if df_curr is not None and not df_curr.empty:
            curr_price = df_curr['Close'].iloc[-1]
            total_cost = curr_price * quantity
            st.write(f"Tahmini İşlem Tutarı: **{format_currency(total_cost)}**")
            st.caption(f"Birim Fiyat: {curr_price:.2f} TL")

            if st.button("Emri Onayla", use_container_width=True):
                if action == "AL":
                    if st.session_state.cash >= total_cost:
                        st.session_state.cash -= total_cost
                        if trade_symbol in st.session_state.portfolio:
                            existing = st.session_state.portfolio[trade_symbol]
                            new_shares = existing['shares'] + quantity
                            new_avg = ((existing['shares'] * existing['avg_cost']) + total_cost) / new_shares
                            st.session_state.portfolio[trade_symbol] = {'shares': new_shares, 'avg_cost': new_avg}
                        else:
                            st.session_state.portfolio[trade_symbol] = {'shares': quantity, 'avg_cost': curr_price}

                        st.session_state.history.append({
                            "Tarih": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "Hisse": trade_symbol,
                            "Tip": "AL",
                            "Adet": quantity,
                            "Fiyat": curr_price,
                            "Tutar": total_cost
                        })
                        st.success(f"{quantity} adet {trade_symbol} başarıyla alındı.")
                        st.rerun()
                    else:
                        st.error("Yetersiz Bakiye!")
                
                elif action == "SAT":
                    if trade_symbol in st.session_state.portfolio and st.session_state.portfolio[trade_symbol]['shares'] >= quantity:
                        st.session_state.cash += total_cost
                        st.session_state.portfolio[trade_symbol]['shares'] -= quantity

                        if st.session_state.portfolio[trade_symbol]['shares'] == 0:
                            del st.session_state.portfolio[trade_symbol]

                        st.session_state.history.append({
                            "Tarih": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "Hisse": trade_symbol,
                            "Tip": "SAT",
                            "Adet": quantity,
                            "Fiyat": curr_price,
                            "Tutar": total_cost
                        })
                        st.success(f"{quantity} adet {trade_symbol} başarıyla satıldı.")
                        st.rerun()
                    else:
                        st.error("Portföyünüzde yeterli hisse yok!")

    with col_view:
        st.subheader("Mevcut Pozisyonlar")
        
        portfolio_data = []
        for sym, data in st.session_state.portfolio.items():
            df_p = DataEngine.fetch_history(sym, period="5d")
            c_p = df_p['Close'].iloc[-1] if df_p is not None else data['avg_cost']
            mkt_val = c_p * data['shares']
            profit_loss = (c_p - data['avg_cost']) * data['shares']
            pnl_pct = ((c_p - data['avg_cost']) / data['avg_cost']) * 100

            portfolio_data.append({
                "Hisse": sym,
                "Adet": data['shares'],
                "Ort. Maliyet": data['avg_cost'],
                "Güncel Fiyat": c_p,
                "Toplam Değer": mkt_val,
                "Kar/Zarar (TL)": profit_loss,
                "Kar/Zarar (%)": pnl_pct
            })

        if portfolio_data:
            df_port = pd.DataFrame(portfolio_data)
            st.dataframe(
                df_port,
                column_config={
                    "Ort. Maliyet": st.column_config.NumberColumn(format="%.2f TL"),
                    "Güncel Fiyat": st.column_config.NumberColumn(format="%.2f TL"),
                    "Toplam Değer": st.column_config.NumberColumn(format="%.2f TL"),
                    "Kar/Zarar (TL)": st.column_config.NumberColumn(format="%+.2f TL"),
                    "Kar/Zarar (%)": st.column_config.NumberColumn(format="%+.2f %%"),
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Henüz açılmış bir pozisyonunuz bulunmuyor.")

        st.markdown("---")
        st.subheader("İşlem Geçmişi")
        if st.session_state.history:
            st.dataframe(pd.DataFrame(st.session_state.history), use_container_width=True, hide_index=True)


# ==============================================================================
# 9. ANA UYGULAMA GİRİŞ NOKTASI (MAIN ENTRYPOINT)
# ==============================================================================

def main():
    st.set_page_config(
        page_title="BİST 100 Quant Engine",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    inject_custom_css()
    initialize_session_state()

    min_score, min_rvol, selected_sector = render_sidebar()

    st.title(f"⚡ {APP_TITLE}")
    st.caption("Borsa İstanbul Algoritmik Analiz, Quant Taraması ve Portföy Yönetim Platformu")

    tab1, tab2, tab3 = st.tabs([
        "🔍 Canlı Quant Radar", 
        "📈 Grafik ve İndikatör Detayı", 
        "💸 Sanal Portföy"
    ])

    with tab1:
        render_tab_radar(min_score, min_rvol, selected_sector)

    with tab2:
        render_tab_chart()

    with tab3:
        render_tab_portfolio()


if __name__ == "__main__":
    main()

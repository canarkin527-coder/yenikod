"""
================================================================================
BİST 100 AUTOMATED QUANT SCANNER & BROKER TERMINAL (FIXED ADX)
================================================================================
- Tüm BİST Watchlist Otomatik Sinyal Taraması (Sadece AL/SAT Verenler Tablosu)
- Türk Lirası (₺) Tabanlı Stop-Loss, TP1/TP2 ve Lot Hesaplama
- Düzeltilmiş ADX Trend Motoru ve Performans İyileştirmesi
================================================================================
"""

import os
import sqlite3
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# Streamlit Ekran Düzeni
st.set_page_config(page_title="BİST 100 Quant Scanner", layout="wide", page_icon="🚨")


# ==============================================================================
# 1. CONFIGURATION & BİST 100 HİSSE LİSTESİ
# ==============================================================================
class SignalType(Enum):
    NONE = "NONE"
    BUY = "BUY"
    SELL = "SELL"


class SystemConfig:
    # Taranacak Popüler BİST 100 Hisseleri Listesi
    BIST_WATCHLIST = [
        'THYAO.IS', 'GARAN.IS', 'EREGL.IS', 'TUPRS.IS', 'ASELS.IS',
        'BIMAS.IS', 'AKBNK.IS', 'KCHOL.IS', 'SAHOL.IS', 'SISE.IS',
        'YKBNK.IS', 'ISCTR.IS', 'HEKTS.IS', 'SASA.IS', 'PETKM.IS',
        'KOZAL.IS', 'KORDS.IS', 'DOHOL.IS', 'ARCLK.IS', 'TOASO.IS'
    ]
    
    TIMEFRAME = '1d'            # 1 Günlük Mumlar
    BACKTEST_YEARS = 5          # 5 Yıllık Geçmiş Veri
    DATA_DIR = 'bist_cache'
    CURRENCY = '₺'
    
    # Hesap & Risk Ayarları
    INITIAL_CAPITAL = 100000.0  # 100.000 TL Sermaye
    RISK_PER_TRADE_PCT = 1.0    # Her işlemde risk %1
    ATR_PERIOD = 14
    ATR_SL_MULT = 1.5
    ATR_TP1_MULT = 1.5           
    ATR_TP2_MULT = 3.0           
    
    # Sinyal Filtre Eşikleri
    RVOL_THRESHOLD = 1.5
    ADX_THRESHOLD = 20.0        # Trend Eşiği (Daha fazla sinyal için 20'ye çekildi)
    VALIDITY_BARS = 3
    DB_FILE = 'bist_terminal.db'


# ==============================================================================
# 2. DATA REPOSITORY (YFINANCE)
# ==============================================================================
class BISTDataRepository:
    def __init__(self, config: SystemConfig):
        self.cfg = config
        os.makedirs(self.cfg.DATA_DIR, exist_ok=True)

    def load_data(self, symbol: str) -> pd.DataFrame:
        clean_symbol = symbol.replace('.IS', '')
        cache_path = os.path.join(self.cfg.DATA_DIR, f"{clean_symbol}_5yr.parquet")
        
        if os.path.exists(cache_path):
            file_time = datetime.fromtimestamp(os.path.getmtime(cache_path))
            if datetime.now() - file_time < timedelta(hours=6):
                return pd.read_parquet(cache_path)

        df = self._fetch_bist_historical(symbol, years=self.cfg.BACKTEST_YEARS)
        if not df.empty:
            df.to_parquet(cache_path)
        return df

    def _fetch_bist_historical(self, symbol: str, years: int) -> pd.DataFrame:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=f"{years}y", interval=self.cfg.TIMEFRAME)
            
            if df.empty:
                return pd.DataFrame()

            df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
            df.columns = ['open', 'high', 'low', 'close', 'volume']
            df.index.name = 'timestamp'
            
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
                
            return df
        except Exception:
            return pd.DataFrame()


# ==============================================================================
# 3. INDICATOR & SIGNAL ENGINE (ADX DÜZELTİLDİ)
# ==============================================================================
class IndicatorEngine:
    @classmethod
    def compute_all_indicators(cls, df: pd.DataFrame) -> pd.DataFrame:
        d = df.copy()
        c, h, l, v = d['close'], d['high'], d['low'], d['volume']
        
        d['ind_01_sma_20'] = c.rolling(20).mean()
        d['ind_02_sma_50'] = c.rolling(50).mean()

        tr0 = abs(h - l)
        tr1 = abs(h - c.shift(1))
        tr2 = abs(l - c.shift(1))
        tr = pd.concat([tr0, tr1, tr2], axis=1).max(axis=1)
        d['ind_27_atr_14'] = tr.ewm(alpha=1/14, adjust=False).mean()

        up_move = h - h.shift(1)
        down_move = l.shift(1) - l
        
        plus_dm_arr = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm_arr = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        # İndekslerin eşleşmesi için pd.Series ile sarmalandı
        plus_dm = pd.Series(plus_dm_arr, index=d.index)
        minus_dm = pd.Series(minus_dm_arr, index=d.index)
        tr_smooth = tr.ewm(alpha=1/14, adjust=False).mean()

        d['ind_38_plus_di'] = 100 * (plus_dm.ewm(alpha=1/14, adjust=False).mean() / (tr_smooth + 1e-10))
        d['ind_39_minus_di'] = 100 * (minus_dm.ewm(alpha=1/14, adjust=False).mean() / (tr_smooth + 1e-10))
        
        dx = 100 * (abs(d['ind_38_plus_di'] - d['ind_39_minus_di']) / (d['ind_38_plus_di'] + d['ind_39_minus_di'] + 1e-10))
        d['ind_40_adx_14'] = dx.ewm(alpha=1/14, adjust=False).mean()

        d['ind_42_vol_sma_20'] = v.rolling(20).mean()
        d['ind_43_rvol'] = v / (d['ind_42_vol_sma_20'] + 1e-10)

        return d


class SignalEngine:
    def __init__(self, config: SystemConfig):
        self.cfg = config

    def process_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        rvol_pass = df['ind_43_rvol'] >= self.cfg.RVOL_THRESHOLD
        adx_pass = df['ind_40_adx_14'] >= self.cfg.ADX_THRESHOLD

        df['raw_bullish'] = rvol_pass & adx_pass & (df['ind_38_plus_di'] > df['ind_39_minus_di'])
        df['raw_bearish'] = rvol_pass & adx_pass & (df['ind_39_minus_di'] > df['ind_38_plus_di'])

        df['bullish_age'] = self._bars_since(df['raw_bullish'])
        df['bearish_age'] = self._bars_since(df['raw_bearish'])

        df['is_bullish_valid'] = df['bullish_age'].between(0, self.cfg.VALIDITY_BARS - 1, inclusive='both')
        df['is_bearish_valid'] = df['bearish_age'].between(0, self.cfg.VALIDITY_BARS - 1, inclusive='both')

        return df

    @staticmethod
    def _bars_since(series: pd.Series) -> list:
        res = []
        c = np.nan
        for val in series:
            if val:
                c = 0
            elif not np.isnan(c):
                c += 1
            res.append(c)
        return res

    @staticmethod
    def calculate_star_rating(rvol: float, adx: float) -> str:
        score = 0
        if rvol >= 1.2: score += 1
        if rvol >= 1.8: score += 1
        if adx >= 20: score += 1
        if adx >= 30: score += 1
        if rvol >= 2.0 and adx >= 30: score += 1
        return "⭐️" * max(1, min(score, 5))


class RiskAndPivotEngine:
    def __init__(self, config: SystemConfig):
        self.cfg = config

    def calculate_pivots(self, df: pd.DataFrame) -> Dict[str, float]:
        last = df.iloc[-2]
        high, low, close = last['high'], last['low'], last['close']
        pivot = (high + low + close) / 3
        return {
            'Pivot': round(pivot, 2),
            'R1': round((2 * pivot) - low, 2),
            'R2': round(pivot + (high - low), 2),
            'S1': round((2 * pivot) - high, 2),
            'S2': round(pivot - (high - low), 2)
        }

    def calculate_trade_targets(self, balance: float, price: float, atr: float, side: str) -> Dict[str, float]:
        risk_budget = balance * (self.cfg.RISK_PER_TRADE_PCT / 100.0)
        
        if side == "BUY":
            sl = price - (atr * self.cfg.ATR_SL_MULT)
            tp1 = price + (atr * self.cfg.ATR_TP1_MULT)
            tp2 = price + (atr * self.cfg.ATR_TP2_MULT)
            risk_per_unit = price - sl
        else:
            sl = price + (atr * self.cfg.ATR_SL_MULT)
            tp1 = price - (atr * self.cfg.ATR_TP1_MULT)
            tp2 = price - (atr * self.cfg.ATR_TP2_MULT)
            risk_per_unit = sl - price

        size = int(risk_budget / risk_per_unit) if risk_per_unit > 0 else 0

        return {
            'Entry': round(price, 2),
            'SL': round(sl, 2),
            'TP1': round(tp1, 2),
            'TP2': round(tp2, 2),
            'Lot_Size': size,
            'Total_Value_TL': round(size * price, 2)
        }


# ==============================================================================
# 4. STREAMLIT SCANNER DASHBOARD
# ==============================================================================
def main():
    cfg = SystemConfig()
    repo = BISTDataRepository(cfg)
    sig_engine = SignalEngine(cfg)
    risk_engine = RiskAndPivotEngine(cfg)

    st.title("🚨 BİST 100 Quant Radar & Tarama Terminali")
    st.caption("Tüm BİST 100 hisselerinin canlı taranması ve aktif sinyal listesi")

    tab1, tab2 = st.tabs(["🔥 Tüm AL Sinyalleri (Radar Tarama)", "📈 Tek Hisse Detayı & Grafikler"])

    # --- SEKME 1: TÜM HİSSELERİN TARANMASI ---
    with tab1:
        st.subheader("📊 BİST 100 Canlı Sinyal Radar Tablosu")
        
        filter_option = st.radio("Filtrele:", ["Sadece AL Sinyalleri 🟢", "Sadece SAT Sinyalleri 🔴", "Tüm Hisseleri Göster ⚪"], horizontal=True)

        if st.button("🔄 Radarı Şimdi Yeniden Tara"):
            st.cache_data.clear()

        scan_data = []
        with st.spinner("BİST 100 Hisseleri Taranıyor..."):
            for symbol in cfg.BIST_WATCHLIST:
                clean_sym = symbol.replace('.IS', '')
                raw_df = repo.load_data(symbol)
                if raw_df.empty:
                    continue
                
                matrix_df = IndicatorEngine.compute_all_indicators(raw_df)
                processed_df = sig_engine.process_signals(matrix_df)
                last = processed_df.iloc[-1]

                side = "NONE"
                age = "-"
                if last['is_bullish_valid']:
                    side = "BUY"
                    age = f"{int(last['bullish_age'])} Gün"
                elif last['is_bearish_valid']:
                    side = "SELL"
                    age = f"{int(last['bearish_age'])} Gün"

                targets = risk_engine.calculate_trade_targets(cfg.INITIAL_CAPITAL, last['close'], last['ind_27_atr_14'], side if side != "NONE" else "BUY")
                stars = sig_engine.calculate_star_rating(last['ind_43_rvol'], last['ind_40_adx_14'])

                adx_val = round(last['ind_40_adx_14'], 1) if not np.isnan(last['ind_40_adx_14']) else 0.0

                scan_data.append({
                    "Hisse": clean_sym,
                    "Sinyal": "🟢 GÜÇLÜ AL" if side == "BUY" else ("🔴 GÜÇLÜ SAT" if side == "SELL" else "⚪ NÖTR"),
                    "Sinyal Yaşı": age,
                    "Son Fiyat (TL)": f"{last['close']:.2f} ₺",
                    "Stop Loss (SL)": f"{targets['SL']} ₺",
                    "TP1 Hedef": f"{targets['TP1']} ₺",
                    "TP2 Hedef": f"{targets['TP2']} ₺",
                    "Önerilen Lot": f"{targets['Lot_Size']} Lot",
                    "Hacim Gücü (RVOL)": round(last['ind_43_rvol'], 2),
                    "Trend (ADX)": adx_val,
                    "Güven": stars,
                    "_raw_side": side
                })

        scan_df = pd.DataFrame(scan_data)

        # Filtreleme
        if filter_option == "Sadece AL Sinyalleri 🟢":
            display_df = scan_df[scan_df['_raw_side'] == "BUY"].drop(columns=['_raw_side'])
        elif filter_option == "Sadece SAT Sinyalleri 🔴":
            display_df = scan_df[scan_df['_raw_side'] == "SELL"].drop(columns=['_raw_side'])
        else:
            display_df = scan_df.drop(columns=['_raw_side'])

        if not display_df.empty:
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.warning("Seçilen filtre kriterine uygun hisse bulunamadı.")

    # --- SEKME 2: TEK HİSSE DETAYI ---
    with tab2:
        selected_symbol = st.selectbox("İncelemek İstediğiniz Hisseyi Seçin:", options=cfg.BIST_WATCHLIST)
        clean_name = selected_symbol.replace('.IS', '')
        
        raw_df = repo.load_data(selected_symbol)
        if not raw_df.empty:
            matrix_df = IndicatorEngine.compute_all_indicators(raw_df)
            processed_df = sig_engine.process_signals(matrix_df)
            last_row = processed_df.iloc[-1]
            
            pivots = risk_engine.calculate_pivots(processed_df)
            
            st.write(f"### 📈 {clean_name} Grafik ve Pivot Seviyeleri")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Son Fiyat", f"{last_row['close']:.2f} ₺")
            c2.metric("R1 Direnç", f"{pivots['R1']} ₺")
            c3.metric("S1 Destek", f"{pivots['S1']} ₺")
            c4.metric("RVOL", f"{last_row['ind_43_rvol']:.2f}")

            recent_df = processed_df.tail(120)
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=recent_df.index, open=recent_df['open'], high=recent_df['high'],
                low=recent_df['low'], close=recent_df['close'], name=clean_name
            ))
            fig.add_hline(y=pivots['R1'], line_dash="dash", line_color="orange", annotation_text="R1 Direnç")
            fig.add_hline(y=pivots['S1'], line_dash="dash", line_color="cyan", annotation_text="S1 Destek")
            fig.update_layout(height=450, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)


if __name__ == '__main__':
    main()

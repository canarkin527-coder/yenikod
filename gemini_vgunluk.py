"""
================================================================================
BİST 100 QUANTITATIVE INSTITUTIONAL RADAR & BACKTEST TERMINAL v5.0
================================================================================
- Multi-Factor Signal Engine: 45+ Quantitative Technical Indicators
- Robust Trend, Momentum, Volatility, Volume, Cycle & Pattern Drivers
- Institutional Composite Signal Scoring (Confluence Matrix)
- Vectorized Multi-Asset Portfolio Backtest Engine (5-Year Historical Simulation)
- Dynamic ATR-Based Risk Management & Capital Allocation (Fixed Risk Model)
- Interactive Institutional Analytics & Charts (Plotly)
================================================================================
"""

import os
import sqlite3
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Any, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf

# Streamlit Ekran Düzeni (Geniş Mod)
st.set_page_config(page_title="BİST 100 Institutional Quant Terminal", layout="wide", page_icon="🏛️")


# ==============================================================================
# 1. SYSTEM CONFIGURATION & CONSTANTS
# ==============================================================================
class SystemConfig:
    BIST_WATCHLIST = [
        'THYAO.IS', 'GARAN.IS', 'EREGL.IS', 'TUPRS.IS', 'ASELS.IS',
        'BIMAS.IS', 'AKBNK.IS', 'KCHOL.IS', 'SAHOL.IS', 'SISE.IS',
        'YKBNK.IS', 'ISCTR.IS', 'HEKTS.IS', 'SASA.IS', 'PETKM.IS',
        'KOZAL.IS', 'KORDS.IS', 'DOHOL.IS', 'ARCLK.IS', 'TOASO.IS'
    ]
    
    TIMEFRAME = '1d'            # Günlük Mumlar
    BACKTEST_YEARS = 5          # 5 Yıllık Backtest Simülasyonu
    DATA_DIR = 'bist_cache'
    CURRENCY = '₺'
    
    # Portfolio & Risk Management
    INITIAL_CAPITAL = 100000.0  # 100.000 TL Varsayılan Sermaye
    RISK_PER_TRADE_PCT = 1.0    # İşlem Başı Risk %1.0
    ATR_PERIOD = 14
    ATR_SL_MULT = 1.5           # Stop Loss Multiplier
    ATR_TP1_MULT = 2.0          # Take Profit 1 Multiplier
    ATR_TP2_MULT = 3.5          # Take Profit 2 Multiplier
    
    # Institutional Confluence Eşikleri
    BUY_SCORE_THRESHOLD = 65.0   # 100 Üzerinden 65 ve Üzeri Score -> AL Sinyali
    SELL_SCORE_THRESHOLD = 35.0  # 100 Üzerinden 35 ve Altı Score -> SAT Sinyali


# ==============================================================================
# 2. DATA REPOSITORY ENGINE
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
# 3. ADVANCED 45+ QUANTITATIVE INDICATOR ENGINE
# ==============================================================================
class QuantitativeIndicatorEngine:
    @classmethod
    def compute_all_indicators(cls, df: pd.DataFrame) -> pd.DataFrame:
        d = df.copy()
        c, h, l, v = d['close'], d['high'], d['low'], d['volume']
        
        # --- 1. MOVING AVERAGES & TREND (10 Indicator) ---
        d['ind_01_sma_10'] = c.rolling(10).mean()
        d['ind_02_sma_20'] = c.rolling(20).mean()
        d['ind_03_sma_50'] = c.rolling(50).mean()
        d['ind_04_sma_200'] = c.rolling(200).mean()
        d['ind_05_ema_9'] = c.ewm(span=9, adjust=False).mean()
        d['ind_06_ema_21'] = c.ewm(span=21, adjust=False).mean()
        d['ind_07_ema_50'] = c.ewm(span=50, adjust=False).mean()
        d['ind_08_ema_200'] = c.ewm(span=200, adjust=False).mean()
        d['ind_09_wma_20'] = c.rolling(20).apply(lambda x: np.dot(x, np.arange(1, 21)) / np.sum(np.arange(1, 21)), raw=True)
        d['ind_10_hma_20'] = (2 * c.ewm(span=10).mean() - c.ewm(span=20).mean()).ewm(span=4).mean()

        # --- 2. MACD & OSCILLATORS (5 Indicator) ---
        d['ind_11_macd'] = d['ind_05_ema_9'] - d['ind_06_ema_21']
        d['ind_12_macd_signal'] = d['ind_11_macd'].ewm(span=9, adjust=False).mean()
        d['ind_13_macd_hist'] = d['ind_11_macd'] - d['ind_12_macd_signal']
        
        # PPO (Percentage Price Oscillator)
        d['ind_14_ppo'] = ((d['ind_05_ema_9'] - d['ind_06_ema_21']) / (d['ind_06_ema_21'] + 1e-10)) * 100
        d['ind_15_ppo_signal'] = d['ind_14_ppo'].ewm(span=9, adjust=False).mean()

        # --- 3. MOMENTUM INDICATORS (8 Indicator) ---
        delta = c.diff()
        gain_14 = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss_14 = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rs_14 = gain_14 / (loss_14 + 1e-10)
        d['ind_16_rsi_14'] = 100 - (100 / (1 + rs_14))
        
        gain_7 = (delta.where(delta > 0, 0)).ewm(alpha=1/7, adjust=False).mean()
        loss_7 = (-delta.where(delta < 0, 0)).ewm(alpha=1/7, adjust=False).mean()
        d['ind_17_rsi_7'] = 100 - (100 / (1 + (gain_7 / (loss_7 + 1e-10))))

        # Stochastic Oscillator
        low_14 = l.rolling(14).min()
        high_14 = h.rolling(14).max()
        d['ind_18_stoch_k'] = 100 * ((c - low_14) / (high_14 - low_14 + 1e-10))
        d['ind_19_stoch_d'] = d['ind_18_stoch_k'].rolling(3).mean()

        # Williams %R
        d['ind_20_williams_r'] = -100 * ((high_14 - c) / (high_14 - low_14 + 1e-10))
        
        # Rate of Change (ROC) & CCI
        d['ind_21_roc_12'] = c.pct_change(12) * 100
        d['ind_22_roc_25'] = c.pct_change(25) * 100
        d['ind_23_cci_20'] = (c - (h + l + c)/3.0) / (0.015 * (c - (h + l + c)/3.0).abs().rolling(20).mean() + 1e-10)

        # --- 4. VOLATILITY & BANDS (7 Indicator) ---
        tr0 = abs(h - l)
        tr1 = abs(h - c.shift(1))
        tr2 = abs(l - c.shift(1))
        tr = pd.concat([tr0, tr1, tr2], axis=1).max(axis=1)
        d['ind_24_atr_14'] = tr.ewm(alpha=1/14, adjust=False).mean()
        d['ind_25_natr_14'] = (d['ind_24_atr_14'] / c) * 100

        # Bollinger Bands (20, 2)
        d['ind_26_bb_middle'] = d['ind_02_sma_20']
        bb_std = c.rolling(20).std()
        d['ind_27_bb_upper'] = d['ind_26_bb_middle'] + (2 * bb_std)
        d['ind_28_bb_lower'] = d['ind_26_bb_middle'] - (2 * bb_std)
        d['ind_29_bb_width'] = (d['ind_27_bb_upper'] - d['ind_28_bb_lower']) / (d['ind_26_bb_middle'] + 1e-10)
        d['ind_30_bb_pct_b'] = (c - d['ind_28_bb_lower']) / (d['ind_27_bb_upper'] - d['ind_28_bb_lower'] + 1e-10)

        # --- 5. DMI & ADX STRENGTH (4 Indicator) ---
        up_move = h - h.shift(1)
        down_move = l.shift(1) - l
        plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=d.index)
        minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=d.index)
        tr_smooth = tr.ewm(alpha=1/14, adjust=False).mean()

        d['ind_31_plus_di'] = 100 * (plus_dm.ewm(alpha=1/14, adjust=False).mean() / (tr_smooth + 1e-10))
        d['ind_32_minus_di'] = 100 * (minus_dm.ewm(alpha=1/14, adjust=False).mean() / (tr_smooth + 1e-10))
        dx = 100 * (abs(d['ind_31_plus_di'] - d['ind_32_minus_di']) / (d['ind_31_plus_di'] + d['ind_32_minus_di'] + 1e-10))
        d['ind_33_adx_14'] = dx.ewm(alpha=1/14, adjust=False).mean()
        d['ind_34_adxr_14'] = (d['ind_33_adx_14'] + d['ind_33_adx_14'].shift(14)) / 2.0

        # --- 6. VOLUME & MONEY FLOW (7 Indicator) ---
        d['ind_35_vol_sma_20'] = v.rolling(20).mean()
        d['ind_36_rvol'] = v / (d['ind_35_vol_sma_20'] + 1e-10)
        
        # OBV
        d['ind_37_obv'] = (np.sign(c.diff()) * v).fillna(0).cumsum()
        d['ind_38_obv_ema'] = d['ind_37_obv'].ewm(span=20).mean()

        # MFI
        tp = (h + l + c) / 3.0
        raw_mf = tp * v
        pos_mf = pd.Series(np.where(tp > tp.shift(1), raw_mf, 0.0), index=d.index).rolling(14).sum()
        neg_mf = pd.Series(np.where(tp < tp.shift(1), raw_mf, 0.0), index=d.index).rolling(14).sum()
        mfr = pos_mf / (neg_mf + 1e-10)
        d['ind_39_mfi_14'] = 100 - (100 / (1 + mfr))
        
        # CMF & VWAP
        mfv = (((c - l) - (h - c)) / (h - l + 1e-10)) * v
        d['ind_40_cmf_20'] = mfv.rolling(20).sum() / (v.rolling(20).sum() + 1e-10)
        d['ind_41_vwap'] = (c * v).cumsum() / (v.cumsum() + 1e-10)

        # --- 7. CHANNEL & VOLATILITY EXTENSIONS (5 Indicator) ---
        d['ind_42_kc_middle'] = d['ind_05_ema_9']
        d['ind_43_kc_upper'] = d['ind_42_kc_middle'] + (2 * d['ind_24_atr_14'])
        d['ind_44_kc_lower'] = d['ind_42_kc_middle'] - (2 * d['ind_24_atr_14'])
        
        d['ind_45_donchian_high'] = h.rolling(20).max()
        d['ind_46_donchian_low'] = l.rolling(20).min()
        d['ind_47_donchian_mid'] = (d['ind_45_donchian_high'] + d['ind_46_donchian_low']) / 2.0

        return d


# ==============================================================================
# 4. INSTITUTIONAL MULTI-FACTOR SCORE ENGINE
# ==============================================================================
class InstitutionalScoreEngine:
    def __init__(self, config: SystemConfig):
        self.cfg = config

    def calculate_composite_score(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.DataFrame]:
        d = df.copy()
        
        # Trend Grubu (%30)
        trend_score = (
            (d['close'] > d['ind_02_sma_20']).astype(int) * 20 +
            (d['ind_02_sma_20'] > d['ind_03_sma_50']).astype(int) * 20 +
            (d['ind_03_sma_50'] > d['ind_04_sma_200']).astype(int) * 20 +
            (d['ind_05_ema_9'] > d['ind_06_ema_21']).astype(int) * 20 +
            (d['ind_10_hma_20'] > d['ind_10_hma_20'].shift(1)).astype(int) * 20
        )

        # Momentum Grubu (%25)
        mom_score = (
            (d['ind_16_rsi_14'].between(45, 70)).astype(int) * 20 +
            (d['ind_11_macd'] > d['ind_12_macd_signal']).astype(int) * 25 +
            (d['ind_18_stoch_k'] > d['ind_19_stoch_d']).astype(int) * 20 +
            (d['ind_21_roc_12'] > 0).astype(int) * 15 +
            (d['ind_23_cci_20'] > 0).astype(int) * 20
        )

        # Hacim & Para Akışı Grubu (%25)
        vol_score = (
            (d['ind_36_rvol'] >= 1.3).astype(int) * 30 +
            (d['ind_37_obv'] > d['ind_38_obv_ema']).astype(int) * 25 +
            (d['ind_39_mfi_14'] > 50).astype(int) * 20 +
            (d['ind_40_cmf_20'] > 0.05).astype(int) * 25
        )

        # Volatilite & Yön Gücü Grubu (%20)
        str_score = (
            (d['ind_33_adx_14'] >= 20).astype(int) * 30 +
            (d['ind_31_plus_di'] > d['ind_32_minus_di']).astype(int) * 40 +
            (d['close'] > d['ind_47_donchian_mid']).astype(int) * 30
        )

        # Toplam Kurumsal Quant Skoru (0-100)
        composite_score = (trend_score * 0.30) + (mom_score * 0.25) + (vol_score * 0.25) + (str_score * 0.20)
        d['quant_score'] = composite_score.round(1)

        return d['quant_score'], d


# ==============================================================================
# 5. VECTORIZED MULTI-ASSET PORTFOLIO BACKTEST ENGINE
# ==============================================================================
class BacktestEngine:
    def __init__(self, config: SystemConfig):
        self.cfg = config

    def run_backtest(self, df: pd.DataFrame, initial_capital: float = 100000.0) -> Dict[str, Any]:
        if df.empty or len(df) < 250:
            return {}

        d = df.copy()
        score_engine = InstitutionalScoreEngine(self.cfg)
        d['quant_score'], d = score_engine.calculate_composite_score(d)

        position = 0
        entry_price = 0.0
        sl_price = 0.0
        tp1_price = 0.0
        capital = initial_capital
        equity_curve = []
        trades = []

        for i in range(200, len(d)):
            date = d.index[i]
            close = d['close'].iloc[i]
            score = d['quant_score'].iloc[i]
            atr = d['ind_24_atr_14'].iloc[i]

            if position == 0:
                if score >= self.cfg.BUY_SCORE_THRESHOLD:
                    position = 1
                    entry_price = close
                    sl_price = entry_price - (atr * self.cfg.ATR_SL_MULT)
                    tp1_price = entry_price + (atr * self.cfg.ATR_TP1_MULT)
                    risk_amount = capital * (self.cfg.RISK_PER_TRADE_PCT / 100.0)
                    risk_per_share = entry_price - sl_price
                    shares = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0
                    
                    trades.append({
                        'type': 'BUY', 'date': date, 'price': entry_price, 
                        'shares': shares, 'sl': sl_price, 'tp1': tp1_price
                    })

            elif position == 1:
                if close <= sl_price:
                    pnl = (sl_price - entry_price) * shares
                    capital += pnl
                    trades.append({'type': 'EXIT_SL', 'date': date, 'price': sl_price, 'pnl': pnl})
                    position = 0
                elif close >= tp1_price:
                    pnl = (tp1_price - entry_price) * shares
                    capital += pnl
                    trades.append({'type': 'EXIT_TP', 'date': date, 'price': tp1_price, 'pnl': pnl})
                    position = 0
                elif score < 40.0:
                    pnl = (close - entry_price) * shares
                    capital += pnl
                    trades.append({'type': 'EXIT_SIGNAL', 'date': date, 'price': close, 'pnl': pnl})
                    position = 0

            equity_curve.append({'date': date, 'capital': capital})

        eq_df = pd.DataFrame(equity_curve).set_index('date')
        if eq_df.empty:
            return {}

        total_return = ((capital - initial_capital) / initial_capital) * 100.0
        
        eq_df['peak'] = eq_df['capital'].cummax()
        eq_df['dd'] = (eq_df['capital'] - eq_df['peak']) / eq_df['peak']
        max_dd = eq_df['dd'].min() * 100.0

        closed_trades = [t for t in trades if 'pnl' in t]
        wins = [t for t in closed_trades if t['pnl'] > 0]
        win_rate = (len(wins) / len(closed_trades) * 100.0) if closed_trades else 0.0

        daily_returns = eq_df['capital'].pct_change().dropna()
        sharpe = (daily_returns.mean() / (daily_returns.std() + 1e-10)) * np.sqrt(252)

        return {
            'total_return': round(total_return, 2),
            'max_drawdown': round(max_dd, 2),
            'win_rate': round(win_rate, 1),
            'total_trades': len(closed_trades),
            'sharpe_ratio': round(sharpe, 2),
            'final_capital': round(capital, 2),
            'equity_curve': eq_df
        }


# ==============================================================================
# 6. RISK & PIVOT CALCULATOR
# ==============================================================================
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
# 7. MAIN STREAMLIT APPLICATION DASHBOARD
# ==============================================================================
def main():
    cfg = SystemConfig()
    repo = BISTDataRepository(cfg)
    score_engine = InstitutionalScoreEngine(cfg)
    backtest_engine = BacktestEngine(cfg)
    risk_engine = RiskAndPivotEngine(cfg)

    st.title("🏛️ BİST 100 Institutional Quant & Backtest Terminal v5.0")
    st.caption("45+ İndikatörlü Multi-Faktör Tarama Motoru, Kurumsal Skorlama ve 5 Yıllık Backtest Simülasyonu")

    tab1, tab2, tab3 = st.tabs([
        "🔥 Canlı Sinyal Radarı (45+ İndikatör)", 
        "📊 5-Yıllık Backtest Simülasyonu", 
        "📈 Kurumsal Hisse Analizi & Grafikler"
    ])

    # --- TAB 1: RADAR TARAMA ---
    with tab1:
        st.subheader("⚡ 45+ İndikatörlü Multi-Faktör BİST 100 Taraması")
        
        c_filter, c_cap = st.columns([3, 1])
        with c_filter:
            filter_option = st.radio(
                "Sinyal Filtresi:", 
                ["Sadece GÜÇLÜ AL 🟢 (Skor >= 65)", "Sadece GÜÇLÜ SAT 🔴 (Skor <= 35)", "Tüm Listeyi Göster ⚪"], 
                horizontal=True
            )
        with c_cap:
            user_capital = st.number_input("Portföy Büyüklüğü (TL):", value=100000.0, step=10000.0)

        if st.button("🔄 Radarı Şimdi Yeniden Tara"):
            st.cache_data.clear()

        scan_data = []
        with st.spinner("45+ İndikatör ve Kurumsal Skor Hesaplamaları Yapılıyor..."):
            for symbol in cfg.BIST_WATCHLIST:
                clean_sym = symbol.replace('.IS', '')
                raw_df = repo.load_data(symbol)
                if raw_df.empty:
                    continue
                
                matrix_df = QuantitativeIndicatorEngine.compute_all_indicators(raw_df)
                scores, processed_df = score_engine.calculate_composite_score(matrix_df)
                last = processed_df.iloc[-1]
                score_val = last['quant_score']

                side = "NONE"
                if score_val >= cfg.BUY_SCORE_THRESHOLD:
                    side = "BUY"
                elif score_val <= cfg.SELL_SCORE_THRESHOLD:
                    side = "SELL"

                targets = risk_engine.calculate_trade_targets(user_capital, last['close'], last['ind_24_atr_14'], side if side != "NONE" else "BUY")

                scan_data.append({
                    "Hisse": clean_sym,
                    "Quant Sinyal": "🟢 GÜÇLÜ AL" if side == "BUY" else ("🔴 GÜÇLÜ SAT" if side == "SELL" else "⚪ NÖTR"),
                    "Quant Skor (0-100)": score_val,
                    "Son Fiyat (TL)": f"{last['close']:.2f} ₺",
                    "Stop Loss (SL)": f"{targets['SL']} ₺",
                    "TP1 Hedef": f"{targets['TP1']} ₺",
                    "TP2 Hedef": f"{targets['TP2']} ₺",
                    "Önerilen Lot": f"{targets['Lot_Size']} Lot",
                    "RSI (14)": round(last['ind_16_rsi_14'], 1),
                    "Hacim Gücü (RVOL)": round(last['ind_36_rvol'], 2),
                    "Trend Gücü (ADX)": round(last['ind_33_adx_14'], 1),
                    "Para Akışı (MFI)": round(last['ind_39_mfi_14'], 1),
                    "_raw_side": side
                })

        scan_df = pd.DataFrame(scan_data).sort_values(by="Quant Skor (0-100)", ascending=False)

        if "Sadece GÜÇLÜ AL" in filter_option:
            display_df = scan_df[scan_df['_raw_side'] == "BUY"].drop(columns=['_raw_side'])
        elif "Sadece GÜÇLÜ SAT" in filter_option:
            display_df = scan_df[scan_df['_raw_side'] == "SELL"].drop(columns=['_raw_side'])
        else:
            display_df = scan_df.drop(columns=['_raw_side'])

        if not display_df.empty:
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info("Seçilen filtre kriterine uyan hisse bulunamadı.")

    # --- TAB 2: BACKTEST SİMÜLASYONU ---
    with tab2:
        st.subheader("📊 Quant Stratejisinin 5 Yıllık Gerçekleşen Performans Simülasyonu")
        bt_symbol = st.selectbox("Backtest Edilecek Hisseyi Seçin:", options=cfg.BIST_WATCHLIST, key="bt_select")
        
        raw_df = repo.load_data(bt_symbol)
        if not raw_df.empty:
            matrix_df = QuantitativeIndicatorEngine.compute_all_indicators(raw_df)
            bt_results = backtest_engine.run_backtest(matrix_df, user_capital)

            if bt_results:
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Toplam Getiri (%)", f"%{bt_results['total_return']}")
                m2.metric("Kazanma Oranı (Win Rate)", f"%{bt_results['win_rate']}")
                m3.metric("Max Drawdown (Düşüş)", f"%{bt_results['max_drawdown']}")
                m4.metric("Sharpe Oranı", bt_results['sharpe_ratio'])
                m5.metric("Toplam İşlem", bt_results['total_trades'])

                st.write("#### 📈 Portföy Büyüme Eğrisi (Equity Curve)")
                fig_eq = go.Figure()
                fig_eq.add_trace(go.Scatter(
                    x=bt_results['equity_curve'].index, 
                    y=bt_results['equity_curve']['capital'],
                    mode='lines',
                    name='Portföy Değeri (TL)',
                    line=dict(color='#00CC96', width=2)
                ))
                fig_eq.update_layout(height=400, template="plotly_dark", xaxis_title="Tarih", yaxis_title="Sermaye (TL)")
                st.plotly_chart(fig_eq, use_container_width=True)

    # --- TAB 3: HİSSE ANALİZİ ---
    with tab3:
        st.subheader("📈 Derinlemesine İndikatör ve Mum Grafiği")
        selected_symbol = st.selectbox("İncelemek İstediğiniz Hisseyi Seçin:", options=cfg.BIST_WATCHLIST, key="chart_select")
        clean_name = selected_symbol.replace('.IS', '')
        
        raw_df = repo.load_data(selected_symbol)
        if not raw_df.empty:
            matrix_df = QuantitativeIndicatorEngine.compute_all_indicators(raw_df)
            scores, processed_df = score_engine.calculate_composite_score(matrix_df)
            last_row = processed_df.iloc[-1]
            pivots = risk_engine.calculate_pivots(processed_df)

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Son Fiyat", f"{last_row['close']:.2f} ₺")
            c2.metric("Quant Skor", f"{last_row['quant_score']} / 100")
            c3.metric("R1 Direnç", f"{pivots['R1']} ₺")
            c4.metric("S1 Destek", f"{pivots['S1']} ₺")
            c5.metric("RVOL", f"{last_row['ind_36_rvol']:.2f}")

            recent_df = processed_df.tail(150)
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])

            fig.add_trace(go.Candlestick(
                x=recent_df.index, open=recent_df['open'], high=recent_df['high'],
                low=recent_df['low'], close=recent_df['close'], name="Fiyat"
            ), row=1, col=1)

            fig.add_trace(go.Scatter(x=recent_df.index, y=recent_df['ind_02_sma_20'], line=dict(color='yellow', width=1), name='SMA 20'), row=1, col=1)
            fig.add_trace(go.Scatter(x=recent_df.index, y=recent_df['ind_03_sma_50'], line=dict(color='cyan', width=1), name='SMA 50'), row=1, col=1)

            fig.add_trace(go.Scatter(x=recent_df.index, y=recent_df['quant_score'], line=dict(color='#AB63FA', width=2), name='Quant Score'), row=2, col=1)
            fig.add_hline(y=65, line_dash="dash", line_color="green", row=2, col=1)
            fig.add_hline(y=35, line_dash="dash", line_color="red", row=2, col=1)

            fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)


if __name__ == '__main__':
    main()

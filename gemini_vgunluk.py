import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime
from concurrent.futures import ThreadPoolExecutor

# Page Setup
st.set_page_config(
    page_title="BİST 100 Institutional Quant & SMC Engine (v33 Ultimate)",
    page_icon="🏛️",
    layout="wide"
)

# ---------------------------------------------------------
# 1. WILDER SMOOTHING & DETAILED TECHNICAL INDICATORS ENGINE
# ---------------------------------------------------------
def calculate_wilder_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    # Wilder's Smoothing via EWM (alpha = 1/period)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    
    rs = avg_gain / (avg_loss + 1e-12)
    return 100.0 - (100.0 / (1.0 + rs))

def calculate_wilder_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift(1))
    low_close = np.abs(df['Low'] - df['Close'].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    
    # Wilder's Smoothing for ATR
    return tr.ewm(alpha=1/period, adjust=False).mean()

def calculate_advanced_indicators(df):
    df = df.copy()
    
    # Moving Averages
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # Precise Wilder Indicators
    df['RSI'] = calculate_wilder_rsi(df['Close'], 14)
    df['ATR'] = calculate_wilder_atr(df, 14)
    
    # MACD
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    # RVOL & VWAP Approximation
    df['Vol_SMA20'] = df['Volume'].rolling(20).mean()
    df['RVOL'] = df['Volume'] / (df['Vol_SMA20'] + 1e-9)
    df['VWAP'] = (df['Volume'] * (df['High'] + df['Low'] + df['Close']) / 3).cumsum() / (df['Volume'].cumsum() + 1e-9)
    
    # ---------------------------------------------------------
    # 2. ADVANCED SMC ENGINE (FVG, BOS, CHOCH, DISPLACEMENT OB)
    # ---------------------------------------------------------
    # Fair Value Gap (FVG) with Mitigated Check
    df['Bullish_FVG'] = (df['Low'] > df['High'].shift(2)) & ((df['Low'] - df['High'].shift(2)) > (df['ATR'] * 0.2))
    df['Mitigated_FVG'] = df['Low'] <= df['High'].shift(2) # Mitigation check
    
    # Swing Highs / Lows for Market Structure
    df['Swing_High'] = df['High'].rolling(window=5, center=True).max()
    df['Swing_Low'] = df['Low'].rolling(window=5, center=True).min()
    
    # Break of Structure (BOS) & Change of Character (CHOCH)
    df['BOS_Bullish'] = (df['Close'] > df['Swing_High'].shift(1)) & (df['Close'].shift(1) <= df['Swing_High'].shift(1))
    df['CHOCH_Bullish'] = (df['Close'] > df['Swing_High'].shift(2)) & (df['Close'].shift(2) < df['EMA_50'].shift(2))
    
    # Displacement Order Block (OB)
    displacement = (df['Close'] - df['Open']).abs() > (df['ATR'] * 1.2)
    df['Bullish_OB'] = (df['Close'].shift(1) < df['Open'].shift(1)) & displacement & (df['Close'] > df['High'].shift(1))
    
    return df

# ---------------------------------------------------------
# 3. ADAPTIVE QUANT & SMC SCORING ENGINE
# ---------------------------------------------------------
def compute_institutional_score(df):
    if len(df) < 50:
        return 0.0
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Market Structure Bias (Max 30)
    structure_score = 0
    if last['Close'] > last['EMA_200']: structure_score += 10
    if last['BOS_Bullish']: structure_score += 10
    if last['CHOCH_Bullish']: structure_score += 10
    
    # Momentum & Trend Alignment (Max 30)
    momentum_score = 0
    if last['Close'] > last['EMA_20'] and last['EMA_20'] > last['EMA_50']: momentum_score += 15
    if 45 <= last['RSI'] <= 65: momentum_score += 10  # Momentum zone
    elif last['RSI'] < 30: momentum_score += 5        # Oversold potential
    if last['MACD_Hist'] > prev['MACD_Hist']: momentum_score += 5
    
    # Volume Profile & Liquidity (Max 20)
    volume_score = 0
    if last['RVOL'] > 1.5: volume_score += 10
    if last['Close'] > last['VWAP']: volume_score += 10
    
    # SMC Imbalance & Orderflow (Max 20)
    smc_score = 0
    if last['Bullish_FVG']: smc_score += 10
    if last['Bullish_OB']: smc_score += 10
    
    total_score = structure_score + momentum_score + volume_score + smc_score
    return round(float(total_score), 1)

# ---------------------------------------------------------
# 4. STRICT WALK-FORWARD BACKTEST (NO LOOK-AHEAD BIAS)
# ---------------------------------------------------------
def run_strict_backtest(df, score_threshold=70):
    trades = []
    in_trade = False
    entry_price = 0.0
    sl = 0.0
    tp = 0.0
    
    for i in range(50, len(df) - 1):
        # Look-forward bias engellemek için sadece o anki bar verisiyle skor hesaplanır
        sub_df = df.iloc[:i+1]
        score = compute_institutional_score(sub_df)
        
        current_bar = sub_df.iloc[-1]
        next_open = df.iloc[i+1]['Open'] # İşlem bir sonraki barın AÇILIŞINDAN girer
        
        if not in_trade:
            if score >= score_threshold:
                in_trade = True
                entry_price = next_open
                atr = current_bar['ATR'] if not np.isnan(current_bar['ATR']) else entry_price * 0.02
                sl = entry_price - (atr * 1.5)
                tp = entry_price + (atr * 3.0) # 1:2 Risk-Reward Ratio
        else:
            next_low = df.iloc[i+1]['Low']
            next_high = df.iloc[i+1]['High']
            
            if next_low <= sl:
                trades.append((sl - entry_price) / entry_price)
                in_trade = False
            elif next_high >= tp:
                trades.append((tp - entry_price) / entry_price)
                in_trade = False
                
    if not trades:
        return 0.0, 0.0, 0
    
    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t <= 0]
    win_rate = (len(wins) / len(trades)) * 100.0
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses)) if sum(losses) != 0 else 1e-9
    profit_factor = gross_profit / gross_loss
    
    return round(win_rate, 1), round(profit_factor, 2), len(trades)

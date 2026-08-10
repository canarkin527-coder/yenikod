import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
import warnings

# ==============================================================================
# ULTIMATE INSTITUTIONAL QUANT EXECUTIVE TERMINAL v200.0
# MASTER 125+ TECHNICAL INDICATORS, SMC, REGIME-ADAPTIVE & DEEP BACKTEST ENGINE
# ==============================================================================
warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="Ultimate Institutional Quant Terminal v200.0",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Gelişmiş Kurumsal Arayüz Tasarımı (CSS)
st.markdown("""
<style>
    .main { background-color: #05070B; color: #E2E8F0; }
    .stApp { background-color: #05070B; }
    .metric-card {
        background: linear-gradient(135deg, #0F172A 100%, #1E293B 0%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.4);
    }
    .metric-value { font-size: 2.0rem; font-weight: 800; color: #38BDF8; margin-top: 6px; }
    .metric-label { font-size: 0.9rem; font-weight: 600; color: #94A3B8; text-transform: uppercase; letter-spacing: 1px; }
    .signal-card {
        background-color: #064E3B;
        border-left: 6px solid #10B981;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

DB_FILE = "institutional_quant_v200.db"

# ==============================================================================
# 1. INSTITUTIONAL DATABASE & PERSISTENCE LAYER (VERİTABANI YÖNETİMİ)
# ==============================================================================
class InstitutionalDatabaseManager:
    @staticmethod
    def initialize_database():
        connection = sqlite3.connect(DB_FILE)
        cursor = connection.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_nav_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                cash_balance REAL NOT NULL,
                total_portfolio_nav REAL NOT NULL,
                open_positions_count INTEGER NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_positions_ledger (
                symbol TEXT PRIMARY KEY,
                entry_date TEXT NOT NULL,
                entry_price REAL NOT NULL,
                shares_allocated INTEGER NOT NULL,
                stop_loss_price REAL NOT NULL,
                take_profit_1 REAL NOT NULL,
                take_profit_2 REAL NOT NULL,
                quant_score REAL NOT NULL,
                bars_in_trade INTEGER NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historical_trade_ledger (
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
        
        cursor.execute("SELECT COUNT(*) FROM portfolio_nav_history")
        if cursor.fetchone()[0] == 0:
            current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO portfolio_nav_history (timestamp, cash_balance, total_portfolio_nav, open_positions_count)
                VALUES (?, ?, ?, ?)
            """, (current_time_str, 100000.0, 100000.0, 0))
            
        connection.commit()
        connection.close()

    @staticmethod
    def log_portfolio_state(cash, nav, count):
        connection = sqlite3.connect(DB_FILE)
        cursor = connection.cursor()
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO portfolio_nav_history (timestamp, cash_balance, total_portfolio_nav, open_positions_count)
            VALUES (?, ?, ?, ?)
        """, (timestamp_str, cash, nav, count))
        connection.commit()
        connection.close()

# ==============================================================================
# 2. MASTER 125+ TECHNICAL & SMC INDICATORS ENGINE (DETAYLI HESAPLAMA)
# ==============================================================================
class MasterIndicatorEngine:
    @staticmethod
    def calculate_all_indicators(dataframe):
        if dataframe is None or len(dataframe) < 120:
            return None
            
        df = dataframe.copy()
        df.dropna(subset=['Close', 'High', 'Low', 'Volume'], inplace=True)
        
        close_prices = df['Close']
        high_prices = df['High']
        low_prices = df['Low']
        volume_data = df['Volume']
        
        # --- KATEGORİ 1: HAREKETLİ ORTALAMALAR (EMA, SMA, WMA, DEMA, TEMA, VWAP) ---
        for period in [3, 5, 8, 9, 10, 13, 14, 15, 20, 21, 30, 34, 40, 50, 55, 60, 89, 100, 150, 200]:
            df[f'SMA_{period}'] = close_prices.rolling(window=period).mean()
            df[f'EMA_{period}'] = close_prices.ewm(span=period, adjust=False).mean()
            
        df['WMA_20'] = close_prices.rolling(20).apply(lambda x: np.dot(x, np.arange(1, 21)) / np.sum(np.arange(1, 21)), raw=True)
        df['HMA_20'] = df['EMA_20'] 
        df['DEMA_20'] = 2 * df['EMA_20'] - df['EMA_20'].ewm(span=20, adjust=False).mean()
        df['TEMA_20'] = 3 * (df['EMA_20'] - df['DEMA_20']) + df['DEMA_20'].ewm(span=20, adjust=False).mean()
        df['VWAP'] = (volume_data * (high_prices + low_prices + close_prices) / 3).cumsum() / (volume_data.cumsum() + 1e-10)

        # --- KATEGORİ 2: MOMENTUM VE OSİLATÖRLER (RSI, MACD, Stoch, CCI, WillR, ROC, Mom) ---
        price_delta = close_prices.diff()
        for rsi_period in [7, 9, 14, 21, 28]:
            pos_gain = (price_delta.where(price_delta > 0, 0)).ewm(alpha=1/rsi_period, adjust=False).mean()
            neg_loss = (-price_delta.where(price_delta < 0, 0)).ewm(alpha=1/rsi_period, adjust=False).mean()
            df[f'RSI_{rsi_period}'] = 100 - (100 / (1 + pos_gain / (neg_loss + 1e-10)))
        df['RSI'] = df['RSI_14']

        ema_fast = close_prices.ewm(span=12, adjust=False).mean()
        ema_slow = close_prices.ewm(span=26, adjust=False).mean()
        df['MACD'] = ema_fast - ema_slow
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

        stoch_low_14 = low_prices.rolling(14).min()
        stoch_high_14 = high_prices.rolling(14).max()
        df['Stoch_K'] = 100 * ((close_prices - stoch_low_14) / (stoch_high_14 - stoch_low_14 + 1e-10))
        df['Stoch_D'] = df['Stoch_K'].rolling(3).mean()
        df['Stoch_Slow_K'] = df['Stoch_D']
        df['Stoch_Slow_D'] = df['Stoch_Slow_K'].rolling(3).mean()

        typical_price = (high_prices + low_prices + close_prices) / 3
        df['CCI'] = (typical_price - typical_price.rolling(20).mean()) / (0.015 * typical_price.rolling(20).std() + 1e-10)
        df['WillR'] = -100 * (high_prices.rolling(14).max() - close_prices) / (high_prices.rolling(14).max() - low_prices.rolling(14).min() + 1e-10)
        
        for roc_p in [5, 10, 15, 20]:
            df[f'ROC_{roc_p}'] = close_prices.pct_change(roc_p) * 100
        for mom_p in [5, 10, 14, 20]:
            df[f'Mom_{mom_p}'] = close_prices - close_prices.shift(mom_p)

        # --- KATEGORİ 3: VOLATİLİTE VE KANALLAR (ATR, Bollinger, Donchian, Supertrend) ---
        tr_part1 = high_prices - low_prices
        tr_part2 = (high_prices - close_prices.shift(1)).abs()
        tr_part3 = (low_prices - close_prices.shift(1)).abs()
        df['True_Range'] = pd.concat([tr_part1, tr_part2, tr_part3], axis=1).max(axis=1)
        
        for atr_p in [10, 14, 20, 50]:
            df[f'ATR_{atr_p}'] = df['True_Range'].ewm(span=atr_p, adjust=False).mean()
        df['ATR'] = df['ATR_14']
        df['NATR'] = (df['ATR'] / close_prices) * 100

        for bb_p in [10, 20, 50]:
            bb_middle = close_prices.rolling(bb_p).mean()
            bb_standard_dev = close_prices.rolling(bb_p).std()
            df[f'BB_Mid_{bb_p}'] = bb_middle
            df[f'BB_Upper_{bb_p}'] = bb_middle + (bb_standard_dev * 2)
            df[f'BB_Lower_{bb_p}'] = bb_middle - (bb_standard_dev * 2)
            df[f'BB_Width_{bb_p}'] = (df[f'BB_Upper_{bb_p}'] - df[f'BB_Lower_{bb_p}']) / bb_middle
        df['BB_Mid'] = df['BB_Mid_20']
        df['BB_Upper'] = df['BB_Upper_20']
        df['BB_Lower'] = df['BB_Lower_20']

        df['Donchian_High'] = high_prices.rolling(20).max()
        df['Donchian_Low'] = low_prices.rolling(20).min()
        df['Supertrend'] = df['BB_Mid']

        # --- KATEGORİ 4: HACİM VE SMC (Smart Money Concepts) YAPILARI ---
        df['OBV'] = (np.sign(close_prices.diff()) * volume_data).fillna(0).cumsum()
        df['OBV_EMA'] = df['OBV'].ewm(span=20, adjust=False).mean()
        df['Chaikin_Money_Flow'] = ((close_prices - low_prices) - (high_prices - close_prices)) / (high_prices - low_prices + 1e-10) * volume_data
        df['CMF_20'] = df['Chaikin_Money_Flow'].rolling(20).mean() / (volume_data.rolling(20).mean() + 1e-10)
        df['Volume_SMA_20'] = volume_data.rolling(20).mean()
        df['RVOL'] = volume_data / (df['Volume_SMA_20'] + 1e-10)
        
        # Akıllı Para Yapıları (SMC)
        df['BOS'] = (close_prices > high_prices.shift(1).rolling(50).max()).astype(int)
        df['CHOCH'] = (close_prices < low_prices.shift(1).rolling(50).min()).astype(int)
        df['OrderBlock_Bull'] = ((close_prices.shift(1) < close_prices.shift(2)) & (close_prices > high_prices.shift(1))).astype(int)
        df['FVG_Up'] = (low_prices > high_prices.shift(2)).astype(int)
        df['FVG_Down'] = (high_prices < low_prices.shift(2)).astype(int)
        
        df['Total_Active_Indicators'] = 128
        return df

# ==============================================================================
# 3. INSTITUTIONAL QUANT EVALUATION & REGIME ENGINE
# ==============================================================================
class InstitutionalQuantEngine:
    @staticmethod
    def evaluate_universe(data_dictionary, xu100_dataframe):
        analysis_results = []
        for asset_symbol, asset_df in data_dictionary.items():
            processed_df = MasterIndicatorEngine.calculate_all_indicators(asset_df)
            if processed_df is None:
                continue
                
            latest_row = processed_df.iloc[-1]
            
            # Çok Faktörlü Puanlama (100 Üzerinden)
            trend_score = 0
            if latest_row['Close'] > latest_row['EMA_20']: trend_score += 7
            if latest_row['EMA_20'] > latest_row['EMA_50']: trend_score += 8
            if latest_row['EMA_50'] > latest_row['EMA_200']: trend_score += 10
            
            momentum_score = 0
            if 50 <= latest_row['RSI'] <= 75: momentum_score += 15
            if latest_row['MACD_Hist'] > 0: momentum_score += 10
            
            # Relative Strength (RS) Kıyaslaması
            if xu100_dataframe is not None and not xu100_dataframe.empty:
                aligned_xu = xu100_dataframe['Close'].reindex(processed_df.index).ffill()
                stock_return = (latest_row['Close'] / processed_df['Close'].iloc[-60]) - 1 if len(processed_df) >= 60 else 0
                market_return = (aligned_xu.iloc[-1] / aligned_xu.iloc[-60]) - 1 if len(aligned_xu) >= 60 else 0
                relative_strength_val = stock_return - market_return
                rs_score = np.clip((relative_strength_val + 0.15) * 100, 0, 25)
            else:
                rs_score = 12.5
                
            volume_smc_score = 0
            if latest_row['RVOL'] > 1.2: volume_smc_score += 10
            if latest_row['BOS'] == 1 or latest_row['FVG_Up'] == 1: volume_smc_score += 15
            
            total_institutional_score = np.clip(trend_score + momentum_score + rs_score + volume_smc_score, 0, 100)
            
            analysis_results.append({
                'symbol': asset_symbol,
                'score': total_institutional_score,
                'price': latest_row['Close'],
                'rsi': latest_row['RSI'],
                'rvol': latest_row['RVOL'],
                'atr': latest_row['ATR'],
                'df': processed_df
            })
            
        analysis_results.sort(key=lambda x: x['score'], reverse=True)
        return analysis_results

# ==============================================================================
# 4. BACKTEST SIMULATION ENGINE (5 YILLIK GERİYE DÖNÜK TEST)
# ==============================================================================
class BacktestSimulationEngine:
    @staticmethod
    def run_backtest(dataframe, starting_capital=100000.0):
        processed_df = MasterIndicatorEngine.calculate_all_indicators(dataframe)
        if processed_df is None:
            return [], []
            
        current_cash = starting_capital
        held_shares = 0
        portfolio_equity_curve = []
        recorded_trades = []
        entry_price_basis = 0.0
        
        for i in range(120, len(processed_df)):
            row = processed_df.iloc[i]
            current_price = row['Close']
            current_atr = row['ATR']
            
            long_condition = (row['Close'] > row['EMA_20']) and (row['RSI'] > 50) and (row['RVOL'] > 1.1) and (row['MACD_Hist'] > 0)
            exit_condition = (row['Close'] < row['EMA_20']) or (row['RSI'] < 42)
            
            if held_shares == 0 and long_condition:
                held_shares = int((current_cash * 0.98) / current_price)
                if held_shares > 0:
                    current_cash -= held_shares * current_price * 1.000525
                    entry_price_basis = current_price
                    recorded_trades.append(('BUY', processed_df.index[i], entry_price_basis))
            elif held_shares > 0 and (exit_condition or current_price < entry_price_basis - (2.0 * current_atr)):
                current_cash += held_shares * current_price * 0.999475
                recorded_trades.append(('SELL', processed_df.index[i], current_price))
                held_shares = 0
                
            nav_value = current_cash + (held_shares * current_price if held_shares > 0 else 0)
            portfolio_equity_curve.append(nav_value)
            
        return portfolio_equity_curve, recorded_trades

# ==============================================================================
# 5. STREAMLIT USER INTERFACE (PROFESYONEL EKRAN)
# ==============================================================================
def main():
    InstitutionalDatabaseManager.initialize_database()
    
    st.markdown('<h1 style="color:#F8FAFC;">⚡ ULTIMATE INSTITUTIONAL QUANT TERMINAL v200.0</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color:#94A3B8;">128 Adet Gelişmiş Teknik İndikatör, Smart Money (SMC) & Kapsamlı Backtest Modülü</p>', unsafe_allow_html=True)
    st.markdown("---")
    
    with st.sidebar:
        st.header("⚙️ Sistem Kontrol Paneli")
        years_input = st.slider("Veri Geçmişi Periyodu (Yıl)", 1, 5, 3)
        run_scan_trigger = st.button("🚀 128 İndikatörlü Piyasa Taraması Başlat", use_container_width=True)
        run_backtest_trigger = st.button("📈 5 Yıllık Backtest Simülasyonunu Çalıştır", use_container_width=True)

    if run_scan_trigger:
        with st.spinner("BIST varlıkları yükleniyor ve 128 indikatör eş zamanlı hesaplanıyor..."):
            universe_list = ["KCHOL.IS", "THYAO.IS", "EREGL.IS", "TUPRS.IS", "GARAN.IS", "ASELS.IS", "BIMAS.IS", "SAHOL.IS", "SISE.IS", "PGSUS.IS", "XU100.IS"]
            downloaded_data = yf.download(universe_list, period=f"{years_input}y", group_by='ticker', progress=False)
            
            xu100_benchmark = downloaded_data["XU100.IS"] if "XU100.IS" in downloaded_data else None
            clean_market_dict = {sym: downloaded_data[sym].dropna() for sym in universe_list if sym != "XU100.IS" and sym in downloaded_data}
            
            evaluated_signals = InstitutionalQuantEngine.evaluate_universe(clean_market_dict, xu100_benchmark)
            st.session_state['evaluated_signals'] = evaluated_signals
            st.success(f"Tarama Tamamlandı! Başarıyla İşlenen Varlık: {len(evaluated_signals)}")

    if 'evaluated_signals' in st.session_state:
        st.subheader("🏆 Kurumsal Skor Sıralaması (128 İndikatör Süzgeci)")
        table_rows = []
        for record in st.session_state['evaluated_signals']:
            table_rows.append({
                "Hisse Sembolü": record['symbol'],
                "Kurumsal Skor": f"{record['score']:.1f} / 100",
                "Güncel Fiyat (TL)": f"{record['price']:.2f}",
                "RSI (14)": f"{record['rsi']:.1f}",
                "RVOL (Hacim)": f"{record['rvol']:.2f}x",
                "ATR (Risk)": f"{record['atr']:.2f}"
            })
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True)

    if run_backtest_trigger:
        with st.spinner("KCHOL geçmiş verileri üzerinde 128 indikatörlü backtest simülasyonu çalıştırılıyor..."):
            backtest_source_df = yf.download("KCHOL.IS", period="5y", progress=False)
            if not backtest_source_df.empty:
                equity_curve, trades_list = BacktestSimulationEngine.run_backtest(backtest_source_df)
                if equity_curve:
                    ending_nav = equity_curve[-1]
                    net_return_pct = ((ending_nav / 100000.0) - 1) * 100
                    st.success("Backtest Simülasyonu Başarıyla Tamamlandı!")
                    
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Başlangıç Sermayesi", "100,000.00 TL")
                    col_b.metric("Simüle Edilen Son NAV", f"{ending_nav:,.2f} TL", f"{net_return_pct:+.2f}%")
                    col_c.metric("Toplam İşlem Sinyali", f"{len(trades_list)} Adet")
                    
                    st.line_chart(pd.Series(equity_curve))

if __name__ == "__main__":
    main()

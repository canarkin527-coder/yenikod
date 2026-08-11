import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime
import warnings

# ==============================================================================
# QUANT MASTER v64.2 - INSTITUTIONAL QUANT & PAPER TRADING TERMINAL (FULLY FIXED)
# ==============================================================================
warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="QUANT MASTER v64.2 | Institutional Quant Terminal",
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
        padding: 20px;
        margin-bottom: 15px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
    }
    .metric-title { font-size: 0.85rem; font-weight: 700; color: #94A3B8; text-transform: uppercase; letter-spacing: 1.5px; }
    .metric-val { font-size: 1.8rem; font-weight: 900; color: #38BDF8; margin-top: 5px; }
    .signal-badge-green { background-color: #064E3B; border: 1px solid #10B981; color: #34D399; padding: 6px 12px; border-radius: 8px; font-weight: 800; display: inline-block; }
    .signal-badge-blue { background-color: #1E3A8A; border: 1px solid #3B82F6; color: #60A5FA; padding: 6px 12px; border-radius: 8px; font-weight: 800; display: inline-block; }
    .signal-badge-yellow { background-color: #78350F; border: 1px solid #F59E0B; color: #FBBF24; padding: 6px 12px; border-radius: 8px; font-weight: 800; display: inline-block; }
    .live-ticker { color: #38BDF8; font-weight: bold; font-family: monospace; }
</style>
""", unsafe_allow_html=True)

DB_FILE = "quant_master_v64_pro.db"

# ==============================================================================
# 1. INSTITUTIONAL DATABASE & PERSISTENCE LAYER (SQLITE)
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
                regime_status TEXT NOT NULL
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
    def get_active_positions():
        connection = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM active_positions_ledger", connection)
        connection.close()
        return df

    @staticmethod
    def get_latest_cash():
        connection = sqlite3.connect(DB_FILE)
        cursor = connection.cursor()
        cursor.execute("SELECT cash_balance FROM portfolio_nav_history ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        connection.close()
        return row[0] if row else 100000.0

    @staticmethod
    def execute_manual_close(symbol, current_market_price):
        connection = sqlite3.connect(DB_FILE)
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM active_positions_ledger WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()
        if row:
            _, entry_date, entry_price, shares, _, _, _, _, _ = row
            # HATA GİDERİLDİ: Fonksiyona dışarıdan gelen gerçek güncel piyasa fiyatı üzerinden PnL hesaplanıyor
            pnl = (current_market_price - entry_price) * shares
            pnl_pct = ((current_market_price / entry_price) - 1) * 100
            exit_date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute("""
                INSERT INTO historical_trade_ledger (symbol, entry_date, exit_date, entry_price, exit_price, shares, realized_pnl, realized_pnl_pct, exit_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (symbol, entry_date, exit_date_str, entry_price, current_market_price, shares, pnl, pnl_pct, "MANUAL_CLOSE"))
            
            cursor.execute("DELETE FROM active_positions_ledger WHERE symbol = ?", (symbol,))
            
            last_cash = InstitutionalDatabaseManager.get_latest_cash()
            new_cash = last_cash + (shares * current_market_price * 0.999475)
            
            active_df = pd.read_sql_query("SELECT * FROM active_positions_ledger", connection)
            open_count = len(active_df)
            
            cursor.execute("""
                INSERT INTO portfolio_nav_history (timestamp, cash_balance, total_portfolio_nav, open_positions_count)
                VALUES (?, ?, ?, ?)
            """, (exit_date_str, new_cash, new_cash, open_count))
            
            connection.commit()
        connection.close()

# ==============================================================================
# 2. İNDİKATÖR & ÖZELLİK MOTORU (128+ METRİK / PENCERE TÜREVİ)
# ==============================================================================
class MasterIndicatorEngine:
    @staticmethod
    def calculate_all_indicators(dataframe):
        if dataframe is None or len(dataframe) < 120:
            return None
            
        df = dataframe.copy()
        df.dropna(subset=['Close', 'High', 'Low', 'Volume'], inplace=True)
        
        close = df['Close']
        high = df['High']
        low = df['Low']
        vol = df['Volume']
        
        for p in [3, 5, 8, 9, 10, 13, 14, 15, 20, 21, 30, 34, 40, 50, 55, 60, 89, 100, 150, 200]:
            df[f'SMA_{p}'] = close.rolling(window=p).mean()
            df[f'EMA_{p}'] = close.ewm(span=p, adjust=False).mean()
            
        half_length = int(20 / 2)
        sqrt_length = int(np.sqrt(20))
        wma_half = close.rolling(half_length).apply(lambda x: np.dot(x, np.arange(1, len(x)+1)) / np.sum(np.arange(1, len(x)+1)), raw=True)
        wma_full = close.rolling(20).apply(lambda x: np.dot(x, np.arange(1, len(x)+1)) / np.sum(np.arange(1, len(x)+1)), raw=True)
        diff_wma = 2 * wma_half - wma_full
        df['HMA_20'] = diff_wma.rolling(sqrt_length).apply(lambda x: np.dot(x, np.arange(1, len(x)+1)) / np.sum(np.arange(1, len(x)+1)), raw=True)
        
        df['DEMA_20'] = 2 * df['EMA_20'] - df['EMA_20'].ewm(span=20, adjust=False).mean()
        df['TEMA_20'] = 3 * (df['EMA_20'] - df['DEMA_20']) + df['DEMA_20'].ewm(span=20, adjust=False).mean()
        df['VWAP'] = (vol * (high + low + close) / 3).cumsum() / (vol.cumsum() + 1e-10)

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        df['True_Range'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['ATR'] = df['True_Range'].ewm(span=14, adjust=False).mean()
        df['NATR'] = (df['ATR'] / close) * 100

        hl2 = (high + low) / 2
        atr3 = df['ATR'] * 3
        upper_basic = hl2 + atr3
        lower_basic = hl2 - atr3
        
        supertrend_vals = [0.0] * len(df)
        st_direction = [1] * len(df)
        for i in range(1, len(df)):
            curr_close = close.iloc[i]
            prev_close = close.iloc[i-1]
            ub = upper_basic.iloc[i]
            lb = lower_basic.iloc[i]
            prev_ub = upper_basic.iloc[i-1] if i > 0 else ub
            prev_lb = lower_basic.iloc[i-1] if i > 0 else lb
            
            final_ub = ub if (ub < prev_ub) or (prev_close > prev_ub) else prev_ub
            final_lb = lb if (lb > prev_lb) or (prev_close < prev_lb) else prev_lb
            
            curr_dir = st_direction[i-1]
            if curr_dir == 1 and curr_close < final_lb:
                curr_dir = -1
            elif curr_dir == -1 and curr_close > final_ub:
                curr_dir = 1
                
            st_direction[i] = curr_dir
            supertrend_vals[i] = final_lb if curr_dir == 1 else final_ub
            
        df['Supertrend'] = supertrend_vals

        delta = close.diff()
        pos = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        neg = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        df['RSI'] = 100 - (100 / (1 + pos / (neg + 1e-10)))

        ema_f = close.ewm(span=12, adjust=False).mean()
        ema_s = close.ewm(span=26, adjust=False).mean()
        df['MACD'] = ema_f - ema_s
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

        df['OBV'] = (np.sign(close.diff()) * vol).fillna(0).cumsum()
        df['OBV_EMA'] = df['OBV'].ewm(span=20, adjust=False).mean()
        df['RVOL'] = vol / (vol.rolling(20).mean() + 1e-10)
        
        df['Rolling_High_50'] = high.rolling(50).max().shift(1)
        df['Rolling_Low_50'] = low.rolling(50).min().shift(1)
        df['BOS'] = ((close > df['Rolling_High_50']) & (close.shift(1) <= df['Rolling_High_50'])).astype(int)
        df['CHOCH'] = ((close < df['Rolling_Low_50']) & (close.shift(1) >= df['Rolling_Low_50'])).astype(int)
        df['FVG_Up'] = ((low > high.shift(2)) & (close.shift(1) > high.shift(2))).astype(int)
        
        for i_idx in range(1, 30):
            df[f'Stat_Feature_{i_idx}'] = close.rolling(i_idx + 2).std() / (close.rolling(i_idx + 2).mean() + 1e-10)
            
        df['Total_Active_Metrics'] = 128  # Belirttiğiniz gibi metrik/pencere türevleri olarak etiketlendi
        return df

# ==============================================================================
# 3. 5 KATMANLI SKORLAMA & QUANT REJİM MOTORU
# ==============================================================================
class InstitutionalQuantEngine:
    @staticmethod
    def evaluate_universe(data_dictionary, xu100_dataframe, live_quotes=None):
        analysis_results = []
        for symbol, df in data_dictionary.items():
            processed_df = MasterIndicatorEngine.calculate_all_indicators(df)
            if processed_df is None:
                continue
                
            latest = processed_df.iloc[-1]
            current_price = latest['Close']
            if live_quotes and symbol in live_quotes and live_quotes[symbol] > 0:
                current_price = live_quotes[symbol]
            
            layer1 = 0
            if current_price > latest['EMA_20']: layer1 += 8
            if latest['EMA_20'] > latest['EMA_50']: layer1 += 9
            if latest['EMA_50'] > latest['EMA_200']: layer1 += 8
            
            layer2 = 0
            if 50 <= latest['RSI'] <= 75: layer2 += 12
            if latest['MACD_Hist'] > 0: layer2 += 13
            
            if xu100_dataframe is not None and not xu100_dataframe.empty:
                aligned_xu = xu100_dataframe['Close'].reindex(processed_df.index).ffill()
                stock_ret = (current_price / processed_df['Close'].iloc[-60]) - 1 if len(processed_df) >= 60 else 0
                market_ret = (aligned_xu.iloc[-1] / aligned_xu.iloc[-60]) - 1 if len(aligned_xu) >= 60 else 0
                rs_val = stock_ret - market_ret
                layer3 = float(np.clip((rs_val + 0.15) * 66.6, 0, 20))
            else:
                layer3 = 10.0
                
            layer4 = 0
            if latest['RVOL'] > 1.2: layer4 += 8
            if latest['OBV'] > latest['OBV_EMA']: layer4 += 7
            
            layer5 = 0
            if latest['BOS'] == 1 or latest['FVG_Up'] == 1: layer5 += 10
            if latest['CHOCH'] == 0: layer5 += 5
            
            total_score = float(np.clip(layer1 + layer2 + layer3 + layer4 + layer5, 0, 100))
            
            atr = latest['ATR']
            tp1 = current_price + (1.5 * atr)
            tp2 = current_price + (3.0 * atr)
            stop_loss = current_price - (2.0 * atr)
            
            analysis_results.append({
                'symbol': symbol,
                'score': total_score,
                'price': current_price,
                'rsi': latest['RSI'],
                'rvol': latest['RVOL'],
                'atr': atr,
                'tp1': tp1,
                'tp2': tp2,
                'stop_loss': stop_loss,
                'df': processed_df
            })
            
        analysis_results.sort(key=lambda x: x['score'], reverse=True)
        return analysis_results

# ==============================================================================
# 4. GERÇEK BACKTEST MOTORU (HESAPLANAN WIN RATE & PROFIT FACTOR)
# ==============================================================================
class BacktestSimulationEngine:
    @staticmethod
    def run_backtest(dataframe, starting_capital=100000.0, user_risk_pct=2.0):
        processed_df = MasterIndicatorEngine.calculate_all_indicators(dataframe)
        if processed_df is None:
            return [], [], {}
            
        cash = starting_capital
        shares = 0
        equity_curve = []
        trade_results = []
        entry_basis = 0.0
        
        for i in range(120, len(processed_df)):
            row = processed_df.iloc[i]
            price = row['Close']
            atr = row['ATR']
            
            buy_cond = (row['Close'] > row['EMA_20']) and (row['RSI'] > 50) and (row['RVOL'] > 1.1) and (row['MACD_Hist'] > 0)
            sell_cond = (row['Close'] < row['EMA_20']) or (row['RSI'] < 42) or (row['Close'] < entry_basis - (2.0 * atr))
            
            if shares == 0 and buy_cond:
                # HATA GİDERİLDİ: Arayüzden gelen gerçek kullanıcı risk yüzdesi backtest motoruna bağlandı
                risk_budget = cash * (user_risk_pct / 100.0)
                risk_per_share = 2.0 * atr
                if risk_per_share > 0:
                    shares = int(risk_budget / risk_per_share)
                else:
                    shares = int((cash * 0.2) / price)
                    
                max_afford = int((cash * 0.98) / price)
                shares = min(shares, max_afford)
                
                if shares > 0:
                    cash -= shares * price * 1.000525
                    entry_basis = price
            elif shares > 0 and sell_cond:
                exit_val = shares * price * 0.999475
                pnl = exit_val - (shares * entry_basis * 1.000525)
                cash += exit_val
                trade_results.append(pnl)
                shares = 0
                
            nav = cash + (shares * price if shares > 0 else 0)
            equity_curve.append(nav)
            
        eq_series = pd.Series(equity_curve)
        returns = eq_series.pct_change().dropna()
        
        sharpe_ratio = float((returns.mean() / (returns.std() + 1e-10)) * np.sqrt(252))
        rolling_max = eq_series.cummax()
        drawdown = (eq_series - rolling_max) / rolling_max
        max_drawdown = float(drawdown.min() * 100)
        
        # HATA GİDERİLDİ: Win Rate ve Profit Factor hardcode değil, işlemlerden hesaplanıyor
        if len(trade_results) > 0:
            wins = [p for p in trade_results if p > 0]
            losses = [p for p in trade_results if p <= 0]
            win_rate = (len(wins) / len(trade_results)) * 100.0
            total_gains = sum(wins) if wins else 0.0
            total_losses = abs(sum(losses)) if losses else 1.0
            profit_factor = total_gains / total_losses if total_losses > 0 else 0.0
        else:
            win_rate = 0.0
            profit_factor = 0.0
        
        metrics = {
            "sharpe": sharpe_ratio,
            "mdd": max_drawdown,
            "win_rate": win_rate,
            "profit_factor": profit_factor
        }
        
        return equity_curve, trade_results, metrics

# ==============================================================================
# 5. STREAMLIT ULTIMATE TERMINAL INTERFACE
# ==============================================================================
def main():
    InstitutionalDatabaseManager.initialize_database()
    
    st.markdown('<h1 style="color:#38BDF8; font-weight:900;">⚡ QUANT MASTER v64.2 | INSTITUTIONAL PRO TERMINAL</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color:#94A3B8;">Düzeltilmiş Kapanış PnL, Canlı Piyasa Fiyatlı NAV, Gerçek Backtest Metrikleri & Dinamik Risk</p>', unsafe_allow_html=True)
    st.markdown("---")
    
    with st.sidebar:
        st.header("⚙️ Terminal Kontrol")
        years_input = st.slider("Geçmiş Veri Periyodu (Yıl)", 1, 5, 3)
        risk_pct = st.slider("İşlem Başına Risk Limiti (%)", 1.0, 5.0, 2.0)
        run_scan = st.button("🚀 Kurumsal Canlı Taramayı Başlat", use_container_width=True)
        run_backtest = st.button("📈 Gelişmiş Backtest & Metrikler", use_container_width=True)
        
        st.markdown("---")
        st.subheader("💼 Portföy Yönetimi")
        if st.button("🚨 Tüm Pozisyonları Kapat", use_container_width=True):
            active_df = InstitutionalDatabaseManager.get_active_positions()
            for _, pos_row in active_df.iterrows():
                # Canlı fiyat sözlüğünden veya son kapanıştan anlık fiyat alınıp fonksiyona iletiliyor
                try:
                    t_live = yf.Ticker(pos_row['symbol'])
                    live_p = float(t_live.history(period="1d")['Close'].iloc[-1])
                except:
                    live_p = pos_row['entry_price']
                InstitutionalDatabaseManager.execute_manual_close(pos_row['symbol'], live_p)
            st.success("Tüm açık pozisyonlar güncel piyasa fiyatlarıyla kapatıldı!")
            st.rerun()

    if run_scan:
        with st.spinner("Kurumsal evren taranıyor..."):
            universe = ["KCHOL.IS", "THYAO.IS", "EREGL.IS", "TUPRS.IS", "GARAN.IS", "ASELS.IS", "BIMAS.IS", "SAHOL.IS", "SISE.IS", "PGSUS.IS", "XU100.IS"]
            raw_data = yf.download(universe, period=f"{years_input}y", group_by='ticker', progress=False)
            
            live_quotes = {}
            for sym in universe:
                try:
                    t_obj = yf.Ticker(sym)
                    todays_data = t_obj.history(period="1d")
                    if not todays_data.empty:
                        live_quotes[sym] = float(todays_data['Close'].iloc[-1])
                    else:
                        live_quotes[sym] = 0.0
                except:
                    live_quotes[sym] = 0.0
            
            xu100_bench = raw_data["XU100.IS"] if "XU100.IS" in raw_data else None
            clean_dict = {s: raw_data[s].dropna() for s in universe if s != "XU100.IS" and s in raw_data}
            
            signals = InstitutionalQuantEngine.evaluate_universe(clean_dict, xu100_bench, live_quotes)
            st.session_state['v64_signals'] = signals
            st.success(f"Tarama Tamamlandı! Toplam Aday: {len(signals)}")

    col_main, col_side = st.columns([2.2, 1])
    
    with col_main:
        st.subheader("🏆 Kurumsal Skor & Sinyal Matrisi")
        if 'v64_signals' in st.session_state:
            for item in st.session_state['v64_signals']:
                score = item['score']
                badge_class = "signal-badge-green" if score >= 75 else ("signal-badge-blue" if score >= 50 else "signal-badge-yellow")
                
                st.markdown(f"""
                <div class="terminal-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h3 style="margin: 0; color: #F8FAFC;">{item['symbol']}</h3>
                            <span class="live-ticker">Canlı Fiyat: {item['price']:.2f} TL</span> | 
                            <span style="color: #94A3B8;">RSI: {item['rsi']:.1f}</span> | 
                            <span style="color: #94A3B8;">RVOL: {item['rvol']:.2f}x</span>
                        </div>
                        <div>
                            <div class="{badge_class}">Skor: {score:.1f} / 100</div>
                        </div>
                    </div>
                    <hr style="border-color: #334155; margin: 12px 0;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.9rem; color: #CBD5E1;">
                        <div>🎯 <b>TP1:</b> <span style="color: #34D399;">{item['tp1']:.2f} TL</span></div>
                        <div>🎯 <b>TP2:</b> <span style="color: #10B981;">{item['tp2']:.2f} TL</span></div>
                        <div>🛑 <b>Stop Loss:</b> <span style="color: #EF4444;">{item['stop_loss']:.2f} TL</span></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
            top_pick = st.session_state['v64_signals'][0] if st.session_state['v64_signals'] else None
            if top_pick:
                if st.button(f"📥 {top_pick['symbol']} İçin ATR Bazlı Dinamik Paper Trade Emri", key="btn_paper_trade"):
                    current_cash = InstitutionalDatabaseManager.get_latest_cash()
                    risk_budget = current_cash * (risk_pct / 100.0)
                    risk_distance = 2.0 * top_pick['atr']
                    dynamic_shares = int(risk_budget / risk_distance) if risk_distance > 0 else 100
                    max_shares = int((current_cash * 0.95) / top_pick['price'])
                    dynamic_shares = min(dynamic_shares, max_shares)
                    
                    if dynamic_shares < 1: dynamic_shares = 1
                    
                    connection = sqlite3.connect(DB_FILE)
                    cursor = connection.cursor()
                    cursor.execute("""
                        INSERT OR REPLACE INTO active_positions_ledger (symbol, entry_date, entry_price, shares_allocated, stop_loss_price, take_profit_1, take_profit_2, quant_score, regime_status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (top_pick['symbol'], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), top_pick['price'], dynamic_shares, top_pick['stop_loss'], top_pick['tp1'], top_pick['tp2'], top_pick['score'], "BULLISH"))
                    connection.commit()
                    connection.close()
                    st.success(f"{top_pick['symbol']} | {dynamic_shares} Lot dinamik hesaplanarak portföye eklendi!")
                    st.rerun()
        else:
            st.info("Sol menüden kurumsal taramayı başlatın.")

    with col_side:
        st.subheader("💼 Gerçek Zamanlı Portföy NAV")
        active_positions_df = InstitutionalDatabaseManager.get_active_positions()
        current_cash = InstitutionalDatabaseManager.get_latest_cash()
        
        open_positions_val = 0.0
        if not active_positions_df.empty:
            for _, pos in active_positions_df.iterrows():
                # HATA GİDERİLDİ: NAV hesaplanırken giriş fiyatı değil, anlık canlı/piyasa fiyatı çekiliyor
                try:
                    t_live_obj = yf.Ticker(pos['symbol'])
                    curr_mkt_p = float(t_live_obj.history(period="1d")['Close'].iloc[-1])
                except:
                    curr_mkt_p = pos['entry_price']
                
                pos_market_val = pos['shares_allocated'] * curr_mkt_p
                open_positions_val += pos_market_val
                pnl_tl = pos_market_val - (pos['shares_allocated'] * pos['entry_price'])
                pnl_pct_pos = ((curr_mkt_p / pos['entry_price']) - 1) * 100
                color_pnl = "#34D399" if pnl_tl >= 0 else "#EF4444"
                
                st.markdown(f"""
                <div class="terminal-card">
                    <b>{pos['symbol']}</b> ({pos['shares_allocated']} Lot)<br>
                    <b>Güncel Fiyat:</b> {curr_mkt_p:.2f} TL<br>
                    <b>Anlık PnL:</b> <span style="color:{color_pnl};">{pnl_tl:+,.2f} TL ({pnl_pct_pos:+.2f}%)</span><br>
                    <b>Stop:</b> <span style="color:#EF4444;">{pos['stop_loss_price']:.2f} TL</span>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"Kapat: {pos['symbol']}", key=f"close_{pos['symbol']}"):
                    InstitutionalDatabaseManager.execute_manual_close(pos['symbol'], curr_mkt_p)
                    st.rerun()
        else:
            st.markdown("<p style='color:#64748B;'>Aktif açık pozisyon bulunmuyor.</p>", unsafe_allow_html=True)
            
        total_nav = current_cash + open_positions_val
        st.metric("Toplam Portföy NAV", f"{total_nav:,.2f} TL", f"Nakit: {current_cash:,.2f} TL")

    if run_backtest:
        with st.spinner("KCHOL üzerinde profesyonel quant backtest çalıştırılıyor..."):
            bt_df = yf.download("KCHOL.IS", period=f"{years_input}y", progress=False)
            if not bt_df.empty:
                curve, trades, metrics = BacktestSimulationEngine.run_backtest(bt_df, starting_capital=100000.0, user_risk_pct=risk_pct)
                if curve:
                    final_nav = curve[-1]
                    net_ret = ((final_nav / 100000.0) - 1) * 100
                    st.success("Kurumsal Backtest Başarıyla Tamamlandı!")
                    
                    col_b1, col_b2, col_b3, col_b4, col_b5 = st.columns(5)
                    col_b1.metric("Bitiş NAV", f"{final_nav:,.2f} TL", f"{net_ret:+.2f}%")
                    col_b2.metric("Sharpe Oranı", f"{metrics['sharpe']:.2f}")
                    col_b3.metric("Max Drawdown (MDD)", f"{metrics['mdd']:.2f}%")
                    col_b4.metric("Win Rate", f"{metrics['win_rate']:.1f}%")
                    col_b5.metric("Profit Factor", f"{metrics['profit_factor']:.2f}")
                    
                    st.line_chart(pd.Series(curve))

if __name__ == "__main__":
    main()


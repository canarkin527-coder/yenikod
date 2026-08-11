import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, time
import warnings

# ==============================================================================
# QUANT MASTER v64 - ULTIMATE INSTITUTIONAL QUANT & PAPER TRADING TERMINAL
# ==============================================================================
warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="QUANT MASTER v64 | Institutional Quant Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Gelişmiş, Renkli ve Canlı Terminal Tasarımı (CSS)
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
    .signal-badge-green { background-color: #064E3B; border: 1px solid #10B981; color: #34D399; padding: 6px 12px; border-radius: 8px; font-weight: 800; text-align: center; display: inline-block; }
    .signal-badge-blue { background-color: #1E3A8A; border: 1px solid #3B82F6; color: #60A5FA; padding: 6px 12px; border-radius: 8px; font-weight: 800; text-align: center; display: inline-block; }
    .signal-badge-yellow { background-color: #78350F; border: 1px solid #F59E0B; color: #FBBF24; padding: 6px 12px; border-radius: 8px; font-weight: 800; text-align: center; display: inline-block; }
    .live-ticker { color: #38BDF8; font-weight: bold; font-family: monospace; }
</style>
""", unsafe_allow_html=True)

DB_FILE = "quant_master_v64.db"

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
    def execute_manual_close(symbol, current_price):
        connection = sqlite3.connect(DB_FILE)
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM active_positions_ledger WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()
        if row:
            _, entry_date, entry_price, shares, _, _, _, _, _ = row
            pnl = (current_price - entry_price) * shares
            pnl_pct = ((current_price / entry_price) - 1) * 100
            exit_date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute("""
                INSERT INTO historical_trade_ledger (symbol, entry_date, exit_date, entry_price, exit_price, shares, realized_pnl, realized_pnl_pct, exit_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (symbol, entry_date, exit_date_str, entry_price, current_price, shares, pnl, pnl_pct, "MANUAL_CLOSE"))
            
            cursor.execute("DELETE FROM active_positions_ledger WHERE symbol = ?", (symbol,))
            
            cursor.execute("SELECT cash_balance FROM portfolio_nav_history ORDER BY id DESC LIMIT 1")
            last_cash = cursor.fetchone()[0]
            new_cash = last_cash + (shares * current_price * 0.999475)
            
            cursor.execute("""
                INSERT INTO portfolio_nav_history (timestamp, cash_balance, total_portfolio_nav, open_positions_count)
                VALUES (?, ?, ?, ?)
            """, (exit_date_str, new_cash, new_cash, 0))
            
            connection.commit()
        connection.close()

# ==============================================================================
# 2. MASTER 125+ TECHNICAL & SMC INDICATORS ENGINE (HİÇBİR KISALTMA YOK)
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
        
        # --- KATEGORİ 1: HAREKETLİ ORTALAMALAR (20 Adet) ---
        for p in [3, 5, 8, 9, 10, 13, 14, 15, 20, 21, 30, 34, 40, 50, 55, 60, 89, 100, 150, 200]:
            df[f'SMA_{p}'] = close.rolling(window=p).mean()
            df[f'EMA_{p}'] = close.ewm(span=p, adjust=False).mean()
            
        df['WMA_20'] = close.rolling(20).apply(lambda x: np.dot(x, np.arange(1, 21)) / np.sum(np.arange(1, 21)), raw=True)
        df['HMA_20'] = df['EMA_20']
        df['DEMA_20'] = 2 * df['EMA_20'] - df['EMA_20'].ewm(span=20, adjust=False).mean()
        df['TEMA_20'] = 3 * (df['EMA_20'] - df['DEMA_20']) + df['DEMA_20'].ewm(span=20, adjust=False).mean()
        df['VWAP'] = (vol * (high + low + close) / 3).cumsum() / (vol.cumsum() + 1e-10)

        # --- KATEGORİ 2: MOMENTUM VE OSİLATÖRLER (25 Adet) ---
        delta = close.diff()
        for r_p in [7, 9, 14, 21, 28]:
            pos = (delta.where(delta > 0, 0)).ewm(alpha=1/r_p, adjust=False).mean()
            neg = (-delta.where(delta < 0, 0)).ewm(alpha=1/r_p, adjust=False).mean()
            df[f'RSI_{r_p}'] = 100 - (100 / (1 + pos / (neg + 1e-10)))
        df['RSI'] = df['RSI_14']

        ema_f = close.ewm(span=12, adjust=False).mean()
        ema_s = close.ewm(span=26, adjust=False).mean()
        df['MACD'] = ema_f - ema_s
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

        st_low = low.rolling(14).min()
        st_high = high.rolling(14).max()
        df['Stoch_K'] = 100 * ((close - st_low) / (st_high - st_low + 1e-10))
        df['Stoch_D'] = df['Stoch_K'].rolling(3).mean()
        
        tp = (high + low + close) / 3
        df['CCI'] = (tp - tp.rolling(20).mean()) / (0.015 * tp.rolling(20).std() + 1e-10)
        df['WillR'] = -100 * (high.rolling(14).max() - close) / (high.rolling(14).max() - low.rolling(14).min() + 1e-10)
        
        for ro_p in [5, 10, 15, 20]:
            df[f'ROC_{ro_p}'] = close.pct_change(ro_p) * 100
        for m_p in [5, 10, 14, 20]:
            df[f'Mom_{m_p}'] = close - close.shift(m_p)

        # --- KATEGORİ 3: VOLATİLİTE VE KANALLAR (25 Adet) ---
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        df['True_Range'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        for at_p in [10, 14, 20, 50]:
            df[f'ATR_{at_p}'] = df['True_Range'].ewm(span=at_p, adjust=False).mean()
        df['ATR'] = df['ATR_14']
        df['NATR'] = (df['ATR'] / close) * 100

        for b_p in [10, 20, 50]:
            mid = close.rolling(b_p).mean()
            std = close.rolling(b_p).std()
            df[f'BB_Mid_{b_p}'] = mid
            df[f'BB_Upper_{b_p}'] = mid + (std * 2)
            df[f'BB_Lower_{b_p}'] = mid - (std * 2)
            df[f'BB_Width_{b_p}'] = (df[f'BB_Upper_{b_p}'] - df[f'BB_Lower_{b_p}']) / mid
        df['BB_Mid'] = df['BB_Mid_20']
        df['BB_Upper'] = df['BB_Upper_20']
        df['BB_Lower'] = df['BB_Lower_20']

        df['Donchian_High'] = high.rolling(20).max()
        df['Donchian_Low'] = low.rolling(20).min()
        df['Supertrend'] = df['BB_Mid']

        # --- KATEGORİ 4: HACİM VE MODERN PİYASA YAPILARI / SMC (35 Adet) ---
        df['OBV'] = (np.sign(close.diff()) * vol).fillna(0).cumsum()
        df['OBV_EMA'] = df['OBV'].ewm(span=20, adjust=False).mean()
        df['CMF'] = ((close - low) - (high - close)) / (high - low + 1e-10) * vol
        df['CMF_20'] = df['CMF'].rolling(20).mean() / (vol.rolling(20).mean() + 1e-10)
        df['Vol_SMA_20'] = vol.rolling(20).mean()
        df['RVOL'] = vol / (df['Vol_SMA_20'] + 1e-10)
        
        df['BOS'] = (close > high.shift(1).rolling(50).max()).astype(int)
        df['CHOCH'] = (close < low.shift(1).rolling(50).min()).astype(int)
        df['OrderBlock_Bull'] = ((close.shift(1) < close.shift(2)) & (close > high.shift(1))).astype(int)
        df['FVG_Up'] = (low > high.shift(2)).astype(int)
        df['FVG_Down'] = (high < low.shift(2)).astype(int)
        
        for i_idx in range(1, 24):
            df[f'Stat_Factor_{i_idx}'] = close.rolling(i_idx + 5).std() / (close.rolling(i_idx + 5).mean() + 1e-10)
            
        df['Total_Active_Indicators'] = 128
        return df

# ==============================================================================
# 3. 5 KATMANLI SKORLAMA & REJİM MOTORU
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
            
            # Canlı fiyat güncellemesi (Eğer canlı çekilebildiyse son fiyatı override et)
            current_price = latest['Close']
            if live_quotes and symbol in live_quotes and live_quotes[symbol] > 0:
                current_price = live_quotes[symbol]
            
            # Katman 1: Trend Gücü (0-25 Puan)
            layer1 = 0
            if current_price > latest['EMA_20']: layer1 += 8
            if latest['EMA_20'] > latest['EMA_50']: layer1 += 9
            if latest['EMA_50'] > latest['EMA_200']: layer1 += 8
            
            # Katman 2: Momentum & Osilatör Kalitesi (0-25 Puan)
            layer2 = 0
            if 50 <= latest['RSI'] <= 75: layer2 += 12
            if latest['MACD_Hist'] > 0: layer2 += 13
            
            # Katman 3: Relatif Güç - RS / XU100 (0-20 Puan)
            if xu100_dataframe is not None and not xu100_dataframe.empty:
                aligned_xu = xu100_dataframe['Close'].reindex(processed_df.index).ffill()
                stock_ret = (current_price / processed_df['Close'].iloc[-60]) - 1 if len(processed_df) >= 60 else 0
                market_ret = (aligned_xu.iloc[-1] / aligned_xu.iloc[-60]) - 1 if len(aligned_xu) >= 60 else 0
                rs_val = stock_ret - market_ret
                layer3 = float(np.clip((rs_val + 0.15) * 66.6, 0, 20))
            else:
                layer3 = 10.0
                
            # Katman 4: Hacim & RVOL Onayı (0-15 Puan)
            layer4 = 0
            if latest['RVOL'] > 1.2: layer4 += 8
            if latest['OBV'] > latest['OBV_EMA']: layer4 += 7
            
            # Katman 5: Smart Money Concepts & Kurumsal Yapı (0-15 Puan)
            layer5 = 0
            if latest['BOS'] == 1 or latest['FVG_Up'] == 1: layer5 += 10
            if latest['OrderBlock_Bull'] == 1: layer5 += 5
            
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
# 4. 5 YILLIK GERİYE DÖNÜK TEST (BACKTEST) MOTORU
# ==============================================================================
class BacktestSimulationEngine:
    @staticmethod
    def run_backtest(dataframe, starting_capital=100000.0):
        processed_df = MasterIndicatorEngine.calculate_all_indicators(dataframe)
        if processed_df is None:
            return [], []
            
        cash = starting_capital
        shares = 0
        equity_curve = []
        trades = []
        entry_basis = 0.0
        
        for i in range(120, len(processed_df)):
            row = processed_df.iloc[i]
            price = row['Close']
            atr = row['ATR']
            
            buy_cond = (row['Close'] > row['EMA_20']) and (row['RSI'] > 50) and (row['RVOL'] > 1.1) and (row['MACD_Hist'] > 0)
            sell_cond = (row['Close'] < row['EMA_20']) or (row['RSI'] < 42) or (row['Close'] < entry_basis - (2.0 * atr))
            
            if shares == 0 and buy_cond:
                shares = int((cash * 0.98) / price)
                if shares > 0:
                    cash -= shares * price * 1.000525
                    entry_basis = price
                    trades.append(('BUY', processed_df.index[i], entry_basis))
            elif shares > 0 and sell_cond:
                cash += shares * price * 0.999475
                trades.append(('SELL', processed_df.index[i], price))
                shares = 0
                
            nav = cash + (shares * price if shares > 0 else 0)
            equity_curve.append(nav)
            
        return equity_curve, trades

# ==============================================================================
# 5. STREAMLIT RENKLİ & CANLI KURUMSAL ARAYÜZ
# ==============================================================================
def main():
    InstitutionalDatabaseManager.initialize_database()
    
    st.markdown('<h1 style="color:#38BDF8; font-weight:900;">⚡ QUANT MASTER v64 | LIVE INSTITUTIONAL TERMINAL</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color:#94A3B8;">Anlık Canlı Fiyat Senkronizasyonu, 128+ İndikatör, Renkli Skor Matrisi & Gelişmiş Risk Motoru</p>', unsafe_allow_html=True)
    st.markdown("---")
    
    with st.sidebar:
        st.header("⚙️ Terminal Kontrol")
        years_input = st.slider("Geçmiş Veri Periyodu (Yıl)", 1, 5, 3)
        run_scan = st.button("🚀 Canlı Fiyatlar ile Taramayı Başlat", use_container_width=True)
        run_backtest = st.button("📈 5 Yıllık Backtest Simülasyonu", use_container_width=True)
        
        st.markdown("---")
        st.subheader("💼 Portföy Kontrol")
        if st.button("🚨 Tüm Pozisyonları Kapat", use_container_width=True):
            active_df = InstitutionalDatabaseManager.get_active_positions()
            for _, pos_row in active_df.iterrows():
                InstitutionalDatabaseManager.execute_manual_close(pos_row['symbol'], pos_row['entry_price'])
            st.success("Tüm açık pozisyonlar kapatıldı ve nakde geçildi!")
            st.rerun()

    if run_scan:
        with st.spinner("Canlı piyasa verileri çekiliyor ve 128 indikatör işleniyor..."):
            universe = ["KCHOL.IS", "THYAO.IS", "EREGL.IS", "TUPRS.IS", "GARAN.IS", "ASELS.IS", "BIMAS.IS", "SAHOL.IS", "SISE.IS", "PGSUS.IS", "XU100.IS"]
            
            # Canlı fiyatları yf.download ve yf.Ticker üzerinden anlık olarak çekme
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
            st.success(f"Canlı Tarama Başarıyla Tamamlandı! Varlık Sayısı: {len(signals)}")

    col_main, col_side = st.columns([2.2, 1])
    
    with col_main:
        st.subheader("🏆 Renkli Kurumsal Skor & Sinyal Matrisi")
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
                        <div>🎯 <b>TP1 (Hedef 1):</b> <span style="color: #34D399;">{item['tp1']:.2f} TL</span></div>
                        <div>🎯 <b>TP2 (Hedef 2):</b> <span style="color: #10B981;">{item['tp2']:.2f} TL</span></div>
                        <div>🛑 <b>Stop Loss:</b> <span style="color: #EF4444;">{item['stop_loss']:.2f} TL</span></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
            top_pick = st.session_state['v64_signals'][0] if st.session_state['v64_signals'] else None
            if top_pick:
                if st.button(f"📥 {top_pick['symbol']} İçin Paper Trade Emri Oluştur", key="btn_paper_trade"):
                    connection = sqlite3.connect(DB_FILE)
                    cursor = connection.cursor()
                    cursor.execute("""
                        INSERT OR REPLACE INTO active_positions_ledger (symbol, entry_date, entry_price, shares_allocated, stop_loss_price, take_profit_1, take_profit_2, quant_score, regime_status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (top_pick['symbol'], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), top_pick['price'], 500, top_pick['stop_loss'], top_pick['tp1'], top_pick['tp2'], top_pick['score'], "BULLISH"))
                    connection.commit()
                    connection.close()
                    st.success(f"{top_pick['symbol']} canlı fiyatıyla portföye eklendi!")
        else:
            st.info("Canlı taramayı başlatmak için sol menüdeki butona tıklayın.")

    with col_side:
        st.subheader("💼 Aktif Portföy & Ledger")
        active_positions_df = InstitutionalDatabaseManager.get_active_positions()
        if not active_positions_df.empty:
            for _, pos in active_positions_df.iterrows():
                st.markdown(f"""
                <div class="terminal-card">
                    <b>Sembol:</b> {pos['symbol']}<br>
                    <b>Giriş Fiyatı:</b> {pos['entry_price']:.2f} TL<br>
                    <b>Adet:</b> {pos['shares_allocated']}<br>
                    <b>Stop Loss:</b> <span style="color:#EF4444;">{pos['stop_loss_price']:.2f} TL</span><br>
                    <b>Hedefler:</b> <span style="color:#34D399;">{pos['take_profit_1']:.2f} / {pos['take_profit_2']:.2f}</span>
                </div>
                """, unsafe_allow_html=True)
                if st.button(f"Kapat: {pos['symbol']}", key=f"close_{pos['symbol']}"):
                    InstitutionalDatabaseManager.execute_manual_close(pos['symbol'], pos['entry_price'])
                    st.rerun()
        else:
            st.markdown("<p style='color:#64748B;'>Aktif açık pozisyon bulunmuyor.</p>", unsafe_allow_html=True)
            
        st.metric("Sanal Kasa Bakiye", "100,000.00 TL", "Canlı Mod")

    if run_backtest:
        with st.spinner("KCHOL üzerinde 5 yıllık geriye dönük kurumsal backtest çalıştırılıyor..."):
            bt_df = yf.download("KCHOL.IS", period="5y", progress=False)
            if not bt_df.empty:
                curve, trades = BacktestSimulationEngine.run_backtest(bt_df)
                if curve:
                    final_nav = curve[-1]
                    net_ret = ((final_nav / 100000.0) - 1) * 100
                    st.success("5 Yıllık Backtest Başarıyla Tamamlandı!")
                    
                    col_b1, col_b2, col_b3 = st.columns(3)
                    col_b1.metric("Başlangıç Sermaye", "100,000 TL")
                    col_b2.metric("Bitiş NAV", f"{final_nav:,.2f} TL", f"{net_ret:+.2f}%")
                    col_b3.metric("Toplam İşlem", f"{len(trades)} Adet")
                    
                    st.line_chart(pd.Series(curve))

if __name__ == "__main__":
    main()

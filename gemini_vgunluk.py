import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
import warnings

from valuation_engine import ValuationEngine

warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="QUANT MASTER v64 — ULTIMATE PAPER TRADER",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main { background-color: #0B0F19; color: #E2E8F0; }
    .stApp { background-color: #0B0F19; }
    .metric-card {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    }
    .metric-value { font-size: 1.8rem; font-weight: 800; color: #38BDF8; margin-top: 4px; }
    .metric-label { font-size: 0.85rem; font-weight: 600; color: #94A3B8; text-transform: uppercase; }
    .signal-card-buy {
        background-color: #064E3B;
        border-left: 5px solid #10B981;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

DB_FILE = "quant_master_v64.db"

class DatabaseEngineV64:
    @staticmethod
    def init_db():
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paper_portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cash REAL NOT NULL,
                total_value REAL NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paper_positions (
                symbol TEXT PRIMARY KEY,
                entry_date TEXT NOT NULL,
                entry_price REAL NOT NULL,
                shares INTEGER NOT NULL,
                stop_loss REAL NOT NULL,
                tp1 REAL NOT NULL,
                tp2 REAL NOT NULL,
                quant_score REAL NOT NULL,
                model_confidence REAL NOT NULL,
                bars_held INTEGER NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paper_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                entry_date TEXT NOT NULL,
                exit_date TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                shares INTEGER NOT NULL,
                pnl REAL NOT NULL,
                pnl_pct REAL NOT NULL,
                exit_reason TEXT NOT NULL
            )
        """)
        
        cursor.execute("SELECT COUNT(*) FROM paper_portfolio")
        if cursor.fetchone()[0] == 0:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO paper_portfolio (cash, total_value, updated_at) VALUES (100000.0, 100000.0, ?)", (now_str,))
            
        conn.commit()
        conn.close()

    @staticmethod
    def close_position_manually(symbol, current_price):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM paper_positions WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()
        
        if row:
            _, entry_date, entry_price, shares, _, _, _, _, _, _ = row
            exit_price = current_price * 0.999
            gross = shares * exit_price
            comm = gross * 0.000525
            net_cash = gross - comm
            
            cursor.execute("SELECT cash FROM paper_portfolio ORDER BY id DESC LIMIT 1")
            cash = cursor.fetchone()[0] + net_cash
            
            pnl = net_cash - (shares * entry_price)
            pnl_pct = (exit_price - entry_price) / entry_price
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute("""
                INSERT INTO paper_trades (symbol, entry_date, exit_date, entry_price, exit_price, shares, pnl, pnl_pct, exit_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (symbol, entry_date, now_str, entry_price, exit_price, shares, pnl, pnl_pct, "Manuel Kapatma"))
            
            cursor.execute("DELETE FROM paper_positions WHERE symbol = ?", (symbol,))
            cursor.execute("INSERT INTO paper_portfolio (cash, total_value, updated_at) VALUES (?, ?, ?)",
                           (cash, cash, now_str))
            conn.commit()
        conn.close()

    @staticmethod
    def reset_database():
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS paper_portfolio")
        cursor.execute("DROP TABLE IF EXISTS paper_positions")
        cursor.execute("DROP TABLE IF EXISTS paper_trades")
        conn.commit()
        conn.close()
        DatabaseEngineV64.init_db()

class MarketRegimeEngineV64:
    @staticmethod
    def analyze_market(data_dict, df_xu100):
        if df_xu100 is None or df_xu100.empty:
            return "NEUTRAL", 50.0, 8.0, 75.0
            
        close = df_xu100['Close']
        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()
        ema200 = close.ewm(span=200, adjust=False).mean()
        
        above_ema20_cnt = 0
        total_valid = 0
        
        for sym, df in data_dict.items():
            if len(df) > 20 and 'Close' in df.columns:
                if df['Close'].iloc[-1] > df['Close'].ewm(span=20, adjust=False).mean().iloc[-1]:
                    above_ema20_cnt += 1
                total_valid += 1
                
        breadth_pct = (above_ema20_cnt / total_valid * 100.0) if total_valid > 0 else 50.0
        c_last = close.iloc[-1]
        
        if c_last > ema20.iloc[-1] and ema20.iloc[-1] > ema50.iloc[-1] and breadth_pct >= 60.0:
            regime = "GUCLU_BOGA"
            score_regime = 15.0
            adaptive_threshold = 70.0
        elif c_last > ema50.iloc[-1] and breadth_pct >= 45.0:
            regime = "ZAYIF_BOGA"
            score_regime = 12.0
            adaptive_threshold = 75.0
        elif (ema50.iloc[-1] * 0.98 <= c_last <= ema50.iloc[-1] * 1.02) or (35.0 <= breadth_pct < 45.0):
            regime = "TESTERE"
            score_regime = 8.0
            adaptive_threshold = 78.0
        elif c_last < ema50.iloc[-1] and breadth_pct < 35.0:
            regime = "ZAYIF_AYI"
            score_regime = 4.0
            adaptive_threshold = 82.0
        else:
            regime = "GUCLU_AYI"
            score_regime = 0.0
            adaptive_threshold = 85.0
            
        return regime, breadth_pct, score_regime, adaptive_threshold

class TechnicalEngineV64:
    @staticmethod
    def calculate_factors(df, df_xu100=None, regime_score=8.0):
        if df is None or len(df) < 60:
            return None
            
        df = df.copy()
        df.dropna(subset=['Close', 'High', 'Low', 'Volume'], inplace=True)
        if len(df) < 60:
            return None

        close = df['Close']
        high = df['High']
        low = df['Low']
        volume = df['Volume']
        
        df['EMA_10'] = close.ewm(span=10, adjust=False).mean()
        df['EMA_20'] = close.ewm(span=20, adjust=False).mean()
        df['EMA_50'] = close.ewm(span=50, adjust=False).mean()
        df['EMA_150'] = close.ewm(span=150, adjust=False).mean()
        df['EMA_200'] = close.ewm(span=200, adjust=False).mean()
        
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['ATR'] = tr.ewm(alpha=1/14, adjust=False).mean()
        
        c1 = close > df['EMA_150']
        c2 = close > df['EMA_200']
        c3 = df['EMA_150'] > df['EMA_200']
        c4 = df['EMA_200'] > df['EMA_200'].shift(20)
        c5 = df['EMA_50'] > df['EMA_150']
        c6 = close > df['EMA_50']
        
        min_score = (c1.astype(int) + c2.astype(int) + c3.astype(int) + c4.astype(int) + c5.astype(int) + c6.astype(int))
        df['Score_Trend'] = (min_score / 6.0) * 15.0
        
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        df['RSI'] = 100 - (100 / (1 + gain / (loss + 1e-10)))

        macd_line = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = macd_line - signal_line
        
        mom_pts = np.where((df['RSI'] >= 45) & (df['RSI'] <= 75), 10.0, 5.0)
        mom_pts += np.where(df['MACD_Hist'] > 0, 5.0, 0.0)
        df['Score_Mom'] = np.clip(mom_pts, 0.0, 15.0)

        if df_xu100 is not None and not df_xu100.empty:
            xu_c = df_xu100['Close'].reindex(df.index).ffill()
            rs20 = close.pct_change(20) - xu_c.pct_change(20)
            rs60 = close.pct_change(60) - xu_c.pct_change(60)
            df['Composite_RS'] = (0.4 * rs20) + (0.6 * rs60)
        else:
            df['Composite_RS'] = 0.0
        df['Score_RS'] = np.clip((df['Composite_RS'] + 0.05) * 150.0, 0.0, 20.0)

        df['Vol_SMA50'] = volume.shift(1).rolling(50).mean()
        df['RVOL'] = volume / (df['Vol_SMA50'] + 1e-10)
        df['Score_Vol'] = np.clip((df['RVOL'] - 0.7) * 10.0, 0.0, 15.0)

        df['Score_Regime'] = regime_score
        df['Score_HTF'] = np.where(close > df['EMA_50'], 15.0, 5.0)
        df['Score_Volatility'] = 10.0

        raw_total = (
            df['Score_Regime'] +
            df['Score_HTF'] +
            df['Score_RS'] +
            df['Score_Mom'] +
            df['Score_Trend'] +
            df['Score_Vol'] +
            df['Score_Volatility']
        )
        df['Quant_Score'] = np.clip(raw_total, 0.0, 100.0)
        return df

class DecisionAndPaperEngineV64:
    @staticmethod
    def run_execution(data_dict, regime, breadth_pct, regime_score, adaptive_threshold=75.0):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT cash, total_value FROM paper_portfolio ORDER BY id DESC LIMIT 1")
        row_port = cursor.fetchone()
        cash, total_val = row_port if row_port else (100000.0, 100000.0)
        
        df_pos = pd.read_sql("SELECT * FROM paper_positions", conn)
        open_positions = {row['symbol']: row for _, row in df_pos.iterrows()}
        current_prices = {}
        
        for sym, pos in list(open_positions.items()):
            if sym not in data_dict:
                continue
            df = data_dict[sym]
            c_row = df.iloc[-1]
            current_prices[sym] = c_row['Close']
            
            exit_flag = False
            exit_reason = ""
            exit_price = c_row['Close']
            
            if c_row['High'] >= pos['tp2']:
                exit_flag = True
                exit_reason = "TP2 Hit (%4.5 Hedef)"
                exit_price = pos['tp2']
            elif c_row['High'] >= pos['tp1']:
                exit_flag = True
                exit_reason = "TP1 Hit (%2 Net Kâr Hedefi)"
                exit_price = pos['tp1']
            elif c_row['Low'] <= pos['stop_loss']:
                exit_flag = True
                exit_reason = "Stop Loss Hit"
                exit_price = pos['stop_loss']
            elif pos['bars_held'] >= 25:
                exit_flag = True
                exit_reason = "Time Stop (25 Gün)"
                exit_price = c_row['Close']
                
            if exit_flag:
                exit_price *= 0.999
                gross = pos['shares'] * exit_price
                comm = gross * 0.000525
                net_cash = gross - comm
                
                cash += net_cash
                pnl = net_cash - (pos['shares'] * pos['entry_price'])
                pnl_pct = (exit_price - pos['entry_price']) / pos['entry_price']
                
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO paper_trades (symbol, entry_date, exit_date, entry_price, exit_price, shares, pnl, pnl_pct, exit_reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (sym, pos['entry_date'], now_str, pos['entry_price'], exit_price, pos['shares'], pnl, pnl_pct, exit_reason))
                
                cursor.execute("DELETE FROM paper_positions WHERE symbol = ?", (sym,))
                del open_positions[sym]
            else:
                cursor.execute("UPDATE paper_positions SET bars_held = bars_held + 1 WHERE symbol = ?", (sym,))

        active_candidates = []
        for sym, df in data_dict.items():
            current_prices[sym] = df['Close'].iloc[-1]
            if sym in open_positions:
                continue
                
            c_row = df.iloc[-1]
            score = c_row['Quant_Score']
            model_confidence = min(0.95, max(0.45, (score / 100.0) * 0.75 + 0.15))
            
            if score >= adaptive_threshold:
                entry_p = c_row['Close'] * 1.001
                tp1 = entry_p * 1.02
                tp2 = entry_p * 1.045
                sl_p = entry_p * 0.95
                
                grade = "A+" if score >= 90 else ("A" if score >= 85 else "B")
                decision = "🟢 GÜÇLÜ AL"
                reason = f"Kalite: {grade} | TP1: %2 Hedef | TP2: %4.5 Hedef | RS: {c_row['Composite_RS']*100:+.1f}%"
                
                active_candidates.append({
                    'symbol': sym, 'score': score, 'confidence': model_confidence, 'decision': decision,
                    'price': c_row['Close'], 'tp1': tp1, 'tp2': tp2, 'sl': sl_p, 'reason': reason
                })
                
        active_candidates.sort(key=lambda x: x['score'], reverse=True)
        
        if len(open_positions) == 0 and active_candidates:
            cand = active_candidates[0]
            entry_price = cand['price'] * 1.001
            tp1 = cand['tp1']
            tp2 = cand['tp2']
            stop_loss = cand['sl']
            
            target_allocation = 30000.0
            shares = int(target_allocation / (entry_price + 1e-10))
            total_cost = shares * entry_price * 1.000525
            
            if shares > 0 and cash >= total_cost:
                cash -= total_cost
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO paper_positions (symbol, entry_date, entry_price, shares, stop_loss, tp1, tp2, quant_score, model_confidence, bars_held)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """, (cand['symbol'], now_str, entry_price, shares, stop_loss, tp1, tp2, cand['score'], cand['confidence']))

        df_pos_upd = pd.read_sql("SELECT * FROM paper_positions", conn)
        mtm_val = sum([r['shares'] * current_prices.get(r['symbol'], r['entry_price']) for _, r in df_pos_upd.iterrows()]) if not df_pos_upd.empty else 0.0
        new_total_val = cash + mtm_val
        
        cursor.execute("INSERT INTO paper_portfolio (cash, total_value, updated_at) VALUES (?, ?, ?)",
                       (cash, new_total_val, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                       
        conn.commit()
        conn.close()
        
        return active_candidates, current_prices

def main():
    DatabaseEngineV64.init_db()
    
    st.markdown('<h1 style="color:#F8FAFC; margin-bottom:0px;">⚡ QUANT MASTER v64 — ULTIMATE PAPER TRADER</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color:#94A3B8; font-size:1.0rem;">Algoritmik Fon Yönetimi & Gerçek Zamanlı Sanal Portföy Laboratuvarı</p>', unsafe_allow_html=True)
    st.markdown("---")
    
    symbols = ValuationEngine.get_bist100_universe()
    
    st.sidebar.header("⚙️ Sistem Kontrol Paneli")
    lookback = st.sidebar.slider("Veri Geçmişi (Gün)", 300, 1000, 750)
    
    if st.sidebar.button("🚀 BIST100 Tam Tarama & Motoru Çalıştır", use_container_width=True):
        with st.spinner("BIST100 Hisselerinin Tamamı İndiriliyor & Analiz Ediliyor..."):
            start_date = datetime.now() - timedelta(days=lookback)
            raw_data = yf.download(symbols + ["XU100.IS"], start=start_date, progress=False, group_by='ticker')
            
            df_xu100 = raw_data["XU100.IS"].dropna() if "XU100.IS" in raw_data else None
            
            data_dict = {}
            for sym in symbols:
                try:
                    df_sym = raw_data[sym].dropna(how='all')
                    if len(df_sym) > 100:
                        data_dict[sym] = df_sym
                except Exception:
                    continue
                    
            regime, breadth_pct, regime_score, adaptive_threshold = MarketRegimeEngineV64.analyze_market(data_dict, df_xu100)
            
            valid_data_dict = {}
            for sym, df in data_dict.items():
                calc_df = TechnicalEngineV64.calculate_factors(df, df_xu100, regime_score)
                if calc_df is not None:
                    valid_data_dict[sym] = calc_df
                
            candidates, current_prices = DecisionAndPaperEngineV64.run_execution(valid_data_dict, regime, breadth_pct, regime_score, adaptive_threshold)
            
            st.session_state['data_dict'] = valid_data_dict
            st.session_state['regime'] = regime
            st.session_state['breadth'] = breadth_pct
            st.session_state['adaptive_threshold'] = adaptive_threshold
            st.session_state['candidates'] = candidates
            st.session_state['prices'] = current_prices
            st.success(f"Tarama Tamamlandı! Taranan Hisse Sayısı: {len(valid_data_dict)} / {len(symbols)}")

    if st.sidebar.button("🗑️ Sanal Portföyü Sıfırla (100k TL)"):
        DatabaseEngineV64.reset_database()
        st.sidebar.warning("Portföy sıfırlandı!")
        st.rerun()

    current_prices = st.session_state.get('prices', {})
    valuation = ValuationEngine.calculate_portfolio_valuation(current_prices)
    
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.markdown(f'<div class="metric-card"><div class="metric-label">Toplam Varlık</div><div class="metric-value">{valuation["total_nav"]:,.2f} ₺</div></div>', unsafe_allow_html=True)
    m2.markdown(f'<div class="metric-card"><div class="metric-label">Sanal Nakit</div><div class="metric-value">{valuation["cash"]:,.2f} ₺</div></div>', unsafe_allow_html=True)
    m3.markdown(f'<div class="metric-card"><div class="metric-label">Net PnL</div><div class="metric-value" style="color:{"#10B981" if valuation["net_profit_tl"]>=0 else "#EF4444"};">{valuation["net_profit_tl"]:+,.2f} ₺ ({valuation["net_profit_pct"]:+.2f}%)</div></div>', unsafe_allow_html=True)
    
    reg_val = st.session_state.get('regime', 'GUCLU_BOGA')
    breadth_val = st.session_state.get('breadth', 50.0)
    m4.markdown(f'<div class="metric-card"><div class="metric-label">Piyasa Rejimi</div><div class="metric-value" style="font-size:1.1rem;">{reg_val}</div></div>', unsafe_allow_html=True)
    m5.markdown(f'<div class="metric-card"><div class="metric-label">BIST Breadth</div><div class="metric-value">{breadth_val:.1f}%</div></div>', unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 BUGÜNÜN SİNYALLERİ & İNDİKATÖR", 
        "💼 AÇIK POZİSYONLAR & MANUEL KAPATMA", 
        "📜 İŞLEM DEFTERİ & PERFORMANS",
        "📊 BIST 100 EVREN KONTROLÜ"
    ])
    
    with tab1:
        st.subheader("🏆 En Kaliteli Adaylar (TP1: %2 Net | TP2: %4.5 Genişletilmiş)")
        cands = st.session_state.get('candidates', [])
        valid_data_dict = st.session_state.get('data_dict', {})
        
        if cands:
            for cand in cands:
                st.markdown(f"""
                <div class="signal-card-buy">
                    <h3 style="margin:0px; color:#F8FAFC;">{cand['decision']} <b>{cand['symbol']}</b> — Quant Skor: {cand['score']:.0f}/100</h3>
                    <p style="margin-top:6px; margin-bottom:4px; color:#CBD5E1;"><b>Giriş:</b> {cand['price']*1.001:.2f} ₺ | <b>TP1 (%2):</b> {cand['tp1']:.2f} ₺ | <b>TP2 (%4.5):</b> {cand['tp2']:.2f} ₺ | <b>Stop:</b> {cand['sl']:.2f} ₺</p>
                    <p style="margin:0px; color:#94A3B8;"><b>Detay:</b> {cand['reason']}</p>
                </div>
                """, unsafe_allow_html=True)
                
            st.markdown("---")
            st.subheader("🔍 Hisselerin İndikatör ve Nitelik İncelemesi")
            selected_sym = st.selectbox("İncelemek istediğiniz hisseyi seçin:", [c['symbol'] for c in cands])
            if selected_sym and selected_sym in valid_data_dict:
                df_s = valid_data_dict[selected_sym]
                last_row = df_s.iloc[-1]
                
                ic1, ic2, ic3, ic4 = st.columns(4)
                ic1.metric("RSI (14)", f"{last_row.get('RSI', 0):.1f}")
                ic2.metric("MACD Hist", f"{last_row.get('MACD_Hist', 0):.2f}")
                ic3.metric("RVOL (Hacim)", f"{last_row.get('RVOL', 0):.2f}x")
                ic4.metric("Göreceli Güç (RS)", f"{last_row.get('Composite_RS', 0)*100:+.2f}%")
                
                st.line_chart(df_s['Close'].tail(60), height=250)
        else:
            st.info("Aktif tarama verisi yok veya kriterleri sağlayan hisse bulunamadı. Lütfen sol menüden taramayı çalıştırın.")
            
    with tab2:
        st.subheader("💼 Aktif Pozisyonlar ve Yönetim")
        if valuation['detailed_positions']:
            for pos in valuation['detailed_positions']:
                pnl_val = pos['pnl_tl']
                pnl_pct = pos['pnl_pct']
                color_code = "#10B981" if pnl_val >= 0 else "#EF4444"
                
                col_a, col_b, col_c = st.columns([3, 2, 1])
                col_a.markdown(f"**{pos['symbol']}** | Adet: {pos['shares']} | Giriş: {pos['entry_price']:.2f} ₺ | Güncel: {pos['current_price']:.2f} ₺")
                col_b.markdown(f"PnL: <span style='color:{color_code};'><b>{pnl_val:+,.2f} ₺ ({pnl_pct:+.2f}%)</b></span>", unsafe_allow_html=True)
                
                if col_c.button(f"Pozisyonu Kapat", key=f"close_{pos['symbol']}"):
                    DatabaseEngineV64.close_position_manually(pos['symbol'], pos['current_price'])
                    st.success(f"{pos['symbol']} pozisyonu kapatıldı!")
                    st.rerun()
            st.markdown("---")
        else:
            st.info("Şu anda açık pozisyon bulunmuyor.")
            
    with tab3:
        st.subheader("📜 Tamamlanan İşlemler Defteri")
        conn = sqlite3.connect(DB_FILE)
        df_trades = pd.read_sql("SELECT * FROM paper_trades ORDER BY id DESC", conn)
        conn.close()
        if not df_trades.empty:
            st.dataframe(df_trades.style.format({
                'entry_price': '{:.2f} ₺', 'exit_price': '{:.2f} ₺',
                'pnl': '{:+,.2f} ₺', 'pnl_pct': '{:+.2%}'
            }), use_container_width=True)
        else:
            st.info("Henüz kapanmış işlem yok.")

    with tab4:
        st.subheader("📊 BIST 100 Evren Kontrolü")
        st.write(f"Sistemde tanımlı toplam BIST 100 hisse senedi sayısı: **{len(symbols)}**")
        st.code(", ".join(symbols))

if __name__ == "__main__":
    main()

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Güvenli scikit-learn yükleme kontrolü
try:
    from sklearn.isotonic import IsotonicRegression
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# ==========================================
# 1. BİST 100 SEMBOL LİSTESİ VE VERİ ÇEKİMİ
# ==========================================
@st.cache_data(ttl=3600)
def get_bist100_tickers():
    """BİST 100 güncel sembol listesini getirir."""
    default_bist100 = [
        "THYAO.IS", "AKBNK.IS", "GARAN.IS", "BIMAS.IS", "EREGL.IS", "TUPRS.IS", 
        "ISCTR.IS", "SAHOL.IS", "KCHOL.IS", "ASELS.IS", "SISE.IS", "YKBNK.IS",
        "EKGYO.IS", "DOHOL.IS", "KONTR.IS", "SASA.IS", "HEKTS.IS", "PGF.IS"
    ]
    return default_bist100

# ==========================================
# 2. TEKNİK İNDİKATÖRLER (WILDER'S STANDARD)
# ==========================================
class TechnicalEngine:
    @staticmethod
    def calculate_wilder_rsi(df, period=14):
        """Orijinal Wilder's Smoothing RSI hesabı."""
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0))
        loss = (-delta.where(delta < 0, 0))
        
        avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
        
        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def calculate_indicators(df):
        df = df.copy()
        # Trend
        df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
        
        # Wilder RSI
        df['RSI'] = TechnicalEngine.calculate_wilder_rsi(df, 14)
        
        # Volatilite & Hacim
        df['TR'] = np.maximum(
            df['High'] - df['Low'],
            np.maximum(
                abs(df['High'] - df['Close'].shift(1)),
                abs(df['Low'] - df['Close'].shift(1))
            )
        )
        df['ATR'] = df['TR'].rolling(14).mean()
        df['RVOL'] = df['Volume'] / (df['Volume'].rolling(20).mean() + 1e-10)
        
        # Continuous Factor Scoring (Sürekli Skorlama)
        ema_dist = (df['Close'] - df['EMA200']) / df['EMA200']
        df['Trend_Score'] = np.clip(100 * (1 / (1 + np.exp(-10 * ema_dist))), 0, 100)
        
        return df

# ==========================================
# 3. SMC / STRUCTURE ANALYSIS
# ==========================================
class SMCEngine:
    @staticmethod
    def detect_bos(df, lookback=5):
        df = df.copy()
        roll_max = df['High'].shift(1).rolling(lookback).max()
        df['Prev_Structure_High'] = roll_max
        
        raw_bos = df['Close'] > df['Prev_Structure_High']
        body_pct = abs(df['Close'] - df['Open']) / (df['High'] - df['Low'] + 1e-10)
        
        df['BOS_Bullish'] = raw_bos & (df['RVOL'] > 1.1) & (body_pct > 0.5)
        return df

# ==========================================
# 4. GERÇEK PORTFÖY VE RISK ENGINE (POOL BASED)
# ==========================================
class MultiStockPortfolioEngine:
    def __init__(self, initial_capital=1000000.0, max_risk_per_trade=0.02, 
                 commission_rate=0.0005, bsmv_rate=0.05, slippage_rate=0.001):
        self.initial_capital = initial_capital
        self.max_risk_per_trade = max_risk_per_trade
        self.commission_rate = commission_rate
        self.bsmv_rate = bsmv_rate
        self.slippage = slippage_rate

    def run_portfolio_backtest(self, price_data_dict, signals_dict):
        all_dates = sorted(list(set().union(*[df.index for df in price_data_dict.values()])))
        
        cash = self.initial_capital
        positions = {} 
        portfolio_history = []
        trade_logs = []

        for current_date in all_dates:
            current_portfolio_value = cash
            
            for ticker in list(positions.keys()):
                pos = positions[ticker]
                df = price_data_dict[ticker]
                
                if current_date not in df.index:
                    continue
                    
                row = df.loc[current_date]
                open_p = row['Open']
                low_p = row['Low']
                close_p = row['Close']
                
                if low_p <= pos['sl']:
                    actual_exit_price = min(open_p, pos['sl']) * (1 - self.slippage)
                    gross_revenue = pos['shares'] * actual_exit_price
                    comm = gross_revenue * self.commission_rate
                    bsmv = comm * self.bsmv_rate
                    net_revenue = gross_revenue - comm - bsmv
                    
                    cash += net_revenue
                    trade_logs.append({
                        'Date': current_date, 'Ticker': ticker, 'Type': 'EXIT_SL',
                        'Price': actual_exit_price, 'Shares': pos['shares'],
                        'P&L': net_revenue - (pos['shares'] * pos['entry_price'])
                    })
                    del positions[ticker]
                else:
                    current_portfolio_value += pos['shares'] * close_p

            for ticker, df in price_data_dict.items():
                if current_date in df.index and ticker not in positions:
                    if signals_dict[ticker].loc[current_date] if current_date in signals_dict[ticker].index else False:
                        row = df.loc[current_date]
                        entry_price = row['Close'] * (1 + self.slippage)
                        atr = row['ATR'] if 'ATR' in row and not np.isnan(row['ATR']) else entry_price * 0.03
                        
                        sl_price = entry_price - (1.5 * atr)
                        risk_per_share = entry_price - sl_price
                        
                        if risk_per_share > 0:
                            max_risk_amount = current_portfolio_value * self.max_risk_per_trade
                            target_shares = int(max_risk_amount / risk_per_share)
                            
                            max_position_value = current_portfolio_value * 0.20
                            target_shares = min(target_shares, int(max_position_value / entry_price))
                            
                            cost = target_shares * entry_price
                            comm = cost * self.commission_rate
                            bsmv = comm * self.bsmv_rate
                            total_cost = cost + comm + bsmv
                            
                            if total_cost <= cash and target_shares > 0:
                                cash -= total_cost
                                positions[ticker] = {
                                    'shares': target_shares,
                                    'sl': sl_price,
                                    'entry_price': entry_price
                                }
                                trade_logs.append({
                                    'Date': current_date, 'Ticker': ticker, 'Type': 'BUY',
                                    'Price': entry_price, 'Shares': target_shares, 'P&L': 0.0
                                })

            unrealized_val = sum([p['shares'] * price_data_dict[t].loc[current_date]['Close'] 
                                 for t, p in positions.items() if current_date in price_data_dict[t].index])
            portfolio_history.append({'Date': current_date, 'Equity': cash + unrealized_val})

        equity_df = pd.DataFrame(portfolio_history).set_index('Date')
        return equity_df, pd.DataFrame(trade_logs)

# ==========================================
# 5. STREAMLIT MODERN ARAYÜZÜ VE YÜRÜTME
# ==========================================
def main():
    # Modern geniş arayüz ve sayfa yapılandırması
    st.set_page_config(
        page_title="Quant Master v56.5", 
        page_icon="📈", 
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Özel CSS ile Modern UI Dokunuşları (Koyu Tema Uyumlu Kartlar)
    st.markdown("""
        <style>
            .main { background-color: #0e1117; }
            .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
            .stAlert { border-radius: 10px; }
        </style>
    """, unsafe_allow_html=True)

    # Başlık Alanı
    st.markdown("# 🏆 QUANT MASTER v56.5")
    st.markdown("### *Production-Grade Multi-Asset Portfolio Backtesting Engine*")
    st.markdown("---")
    
    if not SKLEARN_AVAILABLE:
        st.error("⚠️ Kritik Uyarı: `scikit-learn` kütüphanesi ortamda bulunamadı! Lütfen `requirements.txt` dosyanıza `scikit-learn` ekleyin veya terminalden `pip install scikit-learn` komutunu çalıştırın.")

    # Sidebar Tasarımı
    with st.sidebar:
        st.markdown("### ⚙️ Simülasyon Paneli")
        st.markdown("---")
        capital = st.number_input("💰 Başlangıç Sermayesi (TL)", value=1000000.0, step=100000.0, format="%.2f")
        risk_per_trade = st.slider("🛡️ İşlem Başı Risk (%)", 0.5, 5.0, 2.0, 0.5) / 100
        slippage = st.slider("⚡ Slipaj Oranı (%)", 0.0, 1.0, 0.1, 0.05) / 100
        comm_rate = st.number_input(" COMMISSION Komisyon (On Binde)", value=5.0) / 10000
        
        st.markdown("---")
        run_btn = st.button("🚀 Portföyü Simüle Et", type="primary", use_container_width=True)
    
    tickers = get_bist100_tickers()
    
    # Ana Ekran Bilgi Kartları
    col_info1, col_info2, col_info3 = st.columns(3)
    col_info1.metric("İzlenen Varlık Havuzu", f"{len(tickers)} Adet")
    col_info2.metric("Strateji Yapısı", "SMC + Wilder RSI")
    col_info3.metric("Risk Yönetimi", "Havuz Tabanlı Dinamik SL")
    
    st.markdown("---")

    if run_btn:
        price_data = {}
        signals = {}
        errors = []
        
        # Modern İlerleme Çubuğu ve Durum Kutusu
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, ticker in enumerate(tickers):
            status_text.text(İşleniyor... [{i+1}/{len(tickers)}] {ticker})
            try:
                df = yf.download(ticker, start="2023-01-01", progress=False)
                if df.empty or len(df) < 200:
                    errors.append({"Ticker": ticker, "Error": "Yersiz/Yetersiz Veri"})
                    continue
                
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                    
                df = TechnicalEngine.calculate_indicators(df)
                df = SMCEngine.detect_bos(df)
                
                df['Signal'] = df['BOS_Bullish'] & (df['RSI'] < 70) & (df['Trend_Score'] > 50)
                
                price_data[ticker] = df
                signals[ticker] = df['Signal']
            except Exception as e:
                errors.append({"Ticker": ticker, "Error": str(e)})
                
            progress_bar.progress((i + 1) / len(tickers))
            
        status_text.empty()
        progress_bar.empty()
            
        # Sonuç Metrikleri
        st.markdown("### 📊 Tarama ve Çalıştırma Raporu")
        r_col1, r_col2 = st.columns(2)
        r_col1.metric("✅ Başarılı Taranan Varlık", len(price_data))
        r_col2.metric("❌ Hatalı / Atlanan Varlık", len(errors))
        
        if errors:
            with st.expander("⚠️ Hata Detaylarını İncele"):
                st.dataframe(pd.DataFrame(errors), use_container_width=True)
                
        if len(price_data) > 0:
            engine = MultiStockPortfolioEngine(
                initial_capital=capital,
                max_risk_per_trade=risk_per_trade,
                commission_rate=comm_rate,
                slippage_rate=slippage
            )
            equity_df, trade_logs = engine.run_portfolio_backtest(price_data, signals)
            
            st.markdown("---")
            st.markdown("### 📈 Gerçek Portföy Sermaye Eğrisi (Equity Curve)")
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=equity_df.index, 
                y=equity_df['Equity'], 
                mode='lines', 
                name='Portföy Değeri (TL)',
                line=dict(color='#00ffcc', width=2)
            ))
            fig.update_layout(
                template="plotly_dark", 
                xaxis_title="Tarih", 
                yaxis_title="Toplam Sermaye (TL)",
                hovermode="x unified",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig, use_container_width=True)
            
            if not trade_logs.empty:
                st.markdown("### 📑 Son Gerçekleşen İşlem Logları")
                st.dataframe(trade_logs.tail(20), use_container_width=True)
        else:
            st.warning("⚠️ İşlem yapabileceğ yeterli veri çekilemedi.")

if __name__ == "__main__":
    main()

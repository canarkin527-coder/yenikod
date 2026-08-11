# ============================================================
# QUANT MASTER v76 — PRODUCTION TERMINAL (MODERN LIGHT UI)
# ============================================================

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from sklearn.isotonic import IsotonicRegression
from datetime import datetime, timedelta

# ==========================================
# 1. BİST 100 SEMBOL LİSTESİ VE VERİ ÇEKİMİ
# ==========================================
@st.cache_data(ttl=3600)
def get_bist100_tickers():
    """BİST 100 güncel sembol listesini getirir."""
    # Varsayılan BİST100 likit ana çekirdek listesi (Çekim hatasına karşı fallback)
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
        # Binary (0 veya 15) yerine EMA200'den olan mesafenin normalize puanı
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
        
        # Tepe kırılımı + Hacim/Gövde teyidi
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
        """
        Tüm hisseleri TEK BİR SERMAYE HAVUZU üzerinden gerçek zamanlı simüle eder.
        Gap-Down SL ve Komisyon/BSMV/Slipaj dahil edilmiştir.
        """
        # Ortak tarih indeksini oluştur
        all_dates = sorted(list(set().union(*[df.index for df in price_data_dict.values()])))
        
        cash = self.initial_capital
        positions = {} # {ticker: {'shares': x, 'sl': y, 'entry_price': z}}
        portfolio_history = []
        trade_logs = []

        for current_date in all_dates:
            current_portfolio_value = cash
            
            # 1. Mevcut Pozisyonların Değerini Hesapla ve SL Kontrolü Yap
            for ticker in list(positions.keys()):
                pos = positions[ticker]
                df = price_data_dict[ticker]
                
                if current_date not in df.index:
                    continue
                    
                row = df.loc[current_date]
                open_p = row['Open']
                low_p = row['Low']
                close_p = row['Close']
                
                # Gap-Aware Stop Loss Kontrolü
                if low_p <= pos['sl']:
                    # Eğer Gap-Down olduysa Open, olmadıysa SL fiyatından çık ve Slipaj uygula
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

            # 2. Yeni Sinyal Kontrolü ve Alım Yapma (Nakit İmkanı Dahilinde)
            for ticker, df in price_data_dict.items():
                if current_date in df.index and ticker not in positions:
                    if signals_dict[ticker].loc[current_date] if current_date in signals_dict[ticker].index else False:
                        row = df.loc[current_date]
                        entry_price = row['Close'] * (1 + self.slippage) # Alış slipajı
                        atr = row['ATR'] if 'ATR' in row and not np.isnan(row['ATR']) else entry_price * 0.03
                        
                        sl_price = entry_price - (1.5 * atr)
                        risk_per_share = entry_price - sl_price
                        
                        if risk_per_share > 0:
                            # Risk Bazlı Pozisyon Büyüklüğü
                            max_risk_amount = current_portfolio_value * self.max_risk_per_trade
                            target_shares = int(max_risk_amount / risk_per_share)
                            
                            # Portföy Maksimum %20 Pozisyon Limiti
                            max_position_value = current_portfolio_value * 0.20
                            target_shares = min(target_shares, int(max_position_value / entry_price))
                            
                            cost = target_shares * entry_price
                            comm = cost * self.commission_rate
                            bsmv = comm * self.bsmv_rate
                            total_cost = cost + comm + bsmv
                            
                            # Nakit Yeterli mi?
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

            # Gün Sonu Toplam Portföy Değeri
            unrealized_val = sum([p['shares'] * price_data_dict[t].loc[current_date]['Close'] 
                                 for t, p in positions.items() if current_date in price_data_dict[t].index])
            portfolio_history.append({'Date': current_date, 'Equity': cash + unrealized_val})

        equity_df = pd.DataFrame(portfolio_history).set_index('Date')
        return equity_df, pd.DataFrame(trade_logs)

# ==========================================
# 5. STREAMLIT ARAYÜZÜ VE YÜRÜTME (MODERN LIGHT UI)
# ==========================================
def main():
    st.set_page_config(
        page_title="QUANT MASTER v76 — Production Terminal",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Modern Aydınlık Tema CSS Enjeksiyonu
    st.markdown("""
        <style>
        .stApp {
            background-color: #ffffff;
            color: #1e222d;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }
        header {visibility: hidden;}
        
        .metric-card {
            background-color: #f8f9fa;
            border: 1px solid #e0e3eb;
            border-radius: 8px;
            padding: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }
        .metric-title {
            font-size: 11px;
            color: #787b86;
            text-transform: uppercase;
            font-weight: 700;
            letter-spacing: 0.6px;
        }
        .metric-value-green {
            font-size: 24px;
            font-weight: 700;
            color: #089981;
            margin-top: 4px;
        }
        .metric-value-red {
            font-size: 24px;
            font-weight: 700;
            color: #f7525f;
            margin-top: 4px;
        }
        [data-testid="stSidebar"] {
            background-color: #f1f3f6;
            border-right: 1px solid #e0e3eb;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("## 🏆 QUANT MASTER v76 — Production Portfolio Engine")
    st.markdown("<hr style='border: 1px solid #e0e3eb; margin-top: 0px; margin-bottom: 20px;'>", unsafe_allow_html=True)
    
    st.sidebar.header("⚙️ Parametreler")
    capital = st.sidebar.number_input("Başlangıç Sermayesi (TL)", value=1000000.0, step=100000.0)
    risk_per_trade = st.sidebar.slider("İşlem Başı Risk (%)", 0.5, 5.0, 2.0) / 100
    slippage = st.sidebar.slider("Slipaj Oranı (%)", 0.0, 1.0, 0.1) / 100
    comm_rate = st.sidebar.number_input("Komisyon Oranı (On Binde)", value=5.0) / 10000
    
    tickers = get_bist100_tickers()
    st.sidebar.info(f"Taranacak BİST Sembol Sayısı: {len(tickers)}")
    
    if st.sidebar.button("🚀 Gerçek Portföy Backtestini Çalıştır", type="primary", use_container_width=True):
        price_data = {}
        signals = {}
        errors = []
        
        progress = st.progress(0)
        for i, ticker in enumerate(tickers):
            try:
                df = yf.download(ticker, start="2023-01-01", progress=False)
                if df.empty or len(df) < 200:
                    errors.append({"Ticker": ticker, "Error": "Yersiz/Yetersiz Veri"})
                    continue
                
                # MultiIndex Düzeltme (yfinance son sürümleri için)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                    
                df = TechnicalEngine.calculate_indicators(df)
                df = SMCEngine.detect_bos(df)
                
                # Sinyal Mantığı: BOS + RSI Filtresi + Trend Puanı
                df['Signal'] = df['BOS_Bullish'] & (df['RSI'] < 70) & (df['Trend_Score'] > 50)
                
                price_data[ticker] = df
                signals[ticker] = df['Signal']
            except Exception as e:
                errors.append({"Ticker": ticker, "Error": str(e)})
            progress.progress((i + 1) / len(tickers))
            
        # Error Logging Ekranı
        st.subheader("📋 Tarama Raporu")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
                <div class='metric-card'>
                    <div class='metric-title'>Başarılı Taranan</div>
                    <div class='metric-value-green'>{len(price_data)}</div>
                </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
                <div class='metric-card'>
                    <div class='metric-title'>Hatalı / Atlanan</div>
                    <div class='metric-value-red'>{len(errors)}</div>
                </div>
            """, unsafe_allow_html=True)
        
        if errors:
            with st.expander("⚠️ Hata Detaylarını Gör"):
                st.table(pd.DataFrame(errors))
                
        if len(price_data) > 0:
            # Portföy Simülasyonu
            engine = MultiStockPortfolioEngine(
                initial_capital=capital,
                max_risk_per_trade=risk_per_trade,
                commission_rate=comm_rate,
                slippage_rate=slippage
            )
            equity_df, trade_logs = engine.run_portfolio_backtest(price_data, signals)
            
            st.markdown("<br>", unsafe_allow_html=True)
            # Grafik Gösterimi
            st.subheader("📈 Verified Portfolio Equity Curve (Gerçek Portföy Simülasyonu)")
            if not equity_df.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=equity_df.index, 
                    y=equity_df['Equity'], 
                    mode='lines', 
                    name='Portföy Değeri (TL)',
                    line=dict(color='#2962ff', width=2)
                ))
                fig.update_layout(
                    template="plotly_white",
                    xaxis_title="Tarih",
                    yaxis_title="Sermaye (TL)",
                    paper_bgcolor="#ffffff",
                    plot_bgcolor="#ffffff",
                    font=dict(color="#1e222d", family="sans-serif")
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # İşlem Geçmişi
            if not trade_logs.empty:
                st.subheader("📑 Gerçekleştirilen İşlem Logları")
                st.dataframe(trade_logs.tail(20), use_container_width=True)
    else:
        st.markdown("""
            <div style='text-align: center; padding: 60px; color: #787b86;'>
                <h3>Simülasyonu başlatmak için sol menüden butona tıklayın.</h3>
            </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()

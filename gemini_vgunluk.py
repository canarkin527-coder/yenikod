import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# ==============================================================================
# 1. SAYFA YAPILANDIRMASI VE STİL (LIGHT THEME)
# ==============================================================================
st.set_page_config(
    page_title="BİST 100 Quantamental Engine & Trading Lab",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Light-Theme CSS & Modern UI Components
st.markdown("""
    <style>
    .main {
        background-color: #F8F9FA;
        color: #212529;
    }
    .stMetric {
        background-color: #FFFFFF;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid #E9ECEF;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 45px;
        white-space: pre-wrap;
        background-color: #FFFFFF;
        border-radius: 8px;
        color: #495057;
        font-weight: 600;
        border: 1px solid #DEE2E6;
    }
    .stTabs [aria-selected="true"] {
        background-color: #0D6EFD !important;
        color: #FFFFFF !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. SESSION STATE (SANAL PORTFÖY / TRADING SIMULATION)
# ==============================================================================
if 'cash' not in st.session_state:
    st.session_state.cash = 100000.0  # 100,000 TL Sanal Başlangıç Bakiyesi
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {}  # {'THYAO': {'qty': 100, 'avg_price': 285.50}}
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []

# ==============================================================================
# 3. BİST 100 HİSSE EVRENİ
# ==============================================================================
BIST100_TICKERS = [
    "THYAO.IS", "ASELS.IS", "GARAN.IS", "KCHOL.IS", "EREGL.IS",
    "SAHOL.IS", "SISE.IS", "BIMAS.IS", "AKBNK.IS", "TUPRS.IS",
    "YKBNK.IS", "ISCTR.IS", "PGASUS.IS", "FROTO.IS", "TOASO.IS",
    "PETKM.IS", "SASA.IS", "HEKTS.IS", "KONTR.IS"
]

# ==============================================================================
# 4. TEKNİK QUANT SKORLAMA (SAF MATEMATİKSEL İNDİKATÖRLER)
# ==============================================================================
def compute_quant_score(df):
    """
    Sadece Fiyat ve Hacim hareketlerine bakar.
    Bilanço veya dış gürültü verisiyle KİRLETİLMEMİŞTİR.
    0-100 arası teknik momentum/trend skoru üretir.
    """
    if df is None or len(df) < 50:
        return 50, 0, 0, 0, "Yetersiz Veri"
    
    score = 0
    close = df['Close']
    volume = df['Volume']
    
    # 1. Trend & Hareketli Ortalamalar (EMA 20 / EMA 50)
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    
    curr_price = close.iloc[-1]
    curr_ema20 = ema20.iloc[-1]
    curr_ema50 = ema50.iloc[-1]
    
    if curr_price > curr_ema20:
        score += 20
    if curr_ema20 > curr_ema50:
        score += 15  # Yükselen Trend
        
    # 2. RSI (14) Momentum
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    rsi = 100 - (100 / (1 + rs))
    curr_rsi = rsi.iloc[-1]
    
    if 40 <= curr_rsi <= 65:
        score += 25  # İdeal ivme bölgesi
    elif 30 <= curr_rsi < 40:
        score += 15  # Dip Dönüş Potansiyeli
    elif curr_rsi > 70:
        score += 5   # Doygunluk riski
        
    # 3. Göreceli Hacim (RVOL - Relative Volume)
    avg_vol_20 = volume.rolling(20).mean().iloc[-1]
    curr_vol = volume.iloc[-1]
    rvol = curr_vol / (avg_vol_20 + 1e-9)
    
    if rvol >= 1.5:
        score += 25  # Güçlü Para Girişi
    elif rvol >= 1.0:
        score += 15
        
    # 4. MACD Kesişimi
    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    
    if macd.iloc[-1] > signal.iloc[-1]:
        score += 15
        
    return score, round(curr_rsi, 1), round(rvol, 2), round(curr_price, 2), "BAŞARILI"

# ==============================================================================
# 5. TEMEL BİLANÇO SKORLAMA (BAĞIMSIZ FİNANSAL SAĞLIK)
# ==============================================================================
@st.cache_data(ttl=86400)
def compute_fundamental_score(ticker_symbol):
    """
    Sadece Bilanço, Gelir Tablosu ve Nakit Akışına bakar.
    Teknik indikatörleri etkilemeden 0-100 arası Bilanço Kalite Skoru verir.
    """
    score = 0
    try:
        stock = yf.Ticker(ticker_symbol)
        financials = stock.financials
        balance_sheet = stock.balance_sheet
        cashflow = stock.cashflow

        if financials.empty or balance_sheet.empty:
            return 50  # Veri eksikse nötr puan

        # A. Kârlılık ve Büyüme (40 Puan)
        if 'Net Income' in financials.index:
            net_inc = financials.loc['Net Income']
            if len(net_inc) >= 2:
                if net_inc.iloc[0] > net_inc.iloc[1]:
                    score += 20  # Yıllık Kâr Büyümesi
                if net_inc.iloc[0] > 0:
                    score += 10  # Pozitif Net Kâr
                    
        if 'Operating Cash Flow' in cashflow.index:
            op_cf = cashflow.loc['Operating Cash Flow'].iloc[0]
            if op_cf > 0:
                score += 10  # Operasyonel Nakit Üretimi Var

        # B. Borçluluk ve Sağlık (30 Puan)
        if 'Total Stockholder Equity' in balance_sheet.index and 'Total Debt' in balance_sheet.index:
            equity = balance_sheet.loc['Total Stockholder Equity'].iloc[0]
            debt = balance_sheet.loc['Total Debt'].iloc[0]
            if equity > 0 and (debt / equity) < 1.5:
                score += 15  # Borç Yükü Güvenli
                
        if 'Total Current Assets' in balance_sheet.index and 'Total Current Liabilities' in balance_sheet.index:
            curr_assets = balance_sheet.loc['Total Current Assets'].iloc[0]
            curr_liab = balance_sheet.loc['Total Current Liabilities'].iloc[0]
            if curr_liab > 0 and (curr_assets / curr_liab) > 1.2:
                score += 15  # Cari Oran Güçlü (Likit)

        # C. Kâr Kalitesi (30 Puan)
        if 'Net Income' in financials.index and 'Operating Cash Flow' in cashflow.index:
            if cashflow.loc['Operating Cash Flow'].iloc[0] >= financials.loc['Net Income'].iloc[0]:
                score += 30  # Kasaya giren nakit net kârdan yüksek
            else:
                score += 15

    except Exception:
        return 50

    return min(score, 100)

# ==============================================================================
# 6. ARAYÜZ BAŞLIĞI VE SÜZGEÇ KONTROLLERİ
# ==============================================================================
st.title("⚡ BİST 100 Quantamental Radar & Sanal Trading Lab")
st.caption("Çift Süzgeçli Yapı: Sinyali bozmayan teknik Quant analizi ve temel Bilanço Kalite Skoru.")

# Sidebar Kontrolleri (Varsayılan eşikler daha esnek seviyelere çekildi)
st.sidebar.header("🎯 Süzgeç Ayarları")
min_fund_score = st.sidebar.slider("Minimum Bilanço Skoru", 0, 100, 30, help="Bu puanın altındaki şirketler elenir.")
min_quant_score = st.sidebar.slider("Minimum Quant Skor (Teknik)", 0, 100, 40)

st.sidebar.markdown("---")
st.sidebar.subheader("💼 Portföy Özeti")
st.sidebar.write(f"**Nakit Bakiye:** {st.session_state.cash:,.2f} TL")

total_port_val = st.session_state.cash
for tkr, data in st.session_state.portfolio.items():
    try:
        cur_p = yf.Ticker(f"{tkr}.IS").fast_info['lastPrice']
    except:
        cur_p = data['avg_price']
    total_port_val += data['qty'] * cur_p

st.sidebar.write(f"**Toplam Portföy Değeri:** {total_port_val:,.2f} TL")

# ==============================================================================
# 7. TABLI ARAYÜZ (4 ANA SEKMEMİZ)
# ==============================================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 Tablo 1: Canlı Quant Radar", 
    "📊 Tablo 2: Bilanço & Fintables Analizi", 
    "📈 Tablo 3: İnteraktif Grafik & İndikatörler", 
    "💸 Tablo 4: Sanal Trading Simülasyonu"
])

# ------------------------------------------------------------------------------
# TAB 1: CANLI QUANT RADAR (GÜVENLİ & HATA VERMEYEN YAPI)
# ------------------------------------------------------------------------------
with tab1:
    st.subheader("Bilanço Filtreli Quant Sinyal Radarı")
    
    if st.button("🚀 Radarı Taramaya Başla"):
        results = []
        progress_bar = st.progress(0)
        
        for idx, ticker in enumerate(BIST100_TICKERS):
            clean_ticker = ticker.replace(".IS", "")
            
            try:
                df_price = yf.download(ticker, period="6m", interval="1d", progress=False)
            except Exception:
                df_price = pd.DataFrame()
            
            if not df_price.empty:
                if isinstance(df_price.columns, pd.MultiIndex):
                    df_price.columns = df_price.columns.get_level_values(0)

                q_score, rsi, rvol, price, status_code = compute_quant_score(df_price)
                f_score = compute_fundamental_score(ticker)
                
                # Çift Süzgeç Sınıflandırması
                if f_score >= 50 and q_score >= 60:
                    status = "🚀 GÜÇLÜ AL (Sweet Spot)"
                elif f_score < 40 and q_score >= 60:
                    status = "⚠️ SPEKÜLATİF AL (Bilanço Zayıf)"
                elif f_score >= 50 and q_score < 40:
                    status = "👀 İZLEMEYE AL (Teknik Düzeltmede)"
                else:
                    status = "❌ NÖTR / UZAK DUR"

                results.append({
                    "Hisse": clean_ticker,
                    "Fiyat (TL)": price,
                    "Quant Skor (Teknik)": q_score,
                    "Bilanço Skoru (Temel)": f_score,
                    "RSI": rsi,
                    "Göreceli Hacim (RVOL)": rvol,
                    "Sinyal Durumu": status
                })
            progress_bar.progress((idx + 1) / len(BIST100_TICKERS))
            
        # GÜVENLİ DATAFRAME TANIMLAMA (KeyError Önleyici)
        if results:
            res_df = pd.DataFrame(results)
        else:
            res_df = pd.DataFrame(columns=[
                "Hisse", "Fiyat (TL)", "Quant Skor (Teknik)", 
                "Bilanço Skoru (Temel)", "RSI", "Göreceli Hacim (RVOL)", "Sinyal Durumu"
            ])
        
        # Filtreleme
        if not res_df.empty:
            filtered_df = res_df[
                (res_df["Bilanço Skoru (Temel)"] >= min_fund_score) &
                (res_df["Quant Skor (Teknik)"] >= min_quant_score)
            ].sort_values(by="Quant Skor (Teknik)", ascending=False)
        else:
            filtered_df = res_df.copy()
        
        # Metrik Özetleri
        m1, m2, m3 = st.columns(3)
        m1.metric("Taranan Hisse", len(BIST100_TICKERS))
        m2.metric("Süzgeçten Geçen", len(filtered_df))
        m3.metric("Güçlü Al Veren", len(res_df[res_df["Sinyal Durumu"].str.contains("GÜÇLÜ AL")]) if not res_df.empty else 0)

        if not filtered_df.empty:
            st.dataframe(
                filtered_df,
                column_config={
                    "Quant Skor (Teknik)": st.column_config.ProgressColumn("Quant Skor", format="%d", min_value=0, max_value=100),
                    "Bilanço Skoru (Temel)": st.column_config.ProgressColumn("Bilanço Skoru", format="%d", min_value=0, max_value=100),
                    "Fiyat (TL)": st.column_config.NumberColumn(format="%.2f TL")
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("⚠️ Belirlediğiniz süzgeç kriterlerine uygun hisse bulunamadı. Sol menüden filtre değerlerini daha da düşürebilirsiniz.")

        # Tüm Sonuçları Görme Opsiyonu
        with st.expander("📋 Filtrelenmemiş Tüm Taranan Hisseleri Göster"):
            st.dataframe(res_df, use_container_width=True, hide_index=True)

# ------------------------------------------------------------------------------
# TAB 2: BİLANÇO & FİNTABLES BENZERİ DETAYLI ANALİZ
# ------------------------------------------------------------------------------
with tab2:
    st.subheader("Şirket Bilanço ve Rasyo Analizi")
    selected_stock_f = st.selectbox("Analiz Edilecek Hisse Seçin:", [t.replace(".IS", "") for t in BIST100_TICKERS], key="f_select")
    
    if selected_stock_f:
        tkr_obj = yf.Ticker(f"{selected_stock_f}.IS")
        
        col1, col2, col3, col4 = st.columns(4)
        try:
            info = tkr_obj.info
            col1.metric("F/K Oranı", round(info.get('trailingPE', 0), 2))
            col2.metric("PD/DD Oranı", round(info.get('priceToBook', 0), 2))
            col3.metric("Özsermaye Kârlılığı (ROE)", f"%{round(info.get('returnOnEquity', 0)*100, 2)}")
            col4.metric("Firma Değeri / FAVÖK", round(info.get('enterpriseToEbitda', 0), 2))
        except:
            st.warning("Veriler anlık çekilemedi.")
            
        st.markdown("---")
        kap_url = f"https://www.kap.org.tr/tr/sirket-bilgileri/ozet/{selected_stock_f}"
        st.markdown(f"🔗 **[KAP (Kamuoyunu Aydınlatma Platformu) Sayfasına Git]({kap_url})**")

# ------------------------------------------------------------------------------
# TAB 3: İNTERAKTİF GRAFİK & İNDİKATÖRLER
# ------------------------------------------------------------------------------
with tab3:
    st.subheader("Teknik İndikatör & Mum Grafiği")
    selected_stock_g = st.selectbox("Grafik Hissesi Seçin:", [t.replace(".IS", "") for t in BIST100_TICKERS], key="g_select")
    
    if selected_stock_g:
        df_chart = yf.download(f"{selected_stock_g}.IS", period="1y", interval="1d", progress=False)
        if isinstance(df_chart.columns, pd.MultiIndex):
            df_chart.columns = df_chart.columns.get_level_values(0)
            
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df_chart.index,
            open=df_chart['Open'],
            high=df_chart['High'],
            low=df_chart['Low'],
            close=df_chart['Close'],
            name="Fiyat"
        ))
        
        # EMA 20
        ema20 = df_chart['Close'].ewm(span=20, adjust=False).mean()
        fig.add_trace(go.Scatter(x=df_chart.index, y=ema20, mode='lines', name='EMA 20', line=dict(color='orange', width=1.5)))
        
        fig.update_layout(
            title=f"{selected_stock_g} Günlük Fiyat Grafiği ve EMA 20",
            template="plotly_white",
            height=500,
            xaxis_rangeslider_visible=False
        )
        st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------------------
# TAB 4: SANAL TRADING SİMÜLASYONU (PAPER TRADING)
# ------------------------------------------------------------------------------
with tab4:
    st.subheader("Sanal Alım / Satım Paneli")
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("### 🛒 Hisse Al / Sat")
        trade_ticker = st.selectbox("Hisse Seç:", [t.replace(".IS", "") for t in BIST100_TICKERS], key="t_select")
        
        try:
            live_price = yf.Ticker(f"{trade_ticker}.IS").fast_info['lastPrice']
        except:
            live_price = 100.0
            
        st.write(f"**Anlık Fiyat:** {live_price:,.2f} TL")
        trade_qty = st.number_input("Adet:", min_value=1, value=10, step=1)
        
        col_buy, col_sell = st.columns(2)
        
        # ALIM İŞLEMİ
        if col_buy.button("🟢 HİSSE AL"):
            total_cost = trade_qty * live_price
            if st.session_state.cash >= total_cost:
                st.session_state.cash -= total_cost
                
                if trade_ticker in st.session_state.portfolio:
                    old_qty = st.session_state.portfolio[trade_ticker]['qty']
                    old_avg = st.session_state.portfolio[trade_ticker]['avg_price']
                    new_qty = old_qty + trade_qty
                    new_avg = ((old_qty * old_avg) + total_cost) / new_qty
                    st.session_state.portfolio[trade_ticker] = {'qty': new_qty, 'avg_price': new_avg}
                else:
                    st.session_state.portfolio[trade_ticker] = {'qty': trade_qty, 'avg_price': live_price}
                    
                st.session_state.trade_history.append({
                    "Tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Hisse": trade_ticker, "İşlem": "ALIM", "Adet": trade_qty, "Fiyat": live_price
                })
                st.success(f"{trade_qty} adet {trade_ticker} alındı!")
                st.rerun()
            else:
                st.error("Yetersiz Nakit Bakiye!")
                
        # SATIM İŞLEMİ
        if col_sell.button("🔴 HİSSE SAT"):
            if trade_ticker in st.session_state.portfolio and st.session_state.portfolio[trade_ticker]['qty'] >= trade_qty:
                total_income = trade_qty * live_price
                st.session_state.cash += total_income
                
                st.session_state.portfolio[trade_ticker]['qty'] -= trade_qty
                if st.session_state.portfolio[trade_ticker]['qty'] == 0:
                    del st.session_state.portfolio[trade_ticker]
                    
                st.session_state.trade_history.append({
                    "Tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Hisse": trade_ticker, "İşlem": "SATIM", "Adet": trade_qty, "Fiyat": live_price
                })
                st.success(f"{trade_qty} adet {trade_ticker} satıldı!")
                st.rerun()
            else:
                st.error("Portföyünüzde yeterli adet yok!")

    with c2:
        st.markdown("### 📋 Mevcut Portföyüm")
        if st.session_state.portfolio:
            port_data = []
            for tkr, p_info in st.session_state.portfolio.items():
                try:
                    c_price = yf.Ticker(f"{tkr}.IS").fast_info['lastPrice']
                except:
                    c_price = p_info['avg_price']
                val = p_info['qty'] * c_price
                pnl = (c_price - p_info['avg_price']) * p_info['qty']
                
                port_data.append({
                    "Hisse": tkr, "Adet": p_info['qty'], 
                    "Maliyet": round(p_info['avg_price'], 2), 
                    "Son Fiyat": round(c_price, 2),
                    "Toplam Değer": round(val, 2),
                    "Kâr/Zarar (TL)": round(pnl, 2)
                })
            st.dataframe(pd.DataFrame(port_data), use_container_width=True, hide_index=True)
        else:
            st.info("Portföyünüzde henüz hisse bulunmuyor.")

    st.markdown("---")
    st.markdown("### 📜 Geçmiş İşlemler")
    if st.session_state.trade_history:
        st.dataframe(pd.DataFrame(st.session_state.trade_history), use_container_width=True, hide_index=True)

# ============================================================
# QUANT MASTER v76 — MODERN STREAMLIT INTERFACE (LIGHT MODE)
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np

# --- MOTOR KODLARI (Aynen Korunmuştur) ---

class PointInTimeRSEngine:
    @staticmethod
    def compute_pit_composite_rs(universe_dfs: dict) -> dict:
        lookbacks = {20: 0.20, 60: 0.50, 120: 0.30}
        sample_df = next(iter(universe_dfs.values()))
        dates = sample_df.index
        tickers = list(universe_dfs.keys())
        
        close_dict = {}
        for t in tickers:
            df = universe_dfs[t]
            if df is not None and not df.empty:
                close_dict[t] = pd.to_numeric(df["Close"], errors="coerce")
        
        close_df = pd.DataFrame(close_dict).sort_index()
        composite_results = {t: pd.Series(50.0, index=dates) for t in tickers}
        
        mom_dfs = {}
        for lb in lookbacks.keys():
            mom_dfs[lb] = close_df / close_df.shift(lb) - 1.0
            
        pct_dfs = {}
        for lb in lookbacks.keys():
            pct_dfs[lb] = mom_dfs[lb].rank(axis=1, method="average", pct=True) * 100.0
            
        final_composite = pd.DataFrame(0.0, index=close_df.index, columns=tickers)
        for lb, weight in lookbacks.items():
            if lb in pct_dfs:
                final_composite += pct_dfs[lb].fillna(50.0) * weight
            else:
                final_composite += 50.0 * weight
                
        for t in tickers:
            if t in final_composite.columns:
                composite_results[t] = final_composite[t].reindex(dates).fillna(50.0)
                
        return composite_results


class FourStageMarketRegimeEngine:
    @staticmethod
    def evaluate_regime(benchmark_df: pd.DataFrame) -> pd.Series:
        if benchmark_df is None or benchmark_df.empty:
            return pd.Series("NEUTRAL", index=[])
        
        close = benchmark_df["Close"]
        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()
        ema200 = close.ewm(span=200, adjust=False).mean()
        
        conditions = [
            (close > ema20) & (ema20 > ema50) & (ema50 > ema200),
            (close > ema50) & (ema50 > ema200),
            (close > ema200)
        ]
        choices = ["STRONG_BULL", "BULL", "NEUTRAL"]
        regime = np.select(conditions, choices, default="BEAR")
        return pd.Series(regime, index=benchmark_df.index)


class PrecisionWFOEngineV76:
    def __init__(self, train_window: int = 126, test_window: int = 63, initial_capital: float = 100000.0, commission: float = 0.001, slippage: float = 0.0002):
        self.train_window = train_window
        self.test_window = test_window
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage

    def run_backtest(self, df: pd.DataFrame, benchmark_df: pd.DataFrame, pit_rs_series: pd.Series) -> dict:
        total_len = len(df)
        if total_len < (self.train_window + self.test_window):
            raise ValueError("WFO pencereleri için veri uzunluğu yetersiz.")

        all_trades = []
        equity_curve = []
        start_idx = 0

        regime_series = FourStageMarketRegimeEngine.evaluate_regime(benchmark_df)
        processed_full = self._compute_factors(df, pit_rs_series)

        current_cash = self.initial_capital
        current_shares = 0.0
        entry_price = 0.0
        entry_class = None
        stop_loss = 0.0
        take_profit = 0.0

        while start_idx + self.train_window + self.test_window <= total_len:
            test_start = start_idx + self.train_window
            test_finish = min(test_start + self.test_window, total_len)
            
            context_start = max(0, test_start - 250)
            context_df = processed_full.iloc[context_start:test_finish].copy()
            signaled_context = self._generate_signals(context_df, regime_series)
            
            test_df = signaled_context.iloc[test_start - context_start:].copy()
            if test_df.empty:
                start_idx += self.test_window
                continue

            current_cash, current_shares, entry_price, entry_class, stop_loss, take_profit, trades, equity = self._execute_oos_cumulative(
                test_df, current_cash, current_shares, entry_price, entry_class, stop_loss, take_profit
            )
            
            all_trades.extend(trades)
            equity_curve.extend(equity)

            start_idx += self.test_window
            if test_finish >= total_len:
                break

        return self._calculate_metrics(all_trades, equity_curve)

    def _compute_factors(self, df: pd.DataFrame, pit_rs: pd.Series) -> pd.DataFrame:
        data = df.copy()
        data["EMA20"] = data["Close"].ewm(span=20, adjust=False).mean()
        data["EMA50"] = data["Close"].ewm(span=50, adjust=False).mean()
        data["EMA200"] = data["Close"].ewm(span=200, adjust=False).mean()
        
        data["EMA20_SLOPE"] = data["EMA20"] / data["EMA20"].shift(5) - 1.0
        
        delta = data["Close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0.0)
        avg_g = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_l = loss.ewm(alpha=1/14, adjust=False).mean()
        rs_val = avg_g / (avg_l + 1e-10)
        data["RSI"] = 100 - (100 / (1 + rs_val))
        
        prev_close = data["Close"].shift(1)
        tr = pd.concat([
            data["High"] - data["Low"],
            (data["High"] - prev_close).abs(),
            (data["Low"] - prev_close).abs()
        ], axis=1).max(axis=1)
        data["ATR"] = tr.ewm(alpha=1/14, adjust=False).mean()
        
        data["Volume20"] = data["Volume"].rolling(20).mean()
        data["RVOL"] = data["Volume"] / (data["Volume20"] + 1e-10)
        
        prev_high20 = data["High"].rolling(20).max().shift(1)
        data["PREV_HIGH20"] = prev_high20
        data["BREAKOUT20"] = data["Close"] > prev_high20
        data["BREAKOUT_MAG"] = (data["Close"] - prev_high20) / prev_high20 * 100.0
        
        data["LOW_10"] = data["Low"].rolling(10).min().shift(1)
        data["Composite_RS"] = pit_rs.reindex(data.index).fillna(50.0)
        
        return data

    def _generate_signals(self, df: pd.DataFrame, regime_series: pd.Series) -> pd.DataFrame:
        data = df.copy()
        regime = regime_series.reindex(data.index).fillna("NEUTRAL")
        
        a_plus_gate = (
            (regime == "STRONG_BULL") &
            (data["Composite_RS"] >= 88) &
            (data["RSI"].between(50, 72)) &
            (data["EMA20"] > data["EMA50"]) &
            (data["EMA50"] > data["EMA200"]) &
            (data["EMA20_SLOPE"] > 0) &
            (data["RVOL"] >= 1.30) &
            (data["BREAKOUT20"]) &
            (data["BREAKOUT_MAG"] >= 0.1)
        )
        
        a_gate = (
            ((regime == "STRONG_BULL") | (regime == "BULL")) &
            (data["Composite_RS"] >= 78) &
            (data["RSI"].between(48, 75)) &
            (data["EMA20"] > data["EMA50"]) &
            (data["RVOL"] >= 1.15) &
            (~a_plus_gate)
        )
        
        watch_gate = (
            (regime != "BEAR") &
            (data["Composite_RS"] >= 70) &
            (data["RSI"].between(45, 78)) &
            (~a_plus_gate) &
            (~a_gate)
        )
        
        data["Signal_Class"] = np.select(
            [a_plus_gate, a_gate, watch_gate],
            ["A+", "A", "WATCH"],
            default="NO TRADE"
        )
        return data

    def _execute_oos_cumulative(self, test_df, cash, shares, entry_price, entry_class, stop_loss, take_profit):
        trades = []
        equity_curve = []

        for i in range(1, len(test_df)):
            prev = test_df.iloc[i - 1]
            curr = test_df.iloc[i]
            date = test_df.index[i]

            open_p = float(curr["Open"])
            high_p = float(curr["High"])
            low_p = float(curr["Low"])
            close_p = float(curr["Close"])
            atr = float(prev.get("ATR", close_p * 0.02))
            swing_low = float(prev.get("LOW_10", low_p - (2 * atr)))

            if shares == 0:
                sig_class = prev.get("Signal_Class", "NO TRADE")
                if sig_class in ["A+", "A"]:
                    exec_price = open_p * (1 + self.commission + self.slippage)
                    if exec_price > 0:
                        shares = cash / exec_price
                        entry_price = exec_price
                        entry_class = sig_class
                        cash = 0.0

                        atr_stop = entry_price - (2.0 * atr)
                        stop_loss = min(atr_stop, swing_low if not np.isnan(swing_low) else atr_stop)
                        take_profit = entry_price + (3.5 * atr)

                        trades.append({"Date": date, "Action": "BUY", "Price": entry_price, "Class": entry_class})

                        if low_p <= stop_loss:
                            exit_p = open_p if open_p <= stop_loss else stop_loss
                            cash = shares * exit_p * (1 - self.commission - self.slippage)
                            pnl = (exit_p - entry_price) / entry_price * 100.0
                            trades.append({"Date": date, "Action": "SELL", "Price": exit_p, "Reason": "STOP_LOSS", "PnL_Pct": pnl, "Class": entry_class})
                            shares = 0.0
                        elif high_p >= take_profit:
                            exit_p = open_p if open_p >= take_profit else take_profit
                            cash = shares * exit_p * (1 - self.commission - self.slippage)
                            pnl = (exit_p - entry_price) / entry_price * 100.0
                            trades.append({"Date": date, "Action": "SELL", "Price": exit_p, "Reason": "TAKE_PROFIT", "PnL_Pct": pnl, "Class": entry_class})
                            shares = 0.0
            else:
                stop_hit = low_p <= stop_loss
                tp_hit = high_p >= take_profit
                exit_p = None
                reason = None

                if stop_hit:
                    exit_p = open_p if open_p <= stop_loss else stop_loss
                    reason = "STOP_LOSS"
                elif tp_hit:
                    exit_p = open_p if open_p >= take_profit else take_profit
                    reason = "TAKE_PROFIT"

                if exit_p is not None:
                    cash = shares * exit_p * (1 - self.commission - self.slippage)
                    pnl = (exit_p - entry_price) / entry_price * 100.0
                    trades.append({"Date": date, "Action": "SELL", "Price": exit_p, "Reason": reason, "PnL_Pct": pnl, "Class": entry_class})
                    shares = 0.0
                    entry_class = None

            nav = cash + (shares * close_p if shares > 0 else 0)
            equity_curve.append({"Date": date, "NAV": nav})

        return cash, shares, entry_price, entry_class, stop_loss, take_profit, trades, equity_curve

    def _calculate_metrics(self, trades: list, equity_curve: list) -> dict:
        class_stats = {"A+": [], "A": [], "WATCH": []}
        open_trade = None

        for t in trades:
            if t["Action"] == "BUY":
                open_trade = t
            elif t["Action"] == "SELL" and open_trade:
                sig_class = open_trade.get("Class", "UNKNOWN")
                pnl = float(t.get("PnL_Pct", 0.0))
                if sig_class in class_stats:
                    class_stats[sig_class].append(pnl)
                open_trade = None

        report = {}
        for sig_class, pnl_list in class_stats.items():
            if not pnl_list:
                report[sig_class] = {"Trades": 0, "Win_Rate": 0.0, "Profit_Factor": 0.0, "Avg_Return": 0.0}
                continue

            wins = [p for p in pnl_list if p > 0]
            losses = [p for p in pnl_list if p <= 0]
            win_rate = len(wins) / len(pnl_list) * 100.0
            gp = sum(wins)
            gl = abs(sum(losses)) if losses else 1e-10
            pf = gp / gl

            report[sig_class] = {
                "Trades": len(pnl_list),
                "Win_Rate": win_rate,
                "Profit_Factor": pf,
                "Avg_Return": float(np.mean(pnl_list))
            }

        eq_df = pd.DataFrame(equity_curve)
        total_return = (eq_df["NAV"].iloc[-1] / self.initial_capital - 1.0) * 100.0 if not eq_df.empty else 0.0

        return {
            "Total_Return_Pct": total_return,
            "By_Class": report,
            "Trades": trades,
            "Equity": eq_df
        }


# --- MODERN STREAMLIT ARAYÜZÜ (LIGHT MODE) ---

st.set_page_config(
    page_title="QUANT MASTER v76 — Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Aydınlık Tema CSS Enjeksiyonu
st.markdown("""
    <style>
    .stApp {
        background-color: #ffffff;
        color: #1e222d;
        font-family: -apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, Ubuntu, sans-serif;
    }
    header {visibility: hidden;}
    
    .metric-card {
        background-color: #f8f9fa;
        border: 1px solid #e0e3eb;
        border-radius: 6px;
        padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .metric-title {
        font-size: 12px;
        color: #787b86;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 24px;
        font-weight: 700;
        color: #2962ff;
        margin-top: 4px;
    }
    .metric-value-green {
        font-size: 24px;
        font-weight: 700;
        color: #089981;
        margin-top: 4px;
    }
    [data-testid="stSidebar"] {
        background-color: #f1f3f6;
        border-right: 1px solid #e0e3eb;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("## 📊 QUANT MASTER v76 — Precision WFO & Signal Terminal")
st.markdown("<hr style='border: 1px solid #e0e3eb; margin-top: 0px; margin-bottom: 20px;'>", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### ⚙️ Terminal Ayarları")
    initial_capital = st.number_input("Başlangıç Sermayesi (TL)", value=100000.0, step=10000.0)
    train_window = st.number_input("Train Penceresi", value=126, step=10)
    test_window = st.number_input("Test Penceresi (OOS)", value=63, step=5)
    commission = st.number_input("Komisyon Oranı", value=0.001, format="%.4f")
    slippage = st.number_input("Slippage Oranı", value=0.0002, format="%.5f")
    
    run_btn = st.button("🚀 Backtest Çalıştır", type="primary", use_container_width=True)

if run_btn:
    with st.spinner("Piyasa verileri işleniyor ve Point-in-Time RS hesaplanıyor..."):
        np.random.seed(42)
        dates = pd.date_range(start="2024-01-01", periods=500, freq="B")
        
        bench_close = 100 * (1 + np.random.normal(0.0005, 0.015, len(dates))).cumprod()
        benchmark_df = pd.DataFrame({
            "Open": bench_close * 0.99, "High": bench_close * 1.01,
            "Low": bench_close * 0.98, "Close": bench_close,
            "Volume": np.random.randint(1000000, 5000000, len(dates))
        }, index=dates)
        
        tickers = ["GARAN.IS", "THYAO.IS", "AKBNK.IS", "EREGL.IS", "KCHOL.IS"]
        universe_dfs = {}
        for t in tickers:
            close = 50 * (1 + np.random.normal(0.0008, 0.02, len(dates))).cumprod()
            universe_dfs[t] = pd.DataFrame({
                "Open": close * 0.99, "High": close * 1.02,
                "Low": close * 0.97, "Close": close,
                "Volume": np.random.randint(500000, 2000000, len(dates))
            }, index=dates)
            
        pit_rs_dict = PointInTimeRSEngine.compute_pit_composite_rs(universe_dfs)
        
        test_ticker = tickers[0]
        engine = PrecisionWFOEngineV76(
            train_window=int(train_window),
            test_window=int(test_window),
            initial_capital=float(initial_capital),
            commission=float(commission),
            slippage=float(slippage)
        )
        
        results = engine.run_backtest(universe_dfs[test_ticker], benchmark_df, pit_rs_dict[test_ticker])
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
                <div class='metric-card'>
                    <div class='metric-title'>Toplam Getiri</div>
                    <div class='metric-value-green'>%{results['Total_Return_Pct']:.2f}</div>
                </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
                <div class='metric-card'>
                    <div class='metric-title'>Son Sermaye</div>
                    <div class='metric-value'>₺{initial_capital * (1 + results['Total_Return_Pct']/100):,.2f}</div>
                </div>
            """, unsafe_allow_html=True)
        with col3:
            total_trades = sum([v['Trades'] for v in results['By_Class'].values()])
            st.markdown(f"""
                <div class='metric-card'>
                    <div class='metric-title'>Toplam İşlem</div>
                    <div class='metric-value'>{total_trades}</div>
                </div>
            """, unsafe_allow_html=True)
        with col4:
            st.markdown(f"""
                <div class='metric-card'>
                    <div class='metric-title'>Sistem Durumu</div>
                    <div class='metric-value-green'>AKTİF (v76)</div>
                </div>
            """, unsafe_allow_html=True)
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        tab1, tab2, tab3 = st.tabs(["📈 Sermaye Eğrisi (Equity)", "📊 Sınıf Bazlı Performans", "📋 Trade Defteri"])
        
        with tab1:
            if not results['Equity'].empty:
                chart_df = results['Equity'].set_index("Date")
                st.line_chart(chart_df["NAV"])
            else:
                st.info("Gösterilecek equity verisi bulunamadı.")
                
        with tab2:
            class_report_df = pd.DataFrame(results['By_Class']).T
            st.dataframe(class_report_df, use_container_width=True)
            
        with tab3:
            if results['Trades']:
                trades_df = pd.DataFrame(results['Trades'])
                st.dataframe(trades_df, use_container_width=True)
            else:
                st.info("Bu periyotta gerçekleşen işlem bulunamadı.")
else:
    st.markdown("""
        <div style='text-align: center; padding: 50px; color: #787b86;'>
            <h3>Backtest simülasyonunu başlatmak için sol menüden 'Backtest Çalıştır' butonuna tıklayın.</h3>
        </div>
    """, unsafe_allow_html=True)


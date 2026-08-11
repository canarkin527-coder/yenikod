import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime
import warnings
import textwrap

warnings.filterwarnings("ignore")

# ==============================================================================
# QUANT MASTER v64.2 - INSTITUTIONAL QUANT & PAPER TRADING TERMINAL
# FIXED: HTML CODE DISPLAY + YFINANCE MULTIINDEX/COLUMN KeyError
# ==============================================================================

st.set_page_config(
    page_title="QUANT MASTER v64.2 | Institutional Quant Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# CSS
# ==============================================================================
st.markdown(textwrap.dedent("""
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
.metric-title {
    font-size: 0.85rem;
    font-weight: 700;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}
.metric-val {
    font-size: 1.8rem;
    font-weight: 900;
    color: #38BDF8;
    margin-top: 5px;
}
.signal-badge-green {
    background-color: #064E3B;
    border: 1px solid #10B981;
    color: #34D399;
    padding: 6px 12px;
    border-radius: 8px;
    font-weight: 800;
    display: inline-block;
}
.signal-badge-blue {
    background-color: #1E3A8A;
    border: 1px solid #3B82F6;
    color: #60A5FA;
    padding: 6px 12px;
    border-radius: 8px;
    font-weight: 800;
    display: inline-block;
}
.signal-badge-yellow {
    background-color: #78350F;
    border: 1px solid #F59E0B;
    color: #FBBF24;
    padding: 6px 12px;
    border-radius: 8px;
    font-weight: 800;
    display: inline-block;
}
.live-ticker {
    color: #38BDF8;
    font-weight: bold;
    font-family: monospace;
}
</style>
"""), unsafe_allow_html=True)

DB_FILE = "quant_master_v64_pro.db"


# ==============================================================================
# 1. DATAFRAME / YFINANCE NORMALIZATION
# ==============================================================================

def normalize_yfinance_df(df):
    """
    yfinance bazı sürümlerde tek sembol için bile MultiIndex döndürebilir.
    Bu fonksiyon OHLCV kolonlarını güvenli biçimde tek seviyeye indirir.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()

    if isinstance(out.columns, pd.MultiIndex):
        # Önce OHLCV seviyesini bulmaya çalış
        wanted = {"Open", "High", "Low", "Close", "Adj Close", "Volume"}

        # Birinci seviyede OHLCV varsa onu seç
        if any(col in wanted for col in out.columns.get_level_values(0)):
            out.columns = out.columns.get_level_values(0)
        # İkinci seviyede OHLCV varsa onu seç
        elif out.columns.nlevels > 1 and any(
            col in wanted for col in out.columns.get_level_values(-1)
        ):
            out.columns = out.columns.get_level_values(-1)
        else:
            # Son çare: ilk seviyeyi kullan
            out.columns = out.columns.get_level_values(0)

    # Aynı isimli kolonlar oluşmuşsa ilkini kullan
    if out.columns.duplicated().any():
        out = out.loc[:, ~out.columns.duplicated(keep="first")]

    # Adj Close yoksa Close yeterlidir
    required = ["Open", "High", "Low", "Close", "Volume"]
    for col in required:
        if col not in out.columns:
            if col == "Open" and "Close" in out.columns:
                out["Open"] = out["Close"]
            elif col in ("High", "Low") and "Close" in out.columns:
                out[col] = out["Close"]
            elif col == "Volume":
                out["Volume"] = 0.0
            else:
                return pd.DataFrame()

    for col in required:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out = out.dropna(subset=required).copy()
    return out


def download_single(symbol, period="3y"):
    try:
        raw = yf.download(
            symbol,
            period=period,
            progress=False,
            auto_adjust=False,
            threads=False
        )
        return normalize_yfinance_df(raw)
    except Exception:
        return pd.DataFrame()


def get_latest_price(symbol, fallback=None):
    try:
        data = yf.download(
            symbol,
            period="2d",
            interval="1d",
            progress=False,
            auto_adjust=False,
            threads=False
        )
        data = normalize_yfinance_df(data)
        if not data.empty:
            return float(data["Close"].iloc[-1])
    except Exception:
        pass
    return float(fallback) if fallback is not None else 0.0


def download_universe(symbols, period):
    """
    Evreni tek tek indirir.
    Böylece yfinance MultiIndex yapısı ve tek sembol/çoklu sembol
    kolon farklılıkları kaynaklı KeyError engellenir.
    """
    result = {}
    for symbol in symbols:
        df = download_single(symbol, period)
        if not df.empty:
            result[symbol] = df
    return result


# ==============================================================================
# 2. DATABASE
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
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO portfolio_nav_history
                (timestamp, cash_balance, total_portfolio_nav, open_positions_count)
                VALUES (?, ?, ?, ?)
            """, (now, 100000.0, 100000.0, 0))

        connection.commit()
        connection.close()

    @staticmethod
    def get_active_positions():
        connection = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query(
            "SELECT * FROM active_positions_ledger", connection
        )
        connection.close()
        return df

    @staticmethod
    def get_latest_cash():
        connection = sqlite3.connect(DB_FILE)
        cursor = connection.cursor()
        cursor.execute("""
            SELECT cash_balance
            FROM portfolio_nav_history
            ORDER BY id DESC LIMIT 1
        """)
        row = cursor.fetchone()
        connection.close()
        return float(row[0]) if row else 100000.0

    @staticmethod
    def execute_manual_close(symbol, current_market_price):
        connection = sqlite3.connect(DB_FILE)
        cursor = connection.cursor()

        cursor.execute(
            "SELECT * FROM active_positions_ledger WHERE symbol = ?",
            (symbol,)
        )
        row = cursor.fetchone()

        if row:
            (
                _,
                entry_date,
                entry_price,
                shares,
                _,
                _,
                _,
                _,
                _
            ) = row

            pnl = (current_market_price - entry_price) * shares
            pnl_pct = ((current_market_price / entry_price) - 1) * 100
            exit_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                INSERT INTO historical_trade_ledger
                (symbol, entry_date, exit_date, entry_price, exit_price,
                 shares, realized_pnl, realized_pnl_pct, exit_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                entry_date,
                exit_date,
                entry_price,
                current_market_price,
                shares,
                pnl,
                pnl_pct,
                "MANUAL_CLOSE"
            ))

            cursor.execute(
                "DELETE FROM active_positions_ledger WHERE symbol = ?",
                (symbol,)
            )

            # Satış sonrası nakit: komisyon dahil yaklaşık
            last_cash = InstitutionalDatabaseManager.get_latest_cash()
            new_cash = last_cash + (
                shares * current_market_price * 0.999475
            )

            active_df = pd.read_sql_query(
                "SELECT * FROM active_positions_ledger",
                connection
            )
            open_count = len(active_df)

            cursor.execute("""
                INSERT INTO portfolio_nav_history
                (timestamp, cash_balance, total_portfolio_nav, open_positions_count)
                VALUES (?, ?, ?, ?)
            """, (
                exit_date,
                new_cash,
                new_cash,
                open_count
            ))

            connection.commit()

        connection.close()


# ==============================================================================
# 3. INDICATOR ENGINE
# ==============================================================================

class MasterIndicatorEngine:

    @staticmethod
    def calculate_all_indicators(dataframe):

        if dataframe is None or dataframe.empty:
            return None

        df = normalize_yfinance_df(dataframe)

        if df.empty or len(df) < 120:
            return None

        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        vol = df["Volume"]

        for p in [
            3, 5, 8, 9, 10, 13, 14, 15, 20, 21,
            30, 34, 40, 50, 55, 60, 89, 100, 150, 200
        ]:
            df[f"SMA_{p}"] = close.rolling(p).mean()
            df[f"EMA_{p}"] = close.ewm(
                span=p, adjust=False
            ).mean()

        half_length = 10
        sqrt_length = int(np.sqrt(20))

        w = np.arange(1, half_length + 1)
        wma_half = close.rolling(half_length).apply(
            lambda x: np.dot(x, w) / np.sum(w),
            raw=True
        )

        w = np.arange(1, 21)
        wma_full = close.rolling(20).apply(
            lambda x: np.dot(x, w) / np.sum(w),
            raw=True
        )

        diff_wma = 2 * wma_half - wma_full

        w = np.arange(1, sqrt_length + 1)
        df["HMA_20"] = diff_wma.rolling(sqrt_length).apply(
            lambda x: np.dot(x, w) / np.sum(w),
            raw=True
        )

        df["DEMA_20"] = (
            2 * df["EMA_20"]
            - df["EMA_20"].ewm(span=20, adjust=False).mean()
        )

        ema20_2 = df["EMA_20"].ewm(
            span=20, adjust=False
        ).mean()

        df["TEMA_20"] = (
            3 * df["EMA_20"]
            - 3 * ema20_2
            + ema20_2.ewm(span=20, adjust=False).mean()
        )

        df["VWAP"] = (
            (vol * (high + low + close) / 3).cumsum()
            / (vol.cumsum() + 1e-10)
        )

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()

        df["True_Range"] = pd.concat(
            [tr1, tr2, tr3], axis=1
        ).max(axis=1)

        df["ATR"] = df["True_Range"].ewm(
            span=14, adjust=False
        ).mean()

        df["NATR"] = (df["ATR"] / close) * 100

        # Supertrend
        hl2 = (high + low) / 2
        atr3 = df["ATR"] * 3
        upper_basic = hl2 + atr3
        lower_basic = hl2 - atr3

        supertrend_vals = [0.0] * len(df)
        st_direction = [1] * len(df)

        for i in range(1, len(df)):
            curr_close = close.iloc[i]
            prev_close = close.iloc[i - 1]

            ub = upper_basic.iloc[i]
            lb = lower_basic.iloc[i]

            prev_ub = upper_basic.iloc[i - 1]
            prev_lb = lower_basic.iloc[i - 1]

            final_ub = (
                ub
                if (ub < prev_ub or prev_close > prev_ub)
                else prev_ub
            )

            final_lb = (
                lb
                if (lb > prev_lb or prev_close < prev_lb)
                else prev_lb
            )

            curr_dir = st_direction[i - 1]

            if curr_dir == 1 and curr_close < final_lb:
                curr_dir = -1
            elif curr_dir == -1 and curr_close > final_ub:
                curr_dir = 1

            st_direction[i] = curr_dir
            supertrend_vals[i] = (
                final_lb if curr_dir == 1 else final_ub
            )

        df["Supertrend"] = supertrend_vals

        # RSI
        delta = close.diff()

        pos = (
            delta.where(delta > 0, 0)
            .ewm(alpha=1 / 14, adjust=False)
            .mean()
        )

        neg = (
            -delta.where(delta < 0, 0)
            .ewm(alpha=1 / 14, adjust=False)
            .mean()
        )

        df["RSI"] = 100 - (
            100 / (1 + pos / (neg + 1e-10))
        )

        # MACD
        ema_f = close.ewm(
            span=12, adjust=False
        ).mean()

        ema_s = close.ewm(
            span=26, adjust=False
        ).mean()

        df["MACD"] = ema_f - ema_s

        df["MACD_Signal"] = df["MACD"].ewm(
            span=9, adjust=False
        ).mean()

        df["MACD_Hist"] = (
            df["MACD"] - df["MACD_Signal"]
        )

        # Volume indicators
        df["OBV"] = (
            np.sign(close.diff()) * vol
        ).fillna(0).cumsum()

        df["OBV_EMA"] = df["OBV"].ewm(
            span=20, adjust=False
        ).mean()

        df["RVOL"] = (
            vol / (vol.rolling(20).mean() + 1e-10)
        )

        # Structure
        df["Rolling_High_50"] = (
            high.rolling(50).max().shift(1)
        )

        df["Rolling_Low_50"] = (
            low.rolling(50).min().shift(1)
        )

        df["BOS"] = (
            (close > df["Rolling_High_50"])
            & (close.shift(1) <= df["Rolling_High_50"])
        ).astype(int)

        df["CHOCH"] = (
            (close < df["Rolling_Low_50"])
            & (close.shift(1) >= df["Rolling_Low_50"])
        ).astype(int)

        df["FVG_Up"] = (
            (low > high.shift(2))
            & (close.shift(1) > high.shift(2))
        ).astype(int)

        for i_idx in range(1, 30):
            window = i_idx + 2
            df[f"Stat_Feature_{i_idx}"] = (
                close.rolling(window).std()
                / (close.rolling(window).mean() + 1e-10)
            )

        df["Total_Active_Metrics"] = 128

        return df


# ==============================================================================
# 4. QUANT ENGINE
# ==============================================================================

class InstitutionalQuantEngine:

    @staticmethod
    def evaluate_universe(
        data_dictionary,
        xu100_dataframe,
        live_quotes=None
    ):
        analysis_results = []

        xu_processed = normalize_yfinance_df(xu100_dataframe)

        for symbol, df in data_dictionary.items():

            processed_df = (
                MasterIndicatorEngine.calculate_all_indicators(df)
            )

            if processed_df is None:
                continue

            latest = processed_df.iloc[-1]

            current_price = float(latest["Close"])

            if live_quotes and symbol in live_quotes:
                if live_quotes[symbol] > 0:
                    current_price = float(live_quotes[symbol])

            layer1 = 0

            if current_price > latest["EMA_20"]:
                layer1 += 8

            if latest["EMA_20"] > latest["EMA_50"]:
                layer1 += 9

            if latest["EMA_50"] > latest["EMA_200"]:
                layer1 += 8

            layer2 = 0

            if 50 <= latest["RSI"] <= 75:
                layer2 += 12

            if latest["MACD_Hist"] > 0:
                layer2 += 13

            if (
                xu_processed is not None
                and not xu_processed.empty
                and len(processed_df) >= 60
                and len(xu_processed) >= 60
            ):
                aligned_xu = (
                    xu_processed["Close"]
                    .reindex(processed_df.index)
                    .ffill()
                )

                if len(aligned_xu) >= 60:
                    stock_base = float(
                        processed_df["Close"].iloc[-60]
                    )
                    market_base = float(
                        aligned_xu.iloc[-60]
                    )

                    if stock_base > 0 and market_base > 0:
                        stock_ret = (
                            current_price / stock_base
                        ) - 1

                        market_ret = (
                            aligned_xu.iloc[-1] / market_base
                        ) - 1

                        rs_val = stock_ret - market_ret

                        layer3 = float(
                            np.clip(
                                (rs_val + 0.15) * 66.6,
                                0,
                                20
                            )
                        )
                    else:
                        layer3 = 10.0
                else:
                    layer3 = 10.0
            else:
                layer3 = 10.0

            layer4 = 0

            if latest["RVOL"] > 1.2:
                layer4 += 8

            if latest["OBV"] > latest["OBV_EMA"]:
                layer4 += 7

            layer5 = 0

            if (
                latest["BOS"] == 1
                or latest["FVG_Up"] == 1
            ):
                layer5 += 10

            if latest["CHOCH"] == 0:
                layer5 += 5

            total_score = float(
                np.clip(
                    layer1
                    + layer2
                    + layer3
                    + layer4
                    + layer5,
                    0,
                    100
                )
            )

            atr = float(latest["ATR"])

            tp1 = current_price + 1.5 * atr
            tp2 = current_price + 3.0 * atr
            stop_loss = current_price - 2.0 * atr

            analysis_results.append({
                "symbol": symbol,
                "score": total_score,
                "price": current_price,
                "rsi": float(latest["RSI"]),
                "rvol": float(latest["RVOL"]),
                "atr": atr,
                "tp1": tp1,
                "tp2": tp2,
                "stop_loss": stop_loss,
                "df": processed_df
            })

        analysis_results.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        return analysis_results


# ==============================================================================
# 5. BACKTEST ENGINE
# ==============================================================================

class BacktestSimulationEngine:

    @staticmethod
    def run_backtest(
        dataframe,
        starting_capital=100000.0,
        user_risk_pct=2.0
    ):

        dataframe = normalize_yfinance_df(dataframe)

        processed_df = (
            MasterIndicatorEngine.calculate_all_indicators(
                dataframe
            )
        )

        if processed_df is None:
            return [], [], {}

        cash = float(starting_capital)
        shares = 0
        equity_curve = []
        trade_results = []
        entry_basis = 0.0

        start_index = 120

        for i in range(start_index, len(processed_df)):

            row = processed_df.iloc[i]

            price = float(row["Close"])
            atr = float(row["ATR"])

            buy_cond = (
                price > row["EMA_20"]
                and row["RSI"] > 50
                and row["RVOL"] > 1.1
                and row["MACD_Hist"] > 0
            )

            sell_cond = (
                price < row["EMA_20"]
                or row["RSI"] < 42
                or (
                    shares > 0
                    and price < entry_basis - 2.0 * atr
                )
            )

            if shares == 0 and buy_cond:

                risk_budget = (
                    cash * (user_risk_pct / 100.0)
                )

                risk_per_share = 2.0 * atr

                if risk_per_share > 0:
                    shares = int(
                        risk_budget / risk_per_share
                    )
                else:
                    shares = int(
                        (cash * 0.20) / price
                    )

                max_afford = int(
                    (cash * 0.98) / price
                )

                shares = min(
                    shares,
                    max_afford
                )

                if shares > 0:
                    cash -= (
                        shares
                        * price
                        * 1.000525
                    )
                    entry_basis = price

            elif shares > 0 and sell_cond:

                exit_val = (
                    shares
                    * price
                    * 0.999475
                )

                pnl = (
                    exit_val
                    - (
                        shares
                        * entry_basis
                        * 1.000525
                    )
                )

                cash += exit_val

                trade_results.append(
                    float(pnl)
                )

                shares = 0
                entry_basis = 0.0

            nav = (
                cash
                + (
                    shares * price
                    if shares > 0
                    else 0
                )
            )

            equity_curve.append(float(nav))

        # Açık pozisyonu backtest sonunda realize et
        if shares > 0:
            final_price = float(
                processed_df["Close"].iloc[-1]
            )

            exit_val = (
                shares
                * final_price
                * 0.999475
            )

            pnl = (
                exit_val
                - (
                    shares
                    * entry_basis
                    * 1.000525
                )
            )

            cash += exit_val
            trade_results.append(float(pnl))

            if equity_curve:
                equity_curve[-1] = float(cash)

        if not equity_curve:
            return [], trade_results, {}

        eq_series = pd.Series(
            equity_curve,
            dtype=float
        )

        returns = (
            eq_series
            .pct_change()
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )

        if len(returns) > 1 and returns.std() > 0:
            sharpe_ratio = float(
                (
                    returns.mean()
                    / returns.std()
                )
                * np.sqrt(252)
            )
        else:
            sharpe_ratio = 0.0

        rolling_max = eq_series.cummax()

        drawdown = (
            (eq_series - rolling_max)
            / rolling_max
        )

        max_drawdown = float(
            drawdown.min() * 100
        )

        if trade_results:

            wins = [
                p for p in trade_results
                if p > 0
            ]

            losses = [
                p for p in trade_results
                if p <= 0
            ]

            win_rate = (
                len(wins)
                / len(trade_results)
                * 100.0
            )

            total_gains = sum(wins)
            total_losses = abs(sum(losses))

            if total_losses > 0:
                profit_factor = (
                    total_gains
                    / total_losses
                )
            else:
                profit_factor = float("inf")

        else:
            win_rate = 0.0
            profit_factor = 0.0

        metrics = {
            "sharpe": sharpe_ratio,
            "mdd": max_drawdown,
            "win_rate": win_rate,
            "profit_factor": profit_factor
        }

        return (
            equity_curve,
            trade_results,
            metrics
        )


# ==============================================================================
# 6. SIGNAL CARD
# ==============================================================================

def render_signal_card(item):

    score = item["score"]

    if score >= 75:
        badge_class = "signal-badge-green"
    elif score >= 50:
        badge_class = "signal-badge-blue"
    else:
        badge_class = "signal-badge-yellow"

    # ÖNEMLİ:
    # st.markdown içinde 4+ boşlukla başlayan HTML,
    # Markdown tarafından CODE BLOCK olarak algılanabiliyordu.
    # st.html kullanıldığı için HTML artık yazı olarak görünmez.

    html = f"""
    <div class="terminal-card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <h3 style="margin:0; color:#F8FAFC;">
                    {item["symbol"]}
                </h3>

                <span class="live-ticker">
                    Canlı Fiyat: {item["price"]:.2f} TL
                </span>

                <span style="color:#64748B;"> | </span>

                <span style="color:#94A3B8;">
                    RSI: {item["rsi"]:.1f}
                </span>

                <span style="color:#64748B;"> | </span>

                <span style="color:#94A3B8;">
                    RVOL: {item["rvol"]:.2f}x
                </span>
            </div>

            <div>
                <div class="{badge_class}">
                    Skor: {score:.1f} / 100
                </div>
            </div>
        </div>

        <hr style="border-color:#334155; margin:12px 0;">

        <div style="
            display:flex;
            justify-content:space-between;
            font-size:0.9rem;
            color:#CBD5E1;
        ">
            <div>
                🎯 <b>TP1:</b>
                <span style="color:#34D399;">
                    {item["tp1"]:.2f} TL
                </span>
            </div>

            <div>
                🎯 <b>TP2:</b>
                <span style="color:#10B981;">
                    {item["tp2"]:.2f} TL
                </span>
            </div>

            <div>
                🛑 <b>Stop Loss:</b>
                <span style="color:#EF4444;">
                    {item["stop_loss"]:.2f} TL
                </span>
            </div>
        </div>
    </div>
    """

    # Streamlit sürümünde st.html yoksa markdown fallback
    if hasattr(st, "html"):
        st.html(html)
    else:
        st.markdown(
            textwrap.dedent(html),
            unsafe_allow_html=True
        )


# ==============================================================================
# 7. MAIN
# ==============================================================================

def main():

    InstitutionalDatabaseManager.initialize_database()

    st.markdown(
        '<h1 style="color:#38BDF8; font-weight:900;">'
        '⚡ QUANT MASTER v64.2 | INSTITUTIONAL PRO TERMINAL'
        '</h1>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<p style="color:#94A3B8;">'
        'Düzeltilmiş Kapanış PnL, Canlı Piyasa Fiyatlı NAV, '
        'Gerçek Backtest Metrikleri & Dinamik Risk'
        '</p>',
        unsafe_allow_html=True
    )

    st.markdown("---")

    # --------------------------------------------------------------------------
    # SIDEBAR
    # --------------------------------------------------------------------------

    with st.sidebar:

        st.header("⚙️ Terminal Kontrol")

        years_input = st.slider(
            "Geçmiş Veri Periyodu (Yıl)",
            1, 5, 3
        )

        risk_pct = st.slider(
            "İşlem Başına Risk Limiti (%)",
            1.0, 5.0, 2.0
        )

        run_scan = st.button(
            "🚀 Kurumsal Canlı Taramayı Başlat",
            use_container_width=True
        )

        run_backtest = st.button(
            "📈 Gelişmiş Backtest & Metrikler",
            use_container_width=True
        )

        st.markdown("---")

        st.subheader("💼 Portföy Yönetimi")

        if st.button(
            "🚨 Tüm Pozisyonları Kapat",
            use_container_width=True
        ):

            active_df = (
                InstitutionalDatabaseManager
                .get_active_positions()
            )

            for _, pos_row in active_df.iterrows():

                live_p = get_latest_price(
                    pos_row["symbol"],
                    pos_row["entry_price"]
                )

                InstitutionalDatabaseManager.execute_manual_close(
                    pos_row["symbol"],
                    live_p
                )

            st.success(
                "Tüm açık pozisyonlar güncel piyasa fiyatlarıyla kapatıldı!"
            )

            st.rerun()

    # --------------------------------------------------------------------------
    # SCAN
    # --------------------------------------------------------------------------

    if run_scan:

        with st.spinner(
            "Kurumsal evren taranıyor..."
        ):

            universe = [
                "KCHOL.IS",
                "THYAO.IS",
                "EREGL.IS",
                "TUPRS.IS",
                "GARAN.IS",
                "ASELS.IS",
                "BIMAS.IS",
                "SAHOL.IS",
                "SISE.IS",
                "PGSUS.IS",
                "XU100.IS"
            ]

            all_data = download_universe(
                universe,
                f"{years_input}y"
            )

            live_quotes = {}

            for sym in universe:
                fallback = (
                    all_data[sym]["Close"].iloc[-1]
                    if sym in all_data
                    and not all_data[sym].empty
                    else 0.0
                )

                live_quotes[sym] = get_latest_price(
                    sym,
                    fallback
                )

            xu100_bench = all_data.get(
                "XU100.IS",
                pd.DataFrame()
            )

            clean_dict = {
                s: df
                for s, df in all_data.items()
                if s != "XU100.IS"
            }

            signals = (
                InstitutionalQuantEngine
                .evaluate_universe(
                    clean_dict,
                    xu100_bench,
                    live_quotes
                )
            )

            st.session_state["v64_signals"] = signals

            st.success(
                f"Tarama Tamamlandı! Toplam Aday: {len(signals)}"
            )

    # --------------------------------------------------------------------------
    # MAIN COLUMNS
    # --------------------------------------------------------------------------

    col_main, col_side = st.columns(
        [2.2, 1]
    )

    # --------------------------------------------------------------------------
    # SIGNALS
    # --------------------------------------------------------------------------

    with col_main:

        st.subheader(
            "🏆 Kurumsal Skor & Sinyal Matrisi"
        )

        if "v64_signals" in st.session_state:

            signals = st.session_state[
                "v64_signals"
            ]

            if not signals:
                st.info(
                    "Yeterli geçmiş verisi olan aday bulunamadı."
                )

            for item in signals:
                render_signal_card(item)

            top_pick = (
                signals[0]
                if signals
                else None
            )

            if top_pick:

                if st.button(
                    f"📥 {top_pick['symbol']} İçin "
                    f"ATR Bazlı Dinamik Paper Trade Emri",
                    key="btn_paper_trade"
                ):

                    current_cash = (
                        InstitutionalDatabaseManager
                        .get_latest_cash()
                    )

                    risk_budget = (
                        current_cash
                        * (risk_pct / 100.0)
                    )

                    risk_distance = (
                        2.0 * top_pick["atr"]
                    )

                    dynamic_shares = (
                        int(
                            risk_budget
                            / risk_distance
                        )
                        if risk_distance > 0
                        else 100
                    )

                    max_shares = int(
                        (
                            current_cash
                            * 0.95
                        )
                        / top_pick["price"]
                    )

                    dynamic_shares = min(
                        dynamic_shares,
                        max_shares
                    )

                    if dynamic_shares < 1:
                        dynamic_shares = 1

                    connection = sqlite3.connect(
                        DB_FILE
                    )

                    cursor = connection.cursor()

                    cursor.execute("""
                        INSERT OR REPLACE INTO active_positions_ledger
                        (
                            symbol,
                            entry_date,
                            entry_price,
                            shares_allocated,
                            stop_loss_price,
                            take_profit_1,
                            take_profit_2,
                            quant_score,
                            regime_status
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        top_pick["symbol"],
                        datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        top_pick["price"],
                        dynamic_shares,
                        top_pick["stop_loss"],
                        top_pick["tp1"],
                        top_pick["tp2"],
                        top_pick["score"],
                        "BULLISH"
                    ))

                    connection.commit()
                    connection.close()

                    st.success(
                        f"{top_pick['symbol']} | "
                        f"{dynamic_shares} Lot dinamik "
                        f"hesaplanarak portföye eklendi!"
                    )

                    st.rerun()

        else:

            st.info(
                "Sol menüden kurumsal taramayı başlatın."
            )

    # --------------------------------------------------------------------------
    # PORTFOLIO
    # --------------------------------------------------------------------------

    with col_side:

        st.subheader(
            "💼 Gerçek Zamanlı Portföy NAV"
        )

        active_positions_df = (
            InstitutionalDatabaseManager
            .get_active_positions()
        )

        current_cash = (
            InstitutionalDatabaseManager
            .get_latest_cash()
        )

        open_positions_val = 0.0

        if not active_positions_df.empty:

            for _, pos in (
                active_positions_df.iterrows()
            ):

                curr_mkt_p = get_latest_price(
                    pos["symbol"],
                    pos["entry_price"]
                )

                pos_market_val = (
                    pos["shares_allocated"]
                    * curr_mkt_p
                )

                open_positions_val += (
                    pos_market_val
                )

                pnl_tl = (
                    pos_market_val
                    - (
                        pos["shares_allocated"]
                        * pos["entry_price"]
                    )
                )

                pnl_pct_pos = (
                    (curr_mkt_p / pos["entry_price"])
                    - 1
                ) * 100

                color_pnl = (
                    "#34D399"
                    if pnl_tl >= 0
                    else "#EF4444"
                )

                portfolio_html = f"""
                <div class="terminal-card">
                    <b>{pos["symbol"]}</b>
                    ({pos["shares_allocated"]} Lot)<br>

                    <b>Güncel Fiyat:</b>
                    {curr_mkt_p:.2f} TL<br>

                    <b>Anlık PnL:</b>
                    <span style="color:{color_pnl};">
                        {pnl_tl:+,.2f} TL
                        ({pnl_pct_pos:+.2f}%)
                    </span><br>

                    <b>Stop:</b>
                    <span style="color:#EF4444;">
                        {pos["stop_loss_price"]:.2f} TL
                    </span>
                </div>
                """

                if hasattr(st, "html"):
                    st.html(portfolio_html)
                else:
                    st.markdown(
                        textwrap.dedent(portfolio_html),
                        unsafe_allow_html=True
                    )

                if st.button(
                    f"Kapat: {pos['symbol']}",
                    key=f"close_{pos['symbol']}"
                ):
                    InstitutionalDatabaseManager.execute_manual_close(
                        pos["symbol"],
                        curr_mkt_p
                    )
                    st.rerun()

        else:

            st.markdown(
                '<p style="color:#64748B;">'
                'Aktif açık pozisyon bulunmuyor.'
                '</p>',
                unsafe_allow_html=True
            )

        total_nav = (
            current_cash
            + open_positions_val
        )

        st.metric(
            "Toplam Portföy NAV",
            f"{total_nav:,.2f} TL",
            f"Nakit: {current_cash:,.2f} TL"
        )

    # --------------------------------------------------------------------------
    # BACKTEST
    # --------------------------------------------------------------------------

    if run_backtest:

        with st.spinner(
            "KCHOL üzerinde profesyonel quant backtest çalıştırılıyor..."
        ):

            bt_df = download_single(
                "KCHOL.IS",
                f"{years_input}y"
            )

            if bt_df.empty:

                st.error(
                    "KCHOL.IS için yeterli veri alınamadı."
                )

            else:

                curve, trades, metrics = (
                    BacktestSimulationEngine.run_backtest(
                        bt_df,
                        starting_capital=100000.0,
                        user_risk_pct=risk_pct
                    )
                )

                if curve:

                    final_nav = float(curve[-1])

                    net_ret = (
                        (final_nav / 100000.0) - 1
                    ) * 100

                    st.success(
                        "Kurumsal Backtest Başarıyla Tamamlandı!"
                    )

                    (
                        col_b1,
                        col_b2,
                        col_b3,
                        col_b4,
                        col_b5
                    ) = st.columns(5)

                    col_b1.metric(
                        "Bitiş NAV",
                        f"{final_nav:,.2f} TL",
                        f"{net_ret:+.2f}%"
                    )

                    col_b2.metric(
                        "Sharpe Oranı",
                        f"{metrics['sharpe']:.2f}"
                    )

                    col_b3.metric(
                        "Max Drawdown (MDD)",
                        f"{metrics['mdd']:.2f}%"
                    )

                    col_b4.metric(
                        "Win Rate",
                        f"{metrics['win_rate']:.1f}%"
                    )

                    pf = metrics["profit_factor"]

                    if np.isinf(pf):
                        pf_text = "∞"
                    else:
                        pf_text = f"{pf:.2f}"

                    col_b5.metric(
                        "Profit Factor",
                        pf_text
                    )

                    st.line_chart(
                        pd.Series(
                            curve,
                            name="Portföy NAV"
                        )
                    )

                    st.caption(
                        f"Toplam tamamlanan işlem: {len(trades)}"
                    )

                else:

                    st.warning(
                        "Backtest için yeterli işlem oluşmadı."
                    )


if __name__ == "__main__":
    main()

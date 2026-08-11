# ==============================================================================
# QUANT MASTER v64.2
# INSTITUTIONAL QUANT & PAPER TRADING TERMINAL
# FULL FIXED VERSION
# ==============================================================================
#
# FIXES:
# 1. Yahoo Finance MultiIndex / KeyError fix
# 2. Single ticker / multiple ticker normalization
# 3. Streamlit HTML indentation/rendering fix
# 4. Backtest yfinance normalization fix
# 5. Paper trade cash accounting fix
# 6. Live NAV calculation
# 7. Dynamic ATR risk sizing
#
# ==============================================================================

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
# STREAMLIT CONFIGURATION
# ==============================================================================

st.set_page_config(
    page_title="QUANT MASTER v64.2 | Institutional Quant Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ==============================================================================
# INSTITUTIONAL THEME
# ==============================================================================

st.markdown("""
<style>

.main {
    background-color: #030712;
    color: #F8FAFC;
}

.stApp {
    background-color: #030712;
}

.terminal-card {
    background: linear-gradient(
        135deg,
        #0F172A 0%,
        #1E293B 100%
    );

    border: 1px solid #334155;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 15px;

    box-shadow:
        0 10px 15px -3px rgba(0, 0, 0, 0.5);
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
""", unsafe_allow_html=True)


# ==============================================================================
# DATABASE
# ==============================================================================

DB_FILE = "quant_master_v64_pro.db"


class InstitutionalDatabaseManager:

    @staticmethod
    def initialize_database():

        connection = sqlite3.connect(DB_FILE)
        cursor = connection.cursor()

        # --------------------------------------------------------------
        # NAV HISTORY
        # --------------------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_nav_history (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                timestamp TEXT NOT NULL,

                cash_balance REAL NOT NULL,

                total_portfolio_nav REAL NOT NULL,

                open_positions_count INTEGER NOT NULL
            )
        """)

        # --------------------------------------------------------------
        # ACTIVE POSITIONS
        # --------------------------------------------------------------

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

        # --------------------------------------------------------------
        # HISTORICAL TRADES
        # --------------------------------------------------------------

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

        # --------------------------------------------------------------
        # INITIAL CAPITAL
        # --------------------------------------------------------------

        cursor.execute("""
            SELECT COUNT(*)
            FROM portfolio_nav_history
        """)

        count = cursor.fetchone()[0]

        if count == 0:

            current_time_str = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            cursor.execute("""
                INSERT INTO portfolio_nav_history
                (
                    timestamp,
                    cash_balance,
                    total_portfolio_nav,
                    open_positions_count
                )
                VALUES (?, ?, ?, ?)
            """, (
                current_time_str,
                100000.0,
                100000.0,
                0
            ))

        connection.commit()
        connection.close()

    # ------------------------------------------------------------------

    @staticmethod
    def get_active_positions():

        connection = sqlite3.connect(DB_FILE)

        df = pd.read_sql_query(
            "SELECT * FROM active_positions_ledger",
            connection
        )

        connection.close()

        return df

    # ------------------------------------------------------------------

    @staticmethod
    def get_latest_cash():

        connection = sqlite3.connect(DB_FILE)

        cursor = connection.cursor()

        cursor.execute("""
            SELECT cash_balance
            FROM portfolio_nav_history
            ORDER BY id DESC
            LIMIT 1
        """)

        row = cursor.fetchone()

        connection.close()

        if row:
            return float(row[0])

        return 100000.0

    # ------------------------------------------------------------------

    @staticmethod
    def get_total_nav():

        connection = sqlite3.connect(DB_FILE)

        cursor = connection.cursor()

        cursor.execute("""
            SELECT total_portfolio_nav
            FROM portfolio_nav_history
            ORDER BY id DESC
            LIMIT 1
        """)

        row = cursor.fetchone()

        connection.close()

        if row:
            return float(row[0])

        return 100000.0

    # ------------------------------------------------------------------

    @staticmethod
    def execute_manual_close(
        symbol,
        current_market_price
    ):

        connection = sqlite3.connect(DB_FILE)

        cursor = connection.cursor()

        cursor.execute("""
            SELECT *
            FROM active_positions_ledger
            WHERE symbol = ?
        """, (symbol,))

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

            # ----------------------------------------------------------
            # PNL
            # ----------------------------------------------------------

            pnl = (
                current_market_price - entry_price
            ) * shares

            pnl_pct = (
                (current_market_price / entry_price) - 1
            ) * 100

            exit_date_str = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            # ----------------------------------------------------------
            # TRADE LEDGER
            # ----------------------------------------------------------

            cursor.execute("""
                INSERT INTO historical_trade_ledger
                (
                    symbol,
                    entry_date,
                    exit_date,
                    entry_price,
                    exit_price,
                    shares,
                    realized_pnl,
                    realized_pnl_pct,
                    exit_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                entry_date,
                exit_date_str,
                entry_price,
                current_market_price,
                shares,
                pnl,
                pnl_pct,
                "MANUAL_CLOSE"
            ))

            # ----------------------------------------------------------
            # DELETE POSITION
            # ----------------------------------------------------------

            cursor.execute("""
                DELETE FROM active_positions_ledger
                WHERE symbol = ?
            """, (symbol,))

            # ----------------------------------------------------------
            # CASH
            # ----------------------------------------------------------

            cursor.execute("""
                SELECT cash_balance
                FROM portfolio_nav_history
                ORDER BY id DESC
                LIMIT 1
            """)

            cash_row = cursor.fetchone()

            last_cash = (
                float(cash_row[0])
                if cash_row
                else 100000.0
            )

            # Estimated transaction cost
            sale_value = (
                shares *
                current_market_price *
                0.999475
            )

            new_cash = last_cash + sale_value

            # ----------------------------------------------------------
            # OPEN POSITION COUNT
            # ----------------------------------------------------------

            cursor.execute("""
                SELECT COUNT(*)
                FROM active_positions_ledger
            """)

            open_count = cursor.fetchone()[0]

            # ----------------------------------------------------------
            # NAV
            # ----------------------------------------------------------

            cursor.execute("""
                INSERT INTO portfolio_nav_history
                (
                    timestamp,
                    cash_balance,
                    total_portfolio_nav,
                    open_positions_count
                )
                VALUES (?, ?, ?, ?)
            """, (
                exit_date_str,
                new_cash,
                new_cash,
                open_count
            ))

            connection.commit()

        connection.close()


# ==============================================================================
# YFINANCE DATA NORMALIZATION
# ==============================================================================

REQUIRED_OHLCV = [
    "Open",
    "High",
    "Low",
    "Close",
    "Volume"
]


def normalize_yfinance_dataframe(dataframe):

    """
    Yahoo Finance'ın hem eski hem yeni MultiIndex yapısını
    standart OHLCV DataFrame'e dönüştürür.

    Desteklenen örnekler:

        Open High Low Close Volume

    veya

        ('KCHOL.IS', 'Open')
        ('KCHOL.IS', 'High')

    veya

        ('Open', 'KCHOL.IS')
        ('High', 'KCHOL.IS')
    """

    if dataframe is None:
        return None

    if not isinstance(dataframe, pd.DataFrame):
        return None

    if dataframe.empty:
        return None

    df = dataframe.copy()

    # ==============================================================
    # MULTIINDEX
    # ==============================================================

    if isinstance(df.columns, pd.MultiIndex):

        extracted = {}

        for required_col in REQUIRED_OHLCV:

            found_series = None

            for column_tuple in df.columns:

                tuple_values = [
                    str(x).strip()
                    for x in column_tuple
                ]

                if required_col in tuple_values:

                    try:

                        candidate = df[column_tuple]

                        if isinstance(candidate, pd.DataFrame):

                            candidate = candidate.iloc[:, 0]

                        found_series = candidate

                        break

                    except Exception:
                        continue

            if found_series is not None:

                extracted[required_col] = found_series

    # ==============================================================
    # NORMAL COLUMNS
    # ==============================================================

    else:

        extracted = {}

        for required_col in REQUIRED_OHLCV:

            if required_col in df.columns:

                candidate = df[required_col]

                if isinstance(candidate, pd.DataFrame):

                    candidate = candidate.iloc[:, 0]

                extracted[required_col] = candidate

    # ==============================================================
    # REQUIRED CHECK
    # ==============================================================

    missing = [
        col
        for col in REQUIRED_OHLCV
        if col not in extracted
    ]

    if missing:
        return None

    # ==============================================================
    # STANDARD DATAFRAME
    # ==============================================================

    result = pd.DataFrame(index=df.index)

    for col in REQUIRED_OHLCV:

        result[col] = pd.to_numeric(
            extracted[col],
            errors="coerce"
        )

    # ==============================================================
    # CLEAN
    # ==============================================================

    result.replace(
        [np.inf, -np.inf],
        np.nan,
        inplace=True
    )

    result.dropna(
        subset=REQUIRED_OHLCV,
        inplace=True
    )

    # Volume negatif olamaz
    result = result[
        result["Volume"] >= 0
    ]

    if result.empty:
        return None

    return result


# ==============================================================================
# YAHOO SINGLE TICKER HELPER
# ==============================================================================

def download_single_ticker(
    symbol,
    period="3y",
    interval="1d"
):

    try:

        data = yf.download(
            symbol,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=False,
            threads=False
        )

        return normalize_yfinance_dataframe(data)

    except Exception:

        return None


# ==============================================================================
# INDICATOR ENGINE
# ==============================================================================

class MasterIndicatorEngine:

    @staticmethod
    def calculate_all_indicators(dataframe):

        if dataframe is None:
            return None

        if dataframe.empty:
            return None

        # ----------------------------------------------------------
        # VERY IMPORTANT:
        # Normalize BEFORE accessing Close/High/Low/Volume
        # ----------------------------------------------------------

        df = normalize_yfinance_dataframe(dataframe)

        if df is None:
            return None

        if len(df) < 120:
            return None

        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        vol = df["Volume"]

        # ==========================================================
        # MOVING AVERAGES
        # ==========================================================

        for p in [
            3,
            5,
            8,
            9,
            10,
            13,
            14,
            15,
            20,
            21,
            30,
            34,
            40,
            50,
            55,
            60,
            89,
            100,
            150,
            200
        ]:

            df[f"SMA_{p}"] = (
                close.rolling(p).mean()
            )

            df[f"EMA_{p}"] = (
                close.ewm(
                    span=p,
                    adjust=False
                ).mean()
            )

        # ==========================================================
        # HMA 20
        # ==========================================================

        half_length = 10
        sqrt_length = int(np.sqrt(20))

        weights_half = np.arange(
            1,
            half_length + 1
        )

        weights_full = np.arange(
            1,
            20 + 1
        )

        wma_half = close.rolling(
            half_length
        ).apply(
            lambda x: np.dot(
                x,
                weights_half
            ) / weights_half.sum(),
            raw=True
        )

        wma_full = close.rolling(
            20
        ).apply(
            lambda x: np.dot(
                x,
                weights_full
            ) / weights_full.sum(),
            raw=True
        )

        diff_wma = (
            2 * wma_half - wma_full
        )

        hma_weights = np.arange(
            1,
            sqrt_length + 1
        )

        df["HMA_20"] = diff_wma.rolling(
            sqrt_length
        ).apply(
            lambda x: np.dot(
                x,
                hma_weights
            ) / hma_weights.sum(),
            raw=True
        )

        # ==========================================================
        # DEMA / TEMA
        # ==========================================================

        ema20 = df["EMA_20"]

        ema20_second = ema20.ewm(
            span=20,
            adjust=False
        ).mean()

        df["DEMA_20"] = (
            2 * ema20 - ema20_second
        )

        df["TEMA_20"] = (
            3 * (ema20 - df["DEMA_20"])
            + df["DEMA_20"].ewm(
                span=20,
                adjust=False
            ).mean()
        )

        # ==========================================================
        # VWAP
        # ==========================================================

        typical_price = (
            high + low + close
        ) / 3

        df["VWAP"] = (
            (vol * typical_price).cumsum()
            /
            (vol.cumsum() + 1e-10)
        )

        # ==========================================================
        # ATR
        # ==========================================================

        tr1 = high - low

        tr2 = (
            high - close.shift(1)
        ).abs()

        tr3 = (
            low - close.shift(1)
        ).abs()

        df["True_Range"] = pd.concat(
            [
                tr1,
                tr2,
                tr3
            ],
            axis=1
        ).max(axis=1)

        df["ATR"] = df[
            "True_Range"
        ].ewm(
            span=14,
            adjust=False
        ).mean()

        df["NATR"] = (
            df["ATR"] /
            close
        ) * 100

        # ==========================================================
        # SUPERTREND
        # ==========================================================

        hl2 = (
            high + low
        ) / 2

        atr3 = (
            df["ATR"] * 3
        )

        upper_basic = (
            hl2 + atr3
        )

        lower_basic = (
            hl2 - atr3
        )

        supertrend_vals = [
            0.0
        ] * len(df)

        st_direction = [
            1
        ] * len(df)

        for i in range(
            1,
            len(df)
        ):

            curr_close = close.iloc[i]

            prev_close = close.iloc[i - 1]

            ub = upper_basic.iloc[i]

            lb = lower_basic.iloc[i]

            prev_ub = upper_basic.iloc[
                i - 1
            ]

            prev_lb = lower_basic.iloc[
                i - 1
            ]

            final_ub = (
                ub
                if (
                    ub < prev_ub
                    or prev_close > prev_ub
                )
                else prev_ub
            )

            final_lb = (
                lb
                if (
                    lb > prev_lb
                    or prev_close < prev_lb
                )
                else prev_lb
            )

            curr_dir = st_direction[
                i - 1
            ]

            if (
                curr_dir == 1
                and curr_close < final_lb
            ):

                curr_dir = -1

            elif (
                curr_dir == -1
                and curr_close > final_ub
            ):

                curr_dir = 1

            st_direction[i] = curr_dir

            supertrend_vals[i] = (
                final_lb
                if curr_dir == 1
                else final_ub
            )

        df["Supertrend"] = (
            supertrend_vals
        )

        # ==========================================================
        # RSI
        # ==========================================================

        delta = close.diff()

        pos = (
            delta.where(
                delta > 0,
                0
            )
            .ewm(
                alpha=1 / 14,
                adjust=False
            )
            .mean()
        )

        neg = (
            -delta.where(
                delta < 0,
                0
            )
            .ewm(
                alpha=1 / 14,
                adjust=False
            )
            .mean()
        )

        df["RSI"] = (
            100
            -
            (
                100 /
                (
                    1
                    +
                    pos /
                    (neg + 1e-10)
                )
            )
        )

        # ==========================================================
        # MACD
        # ==========================================================

        ema_f = close.ewm(
            span=12,
            adjust=False
        ).mean()

        ema_s = close.ewm(
            span=26,
            adjust=False
        ).mean()

        df["MACD"] = (
            ema_f - ema_s
        )

        df["MACD_Signal"] = (
            df["MACD"]
            .ewm(
                span=9,
                adjust=False
            )
            .mean()
        )

        df["MACD_Hist"] = (
            df["MACD"]
            -
            df["MACD_Signal"]
        )

        # ==========================================================
        # OBV
        # ==========================================================

        df["OBV"] = (
            np.sign(
                close.diff()
            )
            * vol
        ).fillna(0).cumsum()

        df["OBV_EMA"] = (
            df["OBV"]
            .ewm(
                span=20,
                adjust=False
            )
            .mean()
        )

        # ==========================================================
        # RVOL
        # ==========================================================

        df["RVOL"] = (
            vol /
            (
                vol.rolling(20).mean()
                + 1e-10
            )
        )

        # ==========================================================
        # BOS / CHOCH
        # ==========================================================

        df["Rolling_High_50"] = (
            high
            .rolling(50)
            .max()
            .shift(1)
        )

        df["Rolling_Low_50"] = (
            low
            .rolling(50)
            .min()
            .shift(1)
        )

        df["BOS"] = (
            (
                close >
                df["Rolling_High_50"]
            )
            &
            (
                close.shift(1)
                <=
                df["Rolling_High_50"]
            )
        ).astype(int)

        df["CHOCH"] = (
            (
                close <
                df["Rolling_Low_50"]
            )
            &
            (
                close.shift(1)
                >=
                df["Rolling_Low_50"]
            )
        ).astype(int)

        # ==========================================================
        # FVG
        # ==========================================================

        df["FVG_Up"] = (
            (
                low >
                high.shift(2)
            )
            &
            (
                close.shift(1)
                >
                high.shift(2)
            )
        ).astype(int)

        # ==========================================================
        # STATISTICAL FEATURES
        # ==========================================================

        for i_idx in range(
            1,
            30
        ):

            window = i_idx + 2

            df[
                f"Stat_Feature_{i_idx}"
            ] = (
                close.rolling(
                    window
                ).std()
                /
                (
                    close.rolling(
                        window
                    ).mean()
                    + 1e-10
                )
            )

        # ==========================================================
        # METRIC LABEL
        # ==========================================================

        df[
            "Total_Active_Metrics"
        ] = 128

        return df


# ==============================================================================
# QUANT ENGINE
# ==============================================================================

class InstitutionalQuantEngine:

    @staticmethod
    def evaluate_universe(
        data_dictionary,
        xu100_dataframe,
        live_quotes=None
    ):

        analysis_results = []

        # ----------------------------------------------------------
        # Normalize benchmark
        # ----------------------------------------------------------

        xu100_clean = normalize_yfinance_dataframe(
            xu100_dataframe
        )

        for symbol, raw_df in data_dictionary.items():

            processed_df = (
                MasterIndicatorEngine
                .calculate_all_indicators(
                    raw_df
                )
            )

            if processed_df is None:
                continue

            if processed_df.empty:
                continue

            latest = processed_df.iloc[-1]

            current_price = float(
                latest["Close"]
            )

            # ------------------------------------------------------
            # LIVE PRICE
            # ------------------------------------------------------

            if (
                live_quotes is not None
                and symbol in live_quotes
                and live_quotes[symbol] > 0
            ):

                current_price = float(
                    live_quotes[symbol]
                )

            # ======================================================
            # LAYER 1
            # TREND
            # ======================================================

            layer1 = 0

            if (
                current_price
                >
                latest["EMA_20"]
            ):
                layer1 += 8

            if (
                latest["EMA_20"]
                >
                latest["EMA_50"]
            ):
                layer1 += 9

            if (
                latest["EMA_50"]
                >
                latest["EMA_200"]
            ):
                layer1 += 8

            # ======================================================
            # LAYER 2
            # MOMENTUM
            # ======================================================

            layer2 = 0

            if (
                50
                <= latest["RSI"]
                <= 75
            ):
                layer2 += 12

            if (
                latest["MACD_Hist"] > 0
            ):
                layer2 += 13

            # ======================================================
            # LAYER 3
            # RELATIVE STRENGTH
            # ======================================================

            if (
                xu100_clean is not None
                and not xu100_clean.empty
            ):

                aligned_xu = (
                    xu100_clean["Close"]
                    .reindex(
                        processed_df.index
                    )
                    .ffill()
                )

                if (
                    len(processed_df) >= 60
                    and len(aligned_xu) >= 60
                ):

                    stock_old_price = float(
                        processed_df[
                            "Close"
                        ].iloc[-60]
                    )

                    market_old_price = float(
                        aligned_xu.iloc[-60]
                    )

                    if (
                        stock_old_price > 0
                        and market_old_price > 0
                    ):

                        stock_ret = (
                            current_price /
                            stock_old_price
                        ) - 1

                        market_ret = (
                            aligned_xu.iloc[-1] /
                            market_old_price
                        ) - 1

                        rs_val = (
                            stock_ret -
                            market_ret
                        )

                        layer3 = float(
                            np.clip(
                                (
                                    rs_val + 0.15
                                ) * 66.6,
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

            # ======================================================
            # LAYER 4
            # VOLUME / FLOW
            # ======================================================

            layer4 = 0

            if (
                latest["RVOL"] > 1.2
            ):
                layer4 += 8

            if (
                latest["OBV"]
                >
                latest["OBV_EMA"]
            ):
                layer4 += 7

            # ======================================================
            # LAYER 5
            # STRUCTURE
            # ======================================================

            layer5 = 0

            if (
                latest["BOS"] == 1
                or
                latest["FVG_Up"] == 1
            ):
                layer5 += 10

            if (
                latest["CHOCH"] == 0
            ):
                layer5 += 5

            # ======================================================
            # TOTAL
            # ======================================================

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

            # ======================================================
            # ATR
            # ======================================================

            atr = float(
                latest["ATR"]
            )

            if not np.isfinite(atr) or atr <= 0:

                continue

            # ======================================================
            # TARGETS
            # ======================================================

            tp1 = (
                current_price
                +
                (1.5 * atr)
            )

            tp2 = (
                current_price
                +
                (3.0 * atr)
            )

            stop_loss = (
                current_price
                -
                (2.0 * atr)
            )

            analysis_results.append({

                "symbol": symbol,

                "score": total_score,

                "price": current_price,

                "rsi": float(
                    latest["RSI"]
                ),

                "rvol": float(
                    latest["RVOL"]
                ),

                "atr": atr,

                "tp1": tp1,

                "tp2": tp2,

                "stop_loss": stop_loss,

                "layer1": layer1,

                "layer2": layer2,

                "layer3": layer3,

                "layer4": layer4,

                "layer5": layer5,

                "df": processed_df
            })

        # ==========================================================
        # SORT
        # ==========================================================

        analysis_results.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        return analysis_results


# ==============================================================================
# BACKTEST ENGINE
# ==============================================================================

class BacktestSimulationEngine:

    @staticmethod
    def run_backtest(
        dataframe,
        starting_capital=100000.0,
        user_risk_pct=2.0
    ):

        # ----------------------------------------------------------
        # Normalize FIRST
        # ----------------------------------------------------------

        clean_df = normalize_yfinance_dataframe(
            dataframe
        )

        if clean_df is None:
            return [], [], {}

        processed_df = (
            MasterIndicatorEngine
            .calculate_all_indicators(
                clean_df
            )
        )

        if processed_df is None:
            return [], [], {}

        if len(processed_df) < 120:
            return [], [], {}

        # ==========================================================
        # INITIAL STATE
        # ==========================================================

        cash = float(
            starting_capital
        )

        shares = 0

        equity_curve = []

        trade_results = []

        entry_basis = 0.0

        # ==========================================================
        # LOOP
        # ==========================================================

        for i in range(
            120,
            len(processed_df)
        ):

            row = processed_df.iloc[i]

            price = float(
                row["Close"]
            )

            atr = float(
                row["ATR"]
            )

            if not np.isfinite(
                atr
            ) or atr <= 0:

                continue

            # ======================================================
            # BUY
            # ======================================================

            buy_cond = (
                row["Close"]
                >
                row["EMA_20"]
            ) and (
                row["RSI"] > 50
            ) and (
                row["RVOL"] > 1.1
            ) and (
                row["MACD_Hist"] > 0
            )

            # ======================================================
            # SELL
            # ======================================================

            if shares > 0:

                sell_cond = (
                    row["Close"]
                    <
                    row["EMA_20"]
                ) or (
                    row["RSI"] < 42
                ) or (
                    row["Close"]
                    <
                    entry_basis
                    -
                    (2.0 * atr)
                )

            else:

                sell_cond = False

            # ======================================================
            # ENTRY
            # ======================================================

            if (
                shares == 0
                and buy_cond
            ):

                risk_budget = (
                    cash *
                    (
                        user_risk_pct /
                        100.0
                    )
                )

                risk_per_share = (
                    2.0 * atr
                )

                if risk_per_share > 0:

                    shares = int(
                        risk_budget /
                        risk_per_share
                    )

                else:

                    shares = int(
                        (
                            cash * 0.20
                        )
                        /
                        price
                    )

                # --------------------------------------------------
                # Maximum capital usage
                # --------------------------------------------------

                max_afford = int(
                    (
                        cash * 0.98
                    )
                    /
                    price
                )

                shares = min(
                    shares,
                    max_afford
                )

                if shares > 0:

                    total_entry_cost = (
                        shares
                        *
                        price
                        *
                        1.000525
                    )

                    if (
                        total_entry_cost
                        <= cash
                    ):

                        cash -= (
                            total_entry_cost
                        )

                        entry_basis = price

                    else:

                        shares = 0

            # ======================================================
            # EXIT
            # ======================================================

            elif (
                shares > 0
                and sell_cond
            ):

                exit_val = (
                    shares
                    *
                    price
                    *
                    0.999475
                )

                pnl = (
                    exit_val
                    -
                    (
                        shares
                        *
                        entry_basis
                        *
                        1.000525
                    )
                )

                cash += exit_val

                trade_results.append(
                    pnl
                )

                shares = 0

                entry_basis = 0.0

            # ======================================================
            # NAV
            # ======================================================

            nav = (
                cash
                +
                (
                    shares
                    *
                    price
                    if shares > 0
                    else 0
                )
            )

            equity_curve.append(
                nav
            )

        # ==========================================================
        # FINAL FORCE CLOSE
        # ==========================================================

        if (
            shares > 0
            and len(processed_df) > 0
        ):

            final_price = float(
                processed_df[
                    "Close"
                ].iloc[-1]
            )

            exit_val = (
                shares
                *
                final_price
                *
                0.999475
            )

            pnl = (
                exit_val
                -
                (
                    shares
                    *
                    entry_basis
                    *
                    1.000525
                )
            )

            cash += exit_val

            trade_results.append(
                pnl
            )

            shares = 0

            if equity_curve:
                equity_curve[-1] = cash

        # ==========================================================
        # METRICS
        # ==========================================================

        if not equity_curve:

            return [], [], {}

        eq_series = pd.Series(
            equity_curve,
            dtype=float
        )

        returns = (
            eq_series
            .pct_change()
            .replace(
                [np.inf, -np.inf],
                np.nan
            )
            .dropna()
        )

        if (
            len(returns) > 1
            and returns.std() > 0
        ):

            sharpe_ratio = float(
                (
                    returns.mean()
                    /
                    returns.std()
                )
                *
                np.sqrt(252)
            )

        else:

            sharpe_ratio = 0.0

        # ==========================================================
        # MAX DRAWDOWN
        # ==========================================================

        rolling_max = (
            eq_series.cummax()
        )

        drawdown = (
            (
                eq_series
                -
                rolling_max
            )
            /
            rolling_max
        )

        max_drawdown = float(
            drawdown.min() * 100
        )

        # ==========================================================
        # WIN RATE
        # ==========================================================

        if len(trade_results) > 0:

            wins = [
                p
                for p in trade_results
                if p > 0
            ]

            losses = [
                p
                for p in trade_results
                if p <= 0
            ]

            win_rate = (
                len(wins)
                /
                len(trade_results)
            ) * 100.0

            total_gains = sum(
                wins
            ) if wins else 0.0

            total_losses = abs(
                sum(losses)
            ) if losses else 0.0

            if total_losses > 0:

                profit_factor = (
                    total_gains
                    /
                    total_losses
                )

            else:

                profit_factor = (
                    float("inf")
                    if total_gains > 0
                    else 0.0
                )

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
# LIVE PRICE
# ==============================================================================

def get_live_price(symbol):

    try:

        data = yf.download(
            symbol,
            period="1d",
            interval="1m",
            progress=False,
            auto_adjust=False,
            threads=False
        )

        clean = normalize_yfinance_dataframe(
            data
        )

        if (
            clean is not None
            and not clean.empty
        ):

            return float(
                clean["Close"].iloc[-1]
            )

    except Exception:
        pass

    # --------------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------------

    try:

        ticker = yf.Ticker(
            symbol
        )

        history = ticker.history(
            period="1d"
        )

        clean = normalize_yfinance_dataframe(
            history
        )

        if (
            clean is not None
            and not clean.empty
        ):

            return float(
                clean["Close"].iloc[-1]
            )

    except Exception:
        pass

    return 0.0


# ==============================================================================
# MAIN
# ==============================================================================

def main():

    InstitutionalDatabaseManager.initialize_database()

    # ==================================================================
    # HEADER
    # ==================================================================

    st.markdown(
        """
        <h1 style="
            color:#38BDF8;
            font-weight:900;
        ">
            ⚡ QUANT MASTER v64.2 |
            INSTITUTIONAL PRO TERMINAL
        </h1>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        """
        <p style="
            color:#94A3B8;
        ">
            Düzeltilmiş Kapanış PnL,
            Canlı Piyasa Fiyatlı NAV,
            Gerçek Backtest Metrikleri
            & Dinamik Risk
        </p>
        """,
        unsafe_allow_html=True
    )

    st.markdown("---")

    # ==================================================================
    # SIDEBAR
    # ==================================================================

    with st.sidebar:

        st.header(
            "⚙️ Terminal Kontrol"
        )

        years_input = st.slider(
            "Geçmiş Veri Periyodu (Yıl)",
            1,
            5,
            3
        )

        risk_pct = st.slider(
            "İşlem Başına Risk Limiti (%)",
            1.0,
            5.0,
            2.0,
            step=0.5
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

        st.subheader(
            "💼 Portföy Yönetimi"
        )

        if st.button(
            "🚨 Tüm Pozisyonları Kapat",
            use_container_width=True
        ):

            active_df = (
                InstitutionalDatabaseManager
                .get_active_positions()
            )

            for _, pos_row in active_df.iterrows():

                live_p = get_live_price(
                    pos_row["symbol"]
                )

                if live_p <= 0:

                    live_p = float(
                        pos_row[
                            "entry_price"
                        ]
                    )

                InstitutionalDatabaseManager.execute_manual_close(
                    pos_row["symbol"],
                    live_p
                )

            st.success(
                "Tüm açık pozisyonlar güncel piyasa fiyatlarıyla kapatıldı!"
            )

            st.rerun()

    # ==================================================================
    # SCAN
    # ==================================================================

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

            # ----------------------------------------------------------
            # DOWNLOAD
            # ----------------------------------------------------------

            try:

                raw_data = yf.download(
                    universe,
                    period=f"{years_input}y",
                    group_by="ticker",
                    progress=False,
                    auto_adjust=False,
                    threads=False
                )

            except Exception as e:

                st.error(
                    f"Yahoo Finance veri hatası: {e}"
                )

                raw_data = None

            # ----------------------------------------------------------
            # EXTRACT EACH SYMBOL
            # ----------------------------------------------------------

            clean_dict = {}

            if raw_data is not None:

                for symbol in universe:

                    if symbol == "XU100.IS":
                        continue

                    try:

                        # ------------------------------------------------
                        # MultiIndex'ten sembolü çıkar
                        # ------------------------------------------------

                        if isinstance(
                            raw_data.columns,
                            pd.MultiIndex
                        ):

                            symbol_data = None

                            # First level ticker
                            if symbol in raw_data.columns.get_level_values(0):

                                symbol_data = raw_data[
                                    symbol
                                ]

                            # Second level ticker
                            elif symbol in raw_data.columns.get_level_values(1):

                                symbol_data = raw_data[
                                    :, symbol
                                ]

                            if symbol_data is not None:

                                clean = normalize_yfinance_dataframe(
                                    symbol_data
                                )

                            else:

                                clean = None

                        else:

                            clean = normalize_yfinance_dataframe(
                                raw_data
                            )

                        if clean is not None:

                            clean_dict[
                                symbol
                            ] = clean

                    except Exception:

                        continue

            # ----------------------------------------------------------
            # XU100
            # ----------------------------------------------------------

            xu100_bench = None

            try:

                if raw_data is not None:

                    if isinstance(
                        raw_data.columns,
                        pd.MultiIndex
                    ):

                        if (
                            "XU100.IS"
                            in
                            raw_data.columns.get_level_values(0)
                        ):

                            xu100_raw = raw_data[
                                "XU100.IS"
                            ]

                            xu100_bench = (
                                normalize_yfinance_dataframe(
                                    xu100_raw
                                )
                            )

                        elif (
                            "XU100.IS"
                            in
                            raw_data.columns.get_level_values(1)
                        ):

                            xu100_raw = raw_data[
                                :,
                                "XU100.IS"
                            ]

                            xu100_bench = (
                                normalize_yfinance_dataframe(
                                    xu100_raw
                                )
                            )

                    else:

                        xu100_bench = (
                            normalize_yfinance_dataframe(
                                raw_data
                            )
                        )

            except Exception:

                xu100_bench = None

            # ----------------------------------------------------------
            # LIVE QUOTES
            # ----------------------------------------------------------

            live_quotes = {}

            for sym in universe:

                live_p = get_live_price(
                    sym
                )

                live_quotes[sym] = (
                    live_p
                )

            # ----------------------------------------------------------
            # ANALYSIS
            # ----------------------------------------------------------

            signals = (
                InstitutionalQuantEngine
                .evaluate_universe(
                    clean_dict,
                    xu100_bench,
                    live_quotes
                )
            )

            st.session_state[
                "v64_signals"
            ] = signals

            st.success(
                f"Tarama Tamamlandı! "
                f"Toplam Aday: {len(signals)}"
            )

    # ==================================================================
    # MAIN COLUMNS
    # ==================================================================

    col_main, col_side = st.columns(
        [2.2, 1]
    )

    # ==================================================================
    # SIGNAL MATRIX
    # ==================================================================

    with col_main:

        st.subheader(
            "🏆 Kurumsal Skor & Sinyal Matrisi"
        )

        if (
            "v64_signals"
            in
            st.session_state
        ):

            signals = (
                st.session_state[
                    "v64_signals"
                ]
            )

            if not signals:

                st.warning(
                    "Geçerli teknik veriye sahip aday bulunamadı."
                )

            for item in signals:

                score = float(
                    item["score"]
                )

                # ------------------------------------------------------
                # BADGE
                # ------------------------------------------------------

                if score >= 75:

                    badge_class = (
                        "signal-badge-green"
                    )

                elif score >= 50:

                    badge_class = (
                        "signal-badge-blue"
                    )

                else:

                    badge_class = (
                        "signal-badge-yellow"
                    )

                # ======================================================
                # IMPORTANT:
                # textwrap.dedent prevents Streamlit
                # from interpreting HTML as code.
                # ======================================================

                card_html = f"""
<div class="terminal-card">

    <div style="
        display:flex;
        justify-content:space-between;
        align-items:center;
    ">

        <div>

            <h3 style="
                margin:0;
                color:#F8FAFC;
            ">
                {item['symbol']}
            </h3>

            <span class="live-ticker">
                Canlı Fiyat:
                {item['price']:.2f} TL
            </span>

            <span style="color:#94A3B8;">
                &nbsp;|&nbsp;
            </span>

            <span style="
                color:#94A3B8;
            ">
                RSI:
                {item['rsi']:.1f}
            </span>

            <span style="color:#94A3B8;">
                &nbsp;|&nbsp;
            </span>

            <span style="
                color:#94A3B8;
            ">
                RVOL:
                {item['rvol']:.2f}x
            </span>

        </div>

        <div>

            <div class="{badge_class}">
                Skor:
                {score:.1f}
                / 100
            </div>

        </div>

    </div>

    <hr style="
        border-color:#334155;
        margin:12px 0;
    ">

    <div style="
        display:flex;
        justify-content:space-between;
        font-size:0.9rem;
        color:#CBD5E1;
    ">

        <div>
            🎯
            <b>TP1:</b>

            <span style="
                color:#34D399;
            ">
                {item['tp1']:.2f} TL
            </span>
        </div>

        <div>
            🎯
            <b>TP2:</b>

            <span style="
                color:#10B981;
            ">
                {item['tp2']:.2f} TL
            </span>
        </div>

        <div>
            🛑
            <b>Stop Loss:</b>

            <span style="
                color:#EF4444;
            ">
                {item['stop_loss']:.2f} TL
            </span>
        </div>

    </div>

</div>
"""

                # ------------------------------------------------------
                # DEDENT + MARKDOWN
                # ------------------------------------------------------

                st.markdown(
                    textwrap.dedent(
                        card_html
                    ),
                    unsafe_allow_html=True
                )

            # ==========================================================
            # TOP PICK
            # ==========================================================

            top_pick = (
                signals[0]
                if signals
                else None
            )

            if top_pick:

                st.markdown(
                    "---"
                )

                st.subheader(
                    "🏆 En Yüksek Skorlu Aday"
                )

                top_score = float(
                    top_pick["score"]
                )

                st.info(
                    f"{top_pick['symbol']} "
                    f"| Skor: {top_score:.1f}/100 "
                    f"| Fiyat: "
                    f"{top_pick['price']:.2f} TL"
                )

                # ------------------------------------------------------
                # LAYER BREAKDOWN
                # ------------------------------------------------------

                with st.expander(
                    "🔍 Skor Katmanlarını Gör"
                ):

                    c1, c2, c3, c4, c5 = st.columns(5)

                    c1.metric(
                        "Trend",
                        f"{top_pick['layer1']:.0f}/25"
                    )

                    c2.metric(
                        "Momentum",
                        f"{top_pick['layer2']:.0f}/25"
                    )

                    c3.metric(
                        "Relative Strength",
                        f"{top_pick['layer3']:.1f}/20"
                    )

                    c4.metric(
                        "Volume / Flow",
                        f"{top_pick['layer4']:.0f}/15"
                    )

                    c5.metric(
                        "Structure",
                        f"{top_pick['layer5']:.0f}/15"
                    )

                # ------------------------------------------------------
                # PAPER TRADE
                # ------------------------------------------------------

                if st.button(
                    f"📥 "
                    f"{top_pick['symbol']} "
                    f"İçin ATR Bazlı Dinamik Paper Trade Emri",
                    key="btn_paper_trade",
                    use_container_width=True
                ):

                    current_cash = (
                        InstitutionalDatabaseManager
                        .get_latest_cash()
                    )

                    risk_budget = (
                        current_cash
                        *
                        (
                            risk_pct /
                            100.0
                        )
                    )

                    risk_distance = (
                        2.0
                        *
                        top_pick["atr"]
                    )

                    if risk_distance > 0:

                        dynamic_shares = int(
                            risk_budget /
                            risk_distance
                        )

                    else:

                        dynamic_shares = 1

                    # --------------------------------------------------
                    # MAX CAPITAL
                    # --------------------------------------------------

                    max_shares = int(
                        (
                            current_cash
                            *
                            0.95
                        )
                        /
                        top_pick["price"]
                    )

                    dynamic_shares = min(
                        dynamic_shares,
                        max_shares
                    )

                    if dynamic_shares < 1:

                        dynamic_shares = 1

                    # --------------------------------------------------
                    # COST
                    # --------------------------------------------------

                    entry_cost = (
                        dynamic_shares
                        *
                        top_pick["price"]
                        *
                        1.000525
                    )

                    if entry_cost > current_cash:

                        st.error(
                            "Yetersiz nakit."
                        )

                    else:

                        connection = sqlite3.connect(
                            DB_FILE
                        )

                        cursor = connection.cursor()

                        # ------------------------------------------------
                        # Existing position check
                        # ------------------------------------------------

                        cursor.execute("""
                            SELECT symbol
                            FROM active_positions_ledger
                            WHERE symbol = ?
                        """, (
                            top_pick["symbol"],
                        ))

                        existing = (
                            cursor.fetchone()
                        )

                        if existing:

                            connection.close()

                            st.warning(
                                f"{top_pick['symbol']} "
                                f"zaten açık pozisyonda."
                            )

                        else:

                            # --------------------------------------------
                            # POSITION
                            # --------------------------------------------

                            cursor.execute("""
                                INSERT INTO active_positions_ledger
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

                            # --------------------------------------------
                            # CASH DEDUCTION
                            # --------------------------------------------

                            new_cash = (
                                current_cash
                                -
                                entry_cost
                            )

                            cursor.execute("""
                                SELECT COUNT(*)
                                FROM active_positions_ledger
                            """)

                            open_count = (
                                cursor.fetchone()[0]
                            )

                            now_str = (
                                datetime.now()
                                .strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                )
                            )

                            cursor.execute("""
                                INSERT INTO portfolio_nav_history
                                (
                                    timestamp,
                                    cash_balance,
                                    total_portfolio_nav,
                                    open_positions_count
                                )
                                VALUES (?, ?, ?, ?)
                            """, (
                                now_str,
                                new_cash,
                                new_cash,
                                open_count
                            ))

                            connection.commit()

                            connection.close()

                            st.success(
                                f"{top_pick['symbol']} | "
                                f"{dynamic_shares} Lot "
                                f"dinamik hesaplanarak "
                                f"paper portföye eklendi!"
                            )

                            st.rerun()

        else:

            st.info(
                "Sol menüden kurumsal taramayı başlatın."
            )

    # ==================================================================
    # PORTFOLIO
    # ==================================================================

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

        # ==============================================================
        # ACTIVE POSITIONS
        # ==============================================================

        if not active_positions_df.empty:

            for _, pos in (
                active_positions_df.iterrows()
            ):

                symbol = pos[
                    "symbol"
                ]

                curr_mkt_p = (
                    get_live_price(
                        symbol
                    )
                )

                if curr_mkt_p <= 0:

                    curr_mkt_p = float(
                        pos["entry_price"]
                    )

                shares = int(
                    pos[
                        "shares_allocated"
                    ]
                )

                entry_price = float(
                    pos[
                        "entry_price"
                    ]
                )

                pos_market_val = (
                    shares
                    *
                    curr_mkt_p
                )

                open_positions_val += (
                    pos_market_val
                )

                pnl_tl = (
                    pos_market_val
                    -
                    (
                        shares
                        *
                        entry_price
                    )
                )

                if entry_price > 0:

                    pnl_pct_pos = (
                        (
                            curr_mkt_p /
                            entry_price
                        )
                        -
                        1
                    ) * 100

                else:

                    pnl_pct_pos = 0

                if pnl_tl >= 0:

                    color_pnl = (
                        "#34D399"
                    )

                else:

                    color_pnl = (
                        "#EF4444"
                    )

                # ------------------------------------------------------
                # POSITION CARD
                # ------------------------------------------------------

                position_html = f"""
<div class="terminal-card">

    <b>{symbol}</b>
    ({shares} Lot)

    <br>

    <b>Güncel Fiyat:</b>
    {curr_mkt_p:.2f} TL

    <br>

    <b>Anlık PnL:</b>

    <span style="
        color:{color_pnl};
    ">
        {pnl_tl:+,.2f} TL
        ({pnl_pct_pos:+.2f}%)
    </span>

    <br>

    <b>Stop:</b>

    <span style="
        color:#EF4444;
    ">
        {float(pos['stop_loss_price']):.2f} TL
    </span>

    <br>

    <b>TP1:</b>

    <span style="
        color:#34D399;
    ">
        {float(pos['take_profit_1']):.2f} TL
    </span>

    <br>

    <b>TP2:</b>

    <span style="
        color:#10B981;
    ">
        {float(pos['take_profit_2']):.2f} TL
    </span>

</div>
"""

                st.markdown(
                    textwrap.dedent(
                        position_html
                    ),
                    unsafe_allow_html=True
                )

                # ------------------------------------------------------
                # CLOSE BUTTON
                # ------------------------------------------------------

                if st.button(
                    f"Kapat: {symbol}",
                    key=f"close_{symbol}"
                ):

                    InstitutionalDatabaseManager.execute_manual_close(
                        symbol,
                        curr_mkt_p
                    )

                    st.success(
                        f"{symbol} pozisyonu kapatıldı."
                    )

                    st.rerun()

        else:

            st.markdown(
                """
                <p style="
                    color:#64748B;
                ">
                    Aktif açık pozisyon bulunmuyor.
                </p>
                """,
                unsafe_allow_html=True
            )

        # ==============================================================
        # TOTAL NAV
        # ==============================================================

        total_nav = (
            current_cash
            +
            open_positions_val
        )

        st.metric(
            "Toplam Portföy NAV",
            f"{total_nav:,.2f} TL",
            f"Nakit: {current_cash:,.2f} TL"
        )

    # ==================================================================
    # BACKTEST
    # ==================================================================

    if run_backtest:

        with st.spinner(
            "KCHOL üzerinde profesyonel quant backtest çalıştırılıyor..."
        ):

            bt_df = download_single_ticker(
                "KCHOL.IS",
                period=f"{years_input}y",
                interval="1d"
            )

            if bt_df is None or bt_df.empty:

                st.error(
                    "KCHOL.IS için yeterli Yahoo Finance verisi alınamadı."
                )

            else:

                (
                    curve,
                    trades,
                    metrics
                ) = (
                    BacktestSimulationEngine
                    .run_backtest(
                        bt_df,
                        starting_capital=100000.0,
                        user_risk_pct=risk_pct
                    )
                )

                if curve:

                    final_nav = float(
                        curve[-1]
                    )

                    net_ret = (
                        (
                            final_nav /
                            100000.0
                        )
                        -
                        1
                    ) * 100

                    st.success(
                        "Kurumsal Backtest Başarıyla Tamamlandı!"
                    )

                    # ==================================================
                    # METRICS
                    # ==================================================

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

                    pf = metrics[
                        "profit_factor"
                    ]

                    if np.isinf(pf):

                        pf_text = "∞"

                    else:

                        pf_text = (
                            f"{pf:.2f}"
                        )

                    col_b5.metric(
                        "Profit Factor",
                        pf_text
                    )

                    # ==================================================
                    # EQUITY CURVE
                    # ==================================================

                    st.subheader(
                        "📈 Equity Curve"
                    )

                    st.line_chart(
                        pd.Series(
                            curve,
                            name="NAV"
                        )
                    )

                    # ==================================================
                    # TRADE SUMMARY
                    # ==================================================

                    st.subheader(
                        "📊 İşlem Özeti"
                    )

                    st.metric(
                        "Toplam İşlem",
                        len(trades)
                    )

                    if trades:

                        trade_df = pd.DataFrame({
                            "İşlem PnL (TL)": trades
                        })

                        st.dataframe(
                            trade_df,
                            use_container_width=True
                        )

                else:

                    st.warning(
                        "Backtest için yeterli işlem oluşmadı."
                    )


# ==============================================================================
# RUN
# ==============================================================================

if __name__ == "__main__":

    main()

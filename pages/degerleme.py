import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime
import yfinance as yf

DB_FILE = "quant_master_v64.db"

class ValuationEngine:
    @staticmethod
    def get_bist100_universe():
        # Kesin ve eksiksiz BIST 100 sembol listesi
        return sorted(list(set([
            "AEFES.IS", "AGHOL.IS", "AHGAZ.IS", "AKBNK.IS", "AKCNS.IS", "AKFGY.IS", "AKSA.IS", "AKSEN.IS", 
            "ALARK.IS", "ALBRK.IS", "ALFAS.IS", "ARCLK.IS", "ASELS.IS", "ASTOR.IS", "BERA.IS", "BIMAS.IS", 
            "BOBET.IS", "BRSAN.IS", "BRYAT.IS", "BUCIM.IS", "CANTE.IS", "CCOLA.IS", "CIMSA.IS", "CWENE.IS", 
            "DEVA.IS", "DOAS.IS", "DOHOL.IS", "ECILC.IS", "ECZYT.IS", "EGEEN.IS", "EKGYO.IS", "ENJSA.IS", 
            "ENKAI.IS", "EREGL.IS", "EUPWR.IS", "EYYG.IS", "FROTO.IS", "GARAN.IS", "GENIL.IS", "GESAN.IS", 
            "GLYHO.IS", "GOKNR.IS", "GUBRF.IS", "HALKB.IS", "HEKTS.IS", "IPEKE.IS", "ISCTR.IS", "ISDMR.IS", 
            "ISMEN.IS", "IZMDC.IS", "KCHOL.IS", "KMPUR.IS", "KONTR.IS", "KONYA.IS", "KORDS.IS", "KOZAA.IS", 
            "KOZAL.IS", "KRDMD.IS", "KTLEV.IS", "KZBGY.IS", "MAVI.IS", "MGROS.IS", "MIATK.IS", "MPARK.IS", 
            "ODAS.IS", "ONCSM.IS", "OTKAR.IS", "OYAKC.IS", "PATEK.IS", "PCILT.IS", "PETKM.IS", "PGSUS.IS", 
            "QUAGR.IS", "REEDR.IS", "SAHOL.IS", "SASA.IS", "SDTTR.IS", "SISE.IS", "SKBNK.IS", "SMRTG.IS", 
            "SOKM.IS", "TAVHL.IS", "TCELL.IS", "THYAO.IS", "TKFEN.IS", "TMSN.IS", "TOASO.IS", "TSKB.IS", 
            "TTKOM.IS", "TTRAK.IS", "TUPRS.IS", "ULKER.IS", "VAKBN.IS", "VESBE.IS", "VESTL.IS", "YEOTK.IS", 
            "YKBNK.IS", "YYLGD.IS", "ZOREN.IS"
        ])))

    @staticmethod
    def calculate_portfolio_valuation(current_prices=None):
        """
        Portföyün nakit, açık pozisyon piyasa değeri (MTM) ve net varlık değerini
        matematiksel olarak kusursuz hesaplar.
        """
        conn = sqlite3.connect(DB_FILE)
        df_port = pd.read_sql("SELECT * FROM paper_portfolio ORDER BY id DESC LIMIT 1", conn)
        df_pos = pd.read_sql("SELECT * FROM paper_positions", conn)
        conn.close()

        cash = df_port.iloc[0]['cash'] if not df_port.empty else 100000.0
        
        open_positions_value = 0.0
        detailed_positions = []

        if not df_pos.empty:
            for _, row in df_pos.iterrows():
                sym = row['symbol']
                shares = row['shares']
                entry_price = row['entry_price']
                current_p = current_prices.get(sym, entry_price) if current_prices else entry_price
                
                market_val = shares * current_p
                open_positions_value += market_val
                
                pnl_tl = market_val - (shares * entry_price)
                pnl_pct = ((current_p - entry_price) / entry_price) * 100.0
                
                detailed_positions.append({
                    'symbol': sym,
                    'shares': shares,
                    'entry_price': entry_price,
                    'current_price': current_p,
                    'market_value': market_val,
                    'pnl_tl': pnl_tl,
                    'pnl_pct': pnl_pct,
                    'stop_loss': row['stop_loss'],
                    'tp1': row['tp1'],
                    'tp2': row['tp2']
                })

        total_nav = cash + open_positions_value
        initial_capital = 100000.0
        net_profit_tl = total_nav - initial_capital
        net_profit_pct = (net_profit_tl / initial_capital) * 100.0

        return {
            "cash": cash,
            "open_positions_value": open_positions_value,
            "total_nav": total_nav,
            "net_profit_tl": net_profit_tl,
            "net_profit_pct": net_profit_pct,
            "detailed_positions": detailed_positions
        }

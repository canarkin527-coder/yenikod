import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="BİST Değerleme ve Tarama Modeli", layout="wide")

st.title("📊 BİST Hisseleri Otomatik Değerleme ve Fiyat Tablosu")
st.write(
    "Bu program, BİST hisselerinin bilançolarını ve piyasa verilerini çekerek"
    " özel modellerinize göre analiz eder."
)

# Test edilebilecek popüler BİST hisseleri
bist_hisseleri = [
    "KCAER.IS",
    "EREGL.IS",
    "KARDM.IS",
    "SISE.IS",
    "THYAO.IS",
    "ASELS.IS",
]


def veri_cek(hisse_listesi):
  data_list = []
  for ticker in hisse_listesi:
    try:
      h = yf.Ticker(ticker)

      # Anlık Fiyat
      hist = h.history(period="1d")
      fiyat = (
          hist["Close"].iloc[-1]
          if not hist.empty
          else h.info.get("currentPrice", 0)
      )

      info = h.info
      piyasa_degeri = info.get("marketCap", 0)

      # Finansal Bilanço Kalemleri (Özsermaye ve Net Kâr çekme denemesi)
      # yfinance balanced sheet veya info üzerinden güvenli çekim
      ozsermaye = info.get("totalStockholderEquity", 0)
      net_kar = info.get("netIncomeToCommon", 0)

      # Eğer info'da yoksa balance_sheet'ten okumaya çalışalım
      if not ozsermaye or ozsermaye == 0:
        try:
          bs = h.balance_sheet
          if not bs.empty:
            ozsermaye = bs.loc["Stockholders Equity"].iloc[0]
        except:
          ozsermaye = 0

      if not net_kar or net_kar == 0:
        try:
          financials = h.financials
          if not financials.empty:
            net_kar = financials.loc["Net Income"].iloc[0]
        except:
          net_kar = 0

      data_list.append({
          "Hisse": ticker.replace(".IS", ""),
          "Fiyat (TL)": round(fiyat, 2) if fiyat else 0,
          "Piyasa Değeri (TL)": piyasa_degeri,
          "Öz Sermaye (TL)": ozsermaye if ozsermaye else 0,
          "Net Kâr (TL)": net_kar if net_kar else 0,
      })
    except Exception as e:
      data_list.append({
          "Hisse": ticker.replace(".IS", ""),
          "Fiyat (TL)": 0,
          "Piyasa Değeri (TL)": 0,
          "Öz Sermaye (TL)": 0,
          "Net Kâr (TL)": 0,
      })

  df = pd.DataFrame(data_list)

  # Özsermaye / Net Kâr ve konuştuğumuz Model Hesaplaması (Özsermaye / Net Kâr * 10)
  df["Öz Sermaye / Net Kâr"] = np.where(
      df["Net Kâr (TL)"] != 0,
      (df["Öz Sermaye (TL)"] / df["Net Kâr (TL)"]).round(2),
      np.nan,
  )

  df["Model Hedef Skoru"] = np.where(
      df["Net Kâr (TL)"] != 0,
      ((df["Öz Sermaye (TL)"] / df["Net Kâr (TL)"]) * 10).round(2),
      np.nan,
  )

  return df


if st.button("Verileri Güncelle ve Modeli Çalıştır"):
  with st.spinner("BİST verileri taranıyor ve modeller hesaplanıyor..."):
    df = veri_cek(bist_hisseleri)

    if not df.empty and df["Fiyat (TL)"].sum() > 0:
      st.success("Tarama Tamamlandı!")
      st.dataframe(df, use_container_width=True)

      # Excel olarak indirme butonu
      csv = df.to_csv(index=False).encode("utf-8")
      st.download_button(
          label="Tabloyu Excel Olarak İndir",
          data=csv,
          file_name="bist_degerleme_tablosu.csv",
          mime="text/csv",
      )
    else:
      st.warning(
          "Veriler anlık olarak çekilemedi. Yahoo Finance API bağlantısı geçici"
          " olarak kısıtlanmış olabilir. Lütfen birkaç dakika sonra tekrar"
          " deneyin."
      )

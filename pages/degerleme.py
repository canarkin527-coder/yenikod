import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="BİST Değerleme ve Tarama Modeli", layout="wide")

st.title("📊 BİST Hisseleri Otomatik Değerleme ve Fiyat Tablosu")
st.write(
    "Bu program, BİST hisselerinin verilerini çekerek belirlediğiniz model"
    " formüllerine göre analiz eder."
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
      # Hızlı veri almak için history veya fast_info kullanabiliriz
      hist = h.history(period="1d")
      fiyat = (
          hist["Close"].iloc[-1]
          if not hist.empty
          else h.info.get("currentPrice", 0)
      )
      info = h.info

      piyasa_degeri = info.get("marketCap", 0)
      ozsermaye = info.get("bookValue", 0)

      data_list.append({
          "Hisse": ticker.replace(".IS", ""),
          "Fiyat (TL)": round(fiyat, 2) if fiyat else 0,
          "Piyasa Değeri (TL)": piyasa_degeri,
          "Defter Değeri / Hisse": ozsermaye,
      })
    except Exception as e:
      # Hata olursa tabloda boş kalmasın diye en azından ismi ekleyelim
      data_list.append({
          "Hisse": ticker.replace(".IS", ""),
          "Fiyat (TL)": 0,
          "Piyasa Değeri (TL)": 0,
          "Defter Değeri / Hisse": 0,
      })
  return pd.DataFrame(data_list)


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

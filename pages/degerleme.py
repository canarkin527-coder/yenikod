import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="BİST Değerleme ve Tarama Modeli", layout="wide"
)

st.title("📊 BİST Hisseleri Otomatik Değerleme ve Fiyat Tablosu")
st.write(
    "Bu program, BİST hisselerinin verilerini çekerek belirlediğiniz model formüllerine göre analiz eder."
)

# Örnek bir BİST hisse listesi (Genişletilebilir)
bist_hisseleri = [
    "KCAER.IS",
    "EREGL.IS",
    "KARDM.IS",
    "SISE.IS",
    "TUPRS.IS",
    "THYAO.IS",
    "ASELS.IS",
]


@st.cache_data
def veri_cek(hisse_listesi):
  data_list = []
  for ticker in hisse_listesi:
    try:
      h = yf.Ticker(ticker)
      info = h.info
      fiyat = info.get("currentPrice", 0)
      piyasa_degeri = info.get("marketCap", 0)
      ozsermaye = info.get(
          "bookValue", 0
      )  # Veya bilanço bazlı özsermaye verisi

      data_list.append({
          "Hisse": ticker.replace(".IS", ""),
          "Fiyat (TL)": fiyat,
          "Piyasa Değeri (TL)": piyasa_degeri,
          "Defter Değeri / Özsermaye": ozsermaye,
      })
    except:
      pass
  return pd.DataFrame(data_list)


if st.button("Verileri Güncelle ve Modeli Çalıştır"):
  with st.spinner("BİST verileri taranıyor ve modeller hesaplanıyor..."):
    df = veri_cek(bist_hisseleri)

    # Sizin model formülünüzün tabloya uygulanması (Örnek mantık)
    # df['Model Skoru'] = (df['Özsermaye'] / df['Net Kar']) * 10

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


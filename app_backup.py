import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="🌾 NASA Farm Navigator", layout="centered")

st.title("🌾 किसान मौसम सलाह (Farmer Weather Advisory)")

# Input
lat = st.number_input("Latitude (अक्षांश)", value=23.18, format="%.5f")
lon = st.number_input("Longitude (देशांतर)", value=79.95, format="%.5f")
days = st.slider("Days to fetch (दिन)", 7, 30, 21)

if st.button("🔍 Get Advisory"):
    # NASA POWER API
    url = (
        f"https://power.larc.nasa.gov/api/temporal/daily/point"
        f"?parameters=T2M,RH2M,WS2M,PRECTOTCORR"
        f"&community=AG"
        f"&longitude={lon}&latitude={lat}"
        f"&start=20250101&end=20250121&format=JSON"
    )

    res = requests.get(url).json()

    if "properties" in res:
        data = res["properties"]["parameter"]
        df = pd.DataFrame(data)
        st.subheader("📊 Weather Data")
        st.dataframe(df.head())

        # Advisory rules
        try:
            avg_temp = sum(data["T2M"].values()) / len(data["T2M"])
            avg_rain = sum(data["PRECTOTCORR"].values()) / len(data["PRECTOTCORR"])
        except Exception:
            avg_temp, avg_rain = None, None

        if avg_rain and avg_rain > 5:
            advice = "✅ हाल की वर्षा पर्याप्त है — पानी पसंद करने वाली फसलें बोई जा सकती हैं।"
        else:
            advice = "⚠️ वर्षा कम है — अभी सूखा सहने वाली फसल बोएं।"

        st.subheader("🌱 Advisory (सलाह)")
        st.success(advice)

        # SMS & IVR preview
        st.subheader("📩 SMS Preview")
        st.text(f"Farm @ ({lat},{lon}) | Temp: {avg_temp:.1f}°C | Rain: {avg_rain:.1f}mm | Advice: {advice}")

        st.subheader("📞 IVR (Hindi)")
        st.audio("https://translate.google.com/translate_tts?ie=UTF-8&q=" + advice + "&tl=hi&client=tw-ob")

    else:
        st.error("⚠️ Could not fetch NASA POWER data.")

# farm_ui_merged.py
import streamlit as st
import requests
import pandas as pd
import json
from datetime import date, timedelta
import numpy as np
from gtts import gTTS
import tempfile, os

st.set_page_config(page_title="🌾 किसान मौसम सलाह — Farm Navigator", layout="wide")
st.title("🌾 किसान मौसम सलाह — Farm Navigator (Hindi / English)")

# ========== Sidebar inputs ==========
st.sidebar.header("इनपुट / Inputs")
lat = st.sidebar.number_input("Latitude (अक्षांश)", value=23.18, format="%.5f")
lon = st.sidebar.number_input("Longitude (देशांतर)", value=79.95, format="%.5f")
days = st.sidebar.slider("Days to fetch (दिन)", min_value=3, max_value=30, value=10)
community_choice = st.sidebar.selectbox("POWER Community", ["AG", "RE"])
try_both = st.sidebar.checkbox("Try both communities (AG then RE)", value=False)
soil = st.sidebar.selectbox("Soil type (मिट्टी)", ["Loamy", "Sandy", "Clay"])
lang = st.sidebar.selectbox("Language / भाषा", ["English", "Hindi"])
fetch_button = st.sidebar.button("🔍 Fetch & Advise")

# ---------- Helper functions ----------
def call_power_api(lat, lon, start, end, parameter_list, community="AG"):
    url = (
        "https://power.larc.nasa.gov/api/temporal/daily/point"
        f"?parameters={parameter_list}&community={community}&longitude={lon}&latitude={lat}"
        f"&start={start}&end={end}&format=JSON"
    )
    return requests.get(url, timeout=25)

def build_df_from_power(j):
    params = j.get("properties", {}).get("parameter", {})
    df = pd.DataFrame()
    for k, v in params.items():
        if isinstance(v, dict):
            s = pd.Series(v, name=k)
            s.index = pd.to_datetime(s.index, format="%Y%m%d")
            df = pd.concat([df, s], axis=1)
    df = df.sort_index()
    return df

def sanitize_df(df):
    if df is None or df.empty:
        return df
    df_s = df.copy()
    df_s = df_s.apply(pd.to_numeric, errors="coerce")
    df_s = df_s.mask(df_s <= -900, other=np.nan)
    return df_s

def crop_calendar(month):
    if month in [6,7,8,9,10]:
        return "Kharif (Rice, Maize, Millets, Cotton, Soybean, Groundnut)"
    if month in [11,12,1,2,3]:
        return "Rabi (Wheat, Barley, Mustard, Gram, Peas)"
    if month in [4,5]:
        return "Zaid (Watermelon, Muskmelon, Vegetables, Fodder)"
    return "Season info not available"

def crop_recommendation(avg_rain, avg_temp):
    if avg_rain is None or avg_temp is None:
        return "⚠️ Insufficient data for crop recommendation."
    if avg_rain > 20 and avg_temp > 24:
        return "🌾 Rice recommended — rainfall & temperature favorable."
    if 5 <= avg_rain <= 20 and 15 <= avg_temp <= 22:
        return "🌾 Wheat suitable — moderate rain and cooler temps."
    if avg_rain < 5 and 18 <= avg_temp <= 28:
        return "🌱 Pulses (lentils/gram) ideal for dry conditions."
    return "🌿 Consider climate-resilient crops: millets/maize."

def soil_tailored_note(soil_type):
    if soil_type == "Sandy":
        return "Sandy soil: quick drainage — irrigate more frequently."
    if soil_type == "Clay":
        return "Clay soil: water retention high — avoid waterlogging."
    return "Loamy soil: generally ideal for many crops."

def text_to_speech_and_play(text, lang_code="hi"):
    # create temp mp3 and return path for st.audio
    try:
        tts = gTTS(text=text, lang=lang_code)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tmp_name = tmp.name
        tmp.close()
        tts.save(tmp_name)
        return tmp_name
    except Exception as e:
        st.warning(f"TTS failed: {e}")
        return None

# ========== Fetch + process per community ==========
def fetch_for_community(lat, lon, days, community):
    start = (date.today() - timedelta(days=days-1)).strftime("%Y%m%d")
    end = date.today().strftime("%Y%m%d")
    param_attempts = [
        "PRECTOT,PRECTOTCORR,T2M,RH2M,WS2M,ALLSKY_SFC_SW_DWN",
        "PRECTOTCORR,T2M,RH2M,WS2M",
        "PRECTOTCORR,T2M",
        "T2M"
    ]
    last_status = None
    last_text = None
    successful_json = None
    used_params = None
    for plist in param_attempts:
        try:
            r = call_power_api(lat, lon, start, end, plist, community=community)
            last_status = r.status_code
            last_text = r.text[:1500]
            if r.ok:
                successful_json = r.json()
                used_params = plist
                break
        except Exception as e:
            last_text = str(e)
    if not successful_json:
        return {"success": False, "status": last_status, "text": last_text}
    # save raw
    fname = f"api_raw_{community}.json"
    with open(fname, "w", encoding="utf8") as f:
        json.dump(successful_json, f, indent=2, ensure_ascii=False)
    df = build_df_from_power(successful_json)
    df = sanitize_df(df)
    return {"success": True, "df": df, "rawfile": fname, "used": used_params}

# ========== UI actions ==========
if fetch_button:
    communities = ["AG","RE"] if try_both else [community_choice]
    all_results = {}
    for comm in communities:
        st.header(f"Community: {comm}")
        with st.spinner(f"Fetching {comm} ..."):
            res = fetch_for_community(lat, lon, days, comm)
        if not res["success"]:
            st.error(f"Failed for {comm} — status: {res.get('status')}")
            st.text(res.get("text") or "No response text.")
            continue

        df = res["df"]
        st.success(f"Data fetched — saved: `{res['rawfile']}` (params used: {res.get('used')})")
        if df.empty:
            st.warning("No numeric time series after sanitize.")
            continue

        # show keys, quality, sample
        st.subheader("Available Keys & Data Quality")
        st.write(list(df.columns))
        valid_counts = df.count()
        st.write(valid_counts.to_frame("valid_count"))
        st.subheader("Sample (tail)")
        st.dataframe(df.tail(8))

        # metrics & choose precipitation key
        precip_candidates = ["PRECTOT", "PRECTOTCORR", "PRCP", "RAIN", "APCP"]
        precip_key = next((k for k in precip_candidates if k in df.columns), None)

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else None

        c1, c2, c3, c4 = st.columns([1.3,1.3,1,1])
        # temp metric
        if "T2M" in df.columns and valid_counts.get("T2M",0)>0:
            t_now = latest["T2M"]
            t_prev = prev["T2M"] if prev is not None else None
            delta = (t_now - t_prev) if (t_prev is not None and pd.notna(t_now) and pd.notna(t_prev)) else None
            c1.metric("🌡️ Temp (°C) — latest", f"{t_now:.2f}" if pd.notna(t_now) else "N/A",
                      delta=(f"{delta:+.2f}" if delta is not None else ""))
        else:
            c1.metric("🌡️ Temp (°C) — latest", "N/A")

        # precip metric
        if precip_key and valid_counts.get(precip_key,0)>0:
            r_now = latest[precip_key]
            r_prev = prev[precip_key] if prev is not None else None
            delta_r = (r_now - r_prev) if (r_prev is not None and pd.notna(r_now) and pd.notna(r_prev)) else None
            c2.metric(f"☔ Precip ({precip_key}) — latest", f"{r_now:.2f}" if pd.notna(r_now) else "N/A",
                      delta=(f"{delta_r:+.2f}" if delta_r is not None else ""))
        else:
            c2.metric("☔ Precip — latest", "N/A")

        numeric_means = df.mean(numeric_only=True)
        c3.metric("📈 Avg (period) — mean of numeric means", round(numeric_means.mean(),2) if not numeric_means.empty else "N/A")
        c4.metric("Records", f"{len(df)} days")

        # plot precipitation or temp
        if precip_key and valid_counts.get(precip_key,0)>0:
            st.markdown(f"### Precipitation — `{precip_key}`")
            st.bar_chart(df[precip_key])
            st.metric("Avg precipitation (period)", round(df[precip_key].mean(),2))
        elif "T2M" in df.columns and valid_counts.get("T2M",0)>0:
            st.markdown("### Temperature (T2M)")
            st.line_chart(df["T2M"])
            st.metric("Avg temp (period)", round(df["T2M"].mean(),2))
        else:
            st.warning("No valid param to plot.")

        # Advisory: season + crop + soil tailored
        month = date.today().month
        season_msg = crop_calendar(month)
        avg_rain = df[precip_key].mean() if (precip_key and precip_key in df.columns and df[precip_key].count()>0) else None
        avg_temp = df["T2M"].mean() if ("T2M" in df.columns and df["T2M"].count()>0) else None
        crop_msg = crop_recommendation(avg_rain, avg_temp)
        soil_msg = soil_tailored_note(soil)

        st.subheader("🌱 Advisory (Season + Weather + Soil)")
        # localized strings if Hindi wanted
        if lang == "Hindi":
            adv_text = f"मौसम सत्र: {season_msg}\n\nऔसत वर्षा: {round(avg_rain,2) if avg_rain is not None else 'N/A'} mm\nऔसत ताप: {round(avg_temp,2) if avg_temp is not None else 'N/A'} °C\n\nसिफारिश: {crop_msg}\n\nमिट्टी: {soil_msg}"
        else:
            adv_text = f"Season: {season_msg}\n\nAvg Rain: {round(avg_rain,2) if avg_rain is not None else 'N/A'} mm\nAvg Temp: {round(avg_temp,2) if avg_temp is not None else 'N/A'} °C\n\nRecommendation: {crop_msg}\n\nSoil note: {soil_msg}"

        st.text_area("Advisory", value=adv_text, height=160)

        # SMS & IVR templates
        sms = f"Farm @ ({lat:.2f},{lon:.2f}) | Temp: {round(avg_temp,1) if avg_temp is not None else 'N/A'}°C | Rain: {round(avg_rain,1) if avg_rain is not None else 'N/A'}mm | Advice: {crop_msg}"
        st.subheader("📩 SMS (copy ready)")
        st.text_area("SMS", value=sms, height=80)

        st.subheader("📞 IVR (play preview)")
        # use gTTS to make audio (hi if Hindi else en)
        tts_lang = "hi" if lang=="Hindi" else "en"
        # short IVR phrase (localized)
        ivr_phrase = (f"नमस्ते। आपके खेत के लिए सिफारिश: {crop_msg}. {soil_msg}" if lang=="Hindi"
                      else f"Hello. Recommendation for your farm: {crop_msg}. {soil_msg}")
        audio_path = text_to_speech_and_play(ivr_phrase, lang_code=tts_lang)
        if audio_path:
            st.audio(audio_path)
            # cleanup after playing — delayed removal is okay; we remove now
            try:
                os.remove(audio_path)
            except Exception:
                pass
        else:
            st.write("Audio preview not available.")

        # CSV download
        out_df = df.reset_index().rename(columns={"index":"date"})
        csv = out_df.to_csv(index=False)
        st.download_button("📥 Download CSV", csv, file_name=f"nasa_power_{comm}.csv", mime="text/csv")

        all_results[comm] = {"df": df, "avg_rain": avg_rain, "avg_temp": avg_temp}

    # done communities loop

    # final compare box if both requested
    if try_both and len(all_results) > 0:
        st.markdown("---")
        st.header("Comparison (AG vs RE)")
        for comm, info in all_results.items():
            st.write(f"**{comm}** — Avg Rain: {round(info['avg_rain'],2) if info['avg_rain'] is not None else 'N/A'} mm | Avg Temp: {round(info['avg_temp'],2) if info['avg_temp'] is not None else 'N/A'} °C")

else:
    st.info("Set inputs in the sidebar and click 'Fetch & Advise'.")

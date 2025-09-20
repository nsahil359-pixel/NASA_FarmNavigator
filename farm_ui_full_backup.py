# farm_ui_full.py (robust NASA POWER debug + map + advisory)
import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
from gtts import gTTS
import json, os, tempfile

st.set_page_config(page_title="🌾 Farmer Navigator — Debuggable Full", layout="wide")
st.title("🌾 Farmer Navigator — Place + Weather + Advisory (robust)")

# Sidebar inputs
st.sidebar.header("Inputs / इनपुट")
place_name = st.sidebar.text_input("Enter Place Name (स्थान)", "Jabalpur, India")
soil_type = st.sidebar.selectbox("Soil type (मिट्टी)", ["Loamy", "Sandy", "Clay", "Silty"])
language = st.sidebar.selectbox("Language / भाषा", ["English", "Hindi"])
days = st.sidebar.slider("Days to fetch (दिन)", 5, 20, 10)
community_choice = st.sidebar.selectbox("POWER Community", ["AG", "RE"])
fetch_button = st.sidebar.button("✅ Fetch & Advise")

# helper: try multiple parameter sets (avoids 422)
PARAM_OPTIONS = [
    "PRECTOT,PRECTOTCORR,T2M,RH2M,WS2M,ALLSKY_SFC_SW_DWN",
    "PRECTOTCORR,T2M,RH2M,WS2M",
    "PRECTOTCORR,T2M",
    "T2M"
]

def call_power_attempts(lat, lon, start, end, community="AG"):
    last_resp = None
    for plist in PARAM_OPTIONS:
        url = (
            "https://power.larc.nasa.gov/api/temporal/daily/point"
            f"?parameters={plist}&community={community}&longitude={lon}&latitude={lat}"
            f"&start={start}&end={end}&format=JSON"
        )
        try:
            r = requests.get(url, timeout=30)
        except Exception as e:
            last_resp = {"ok": False, "error": str(e), "url": url}
            continue

        # Save last response for debug
        last_resp = {"ok": r.ok, "status": r.status_code, "text": r.text[:2000], "url": url, "params": plist}
        if r.ok:
            try:
                j = r.json()
            except Exception as e_json:
                last_resp["ok"] = False
                last_resp["error"] = f"JSON decode error: {e_json}"
                continue

            # check for properties key
            if "properties" in j and "parameter" in j["properties"]:
                return {"success": True, "json": j, "used_params": plist}
            else:
                # sometimes API returns a different structure or message
                last_resp["ok"] = False
                last_resp["text"] = r.text[:2000]
                # try next param list
                continue
        else:
            # try next param list
            continue

    return {"success": False, "debug": last_resp}

def build_df_from_power(j):
    params = j.get("properties", {}).get("parameter", {})
    df = pd.DataFrame()
    for k, v in params.items():
        if isinstance(v, dict):
            s = pd.Series(v, name=k)
            s.index = pd.to_datetime(list(v.keys()), format="%Y%m%d")
            df = pd.concat([df, s], axis=1)
    return df.sort_index()

def sanitize_df(df):
    if df is None or df.empty:
        return df
    df = df.apply(pd.to_numeric, errors="coerce")
    df = df.mask(df <= -900, other=pd.NA)
    return df

# geocode
geolocator = Nominatim(user_agent="farm_app_example")

if place_name:
    try:
        location = geolocator.geocode(place_name, timeout=15)
    except Exception as e:
        st.error(f"Geocoding error: {e}")
        location = None
else:
    location = None

if location:
    lat, lon = location.latitude, location.longitude
    st.success(f"📍 Location: {place_name} → lat {lat:.5f}, lon {lon:.5f}")

    # map
    m = folium.Map(location=[lat, lon], zoom_start=9)
    folium.Marker([lat, lon], tooltip=place_name).add_to(m)
    st_map = st_folium(m, width=700, height=350)

    if fetch_button:
        # build date range
        end_dt = datetime.today()
        start_dt = end_dt - timedelta(days=days-1)
        start_str = start_dt.strftime("%Y%m%d")
        end_str = end_dt.strftime("%Y%m%d")

        st.info(f"Fetching NASA POWER for {start_str} → {end_str} (community={community_choice}) ...")

        result = call_power_attempts(lat, lon, start_str, end_str, community=community_choice)
        if not result["success"]:
            # show helpful debug output
            dbg = result.get("debug", {})
            st.error("❌ NASA POWER fetch failed with all parameter attempts.")
            st.write("Last attempt (debug):")
            st.json({
                "url": dbg.get("url"),
                "status": dbg.get("status"),
                "params_tried": dbg.get("params"),
                "snippet_or_error": dbg.get("text") or dbg.get("error")
            })
            st.warning("Try changing 'Days to fetch' to a smaller value, switch community (AG/RE), or try a different nearby place.")
        else:
            j = result["json"]
            used = result["used_params"]
            # save raw
            rawfname = f"api_raw_debug_{community_choice}.json"
            with open(rawfname, "w", encoding="utf8") as f:
                json.dump(j, f, indent=2, ensure_ascii=False)
            st.success(f"✅ NASA POWER returned data (params used: {used}). Raw saved: {rawfname}")

            # build df
            df = build_df_from_power(j)
            df = sanitize_df(df)
            if df.empty:
                st.error("❌ After building dataframe, no numeric data present.")
                st.write("Saved raw JSON (open file) may help diagnose.")
            else:
                st.subheader("📊 Time series sample (tail)")
                st.dataframe(df.tail(10))

                # pick precipitation key if available
                precip_candidates = ["PRECTOT","PRECTOTCORR","PRCP","RAIN","APCP"]
                precip_key = next((k for k in precip_candidates if k in df.columns), None)

                # charts: temp and precipitation if present
                if "T2M" in df.columns:
                    st.markdown("### 🌡️ Temperature (T2M)")
                    st.line_chart(df["T2M"])
                    avg_temp = df["T2M"].mean()
                else:
                    avg_temp = None
                    st.warning("T2M not available")

                if precip_key:
                    st.markdown(f"### ☔ Precipitation ({precip_key})")
                    st.bar_chart(df[precip_key])
                    avg_rain = df[precip_key].mean()
                else:
                    avg_rain = None
                    st.warning("No precipitation parameter available from response")

                # Advisory (simple)
                st.subheader("🌱 Advisory")
                month = datetime.today().month
                season = "Kharif" if month in [6,7,8,9,10] else "Rabi" if month in [11,12,1,2,3] else "Zaid"
                if avg_rain is None:
                    base = "⚠️ No rainfall data — use local guidance"
                elif avg_rain < 5:
                    base = "⚠️ Rainfall low — consider irrigation"
                elif avg_rain < 20:
                    base = "🌱 Moderate rainfall — good for sowing"
                else:
                    base = "✅ Adequate rainfall — good for water-loving crops"

                crop_msg = ("🌾 Rice" if (avg_rain and avg_rain>20 and avg_temp and avg_temp>24) else
                            "🌾 Wheat" if (avg_rain and 5<=avg_rain<=20 and avg_temp and 15<=avg_temp<=22) else
                            "🌱 Pulses" if (avg_rain and avg_rain<5 and avg_temp and 18<=avg_temp<=28) else
                            "🌿 Millets/Maize (general)")

                soil_msg = ("Sandy soil: quick drainage — irrigate more frequently." if soil_type=="Sandy"
                            else "Clay soil: high retention — avoid waterlogging." if soil_type=="Clay"
                            else "Loamy soil: generally ideal.")

                adv_text = f"Season: {season}\n{base}\nCrop suggestion: {crop_msg}\nSoil note: {soil_msg}"
                st.text_area("Advisory", value=adv_text, height=140)

                # SMS
                sms = f"Farm @ ({lat:.2f},{lon:.2f}) | Temp: {round(avg_temp,1) if avg_temp is not None else 'N/A'}°C | Rain: {round(avg_rain,1) if avg_rain is not None else 'N/A'} mm | Advice: {base}"
                st.subheader("📩 SMS (copy-ready)")
                st.code(sms)

                # IVR audio
                st.subheader("📞 IVR preview")
                ivr_phrase = adv_text
                try:
                    tts = gTTS(ivr_phrase, lang="hi" if language=="Hindi" else "en")
                    tmpf = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                    tmpf.close()
                    tts.save(tmpf.name)
                    audio_bytes = open(tmpf.name, "rb").read()
                    st.audio(audio_bytes, format="audio/mp3")
                    os.remove(tmpf.name)
                except Exception as e:
                    st.warning(f"TTS failed: {e}")

else:
    st.info("Enter a place name in the sidebar and click locate/fetch.")

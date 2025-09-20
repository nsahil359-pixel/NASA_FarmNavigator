import streamlit as st
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import st_folium

# App Title
st.title("🌾 Farmer Navigator — Place Search + Satellite Map")

# Input for place name
place = st.text_input("🔍 Enter Place Name:", "Jabalpur, India")

if place:
    try:
        geolocator = Nominatim(user_agent="farm_navigator")
        location = geolocator.geocode(place)

        if location:
            lat, lon = location.latitude, location.longitude
            st.success(f"📍 Location found: {place}")
            st.write(f"Latitude: `{lat:.5f}`, Longitude: `{lon:.5f}`")

            # Create Folium Map
            m = folium.Map(location=[lat, lon], zoom_start=10)

            # Add marker
            folium.Marker([lat, lon], tooltip=place, popup=f"{place}\n({lat:.2f}, {lon:.2f})").add_to(m)

            # Show map in Streamlit
            st_folium(m, width=700, height=500)

        else:
            st.error("❌ Could not find location. Try another place.")

    except Exception as e:
        st.error(f"⚠️ Error: {e}")

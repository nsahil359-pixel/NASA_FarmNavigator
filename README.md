# NASA_FarmNavigator
Prototype app for NASA Space Apps — Farm Navigator.  Public (recommended for hackathon).

🌾 NASA Farm Navigator

Hi there! 👋
This is our project for the NASA Space Apps Challenge 2025.

We built Farm Navigator to make NASA’s powerful climate and satellite data useful for farmers on the ground. Instead of raw numbers and complicated datasets, the app gives simple, local, and practical advice — the kind of info a farmer can actually use to decide “Should I sow today? Which crop is better for this season? Do I need to irrigate now?”

🌍 Why we built this

Farmers everywhere depend on the weather — but they often get generic forecasts that don’t really match the conditions of their fields.
We asked ourselves:
👉 What if NASA’s Earth observations could be translated into farmer-friendly insights?
👉 What if a farmer could just type their village name and instantly see rainfall, temperature, and even crop advice?

That’s what this app tries to do.

🌱 What the app does

Search by place – Just type your village/town name (no lat/long needed).

Interactive map – Switch between Esri satellite view and NASA GIBS imagery.

Daily climate data – Pulled directly from NASA POWER API (rainfall, temperature, humidity, wind).

Simple advisory – Crop suggestions based on season, soil type, and rainfall trends.

Farmer-friendly formats – The advice is shown as text, ready-to-send SMS, and even as IVR audio (so farmers with feature phones can still get it).

🚀 Try it out

👉 Live App: NASA Farm Navigator

🛠 Tech behind the scenes

NASA POWER – for climate data

NASA GIBS (VIIRS/MODIS) – for real satellite imagery

Streamlit – for the web app

Folium/Leaflet – for interactive maps

gTTS – to generate audio (IVR preview)

Python – holding it all together

💻 Run it locally

If you want to explore the code yourself:
git clone https://github.com/nsahil359-pixel/NASA_FarmNavigator.git
cd NASA_FarmNavigator
pip install -r requirements.txt
streamlit run farm_ui_full.py


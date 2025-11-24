import streamlit as st
import pandas as pd
from sklearn.linear_model import LinearRegression
import requests
import numpy as np
import time

# ==================== CONFIG & STYLE ====================
st.set_page_config(page_title="Trajets Verts Paris", page_icon="Bicycle")
st.markdown("""
<style>
    .stApp {background: none !important;}
    .stButton > button {background-color: #1b5b00 !important; color: white !important; border: none !important; border-radius: 16px !important; height: 3.8em !important; font-size: 1.3em !important; font-weight: bold !important;}
    .stButton > button:hover {background-color: #256b00 !important;}
    .stTextInput > div > div > input {border: 2px solid #1b5b00 !important; border-radius: 8px;}
    .success-box {background-color: #1b5b00; color: white; padding: 1.6rem; border-radius: 16px; text-align: center; font-size: 1.7em; font-weight: bold;}
    .warning-box {background-color: #e65100; color: white; padding: 1.6rem; border-radius: 16px; text-align: center; font-size: 1.7em; font-weight: bold;}
    .danger-box {background-color: #c62828; color: white; padding: 1.6rem; border-radius: 16px; text-align: center; font-size: 1.7em; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<h1 style="text-align: center; color: #ffffff; font-size: 3.2em; margin-bottom: 0;">
    Trajets Verts Paris 🚴‍♂️🌳🚲🌳🚴‍♂️🌳🚲
</h1>
""", unsafe_allow_html=True)

# ==================== SECRETS ====================
token_aqi = st.secrets["token_aqi"]
google_key = st.secrets["google_key"]

# ==================== AQI LIVE ====================
try:
    resp = requests.get(f'https://api.waqi.info/feed/paris/?token={token_aqi}', timeout=10)
    data = resp.json()['data']
    live_aqi = int(data.get('aqi', 0))
    live_pm25 = data.get('iaqi', {}).get('pm25', {}).get('v', 10)
    live_no2 = data.get('iaqi', {}).get('no2', {}).get('v', 30)
except:
    live_aqi, live_pm25, live_no2 = 50, 15, 35

# ==================== MODÈLE AIRPARIF ====================
@st.cache_resource
def load_model():
    df = pd.read_csv('paris_air.csv', delimiter=';')
    df['aqi_score'] = (df['NO2 Fond-urbain Moyenne annuelle - Airparif'] * 0.5 +
                       df['PM2-5 Fond urbain Moyenne annuelle - Airparif'] * 0.5) / 100
    X = df[['NO2 Fond-urbain Moyenne annuelle - Airparif', 'PM2-5 Fond urbain Moyenne annuelle - Airparif']]
    y = df['aqi_score']
    return LinearRegression().fit(X, y)
model = load_model()

# ==================== AUTOCOMPLÉTION + GÉOCODAGE GOOGLE (version ultra-fiable) ====================
def autocomplete_and_geocode(query):
    if not query.strip():
        return None, None
    
    # 1. Autocomplétion
    url_auto = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params_auto = {
        "input": query + " Paris",
        "key": google_key,
        "language": "fr",
        "components": "country:fr"
    }
    try:
        resp = requests.get(url_auto, params=params_auto, timeout=10)
        predictions = resp.json().get("predictions", [])
        if predictions:
            place_id = predictions[0]["place_id"]
            description = predictions[0]["description"]
        else:
            place_id = None
            description = query
    except:
        place_id = None
        description = query

    # 2. Géocodage précis
    if place_id:
        url_details = "https://maps.googleapis.com/maps/api/place/details/json"
        params_details = {"place_id": place_id, "key": google_key, "fields": "geometry,formatted_address"}
        try:
            resp = requests.get(url_details, params=params_details, timeout=10)
            data = resp.json()
            if data["status"] == "OK":
                loc = data["result"]["geometry"]["location"]
                addr = data["result"]["formatted_address"]
                return (loc["lat"], loc["lng"]), addr
        except:
            pass

    # Fallback : géocodage direct si autocomplétion échoue
    url_geo = "https://maps.googleapis.com/maps/api/geocode/json"
    params_geo = {"address": query + ", Paris, France", "key": google_key}
    try:
        resp = requests.get(url_geo, params=params_geo, timeout=10)
        results = resp.json().get("results", [])
        if results:
            loc = results[0]["geometry"]["location"]
            addr = results[0]["formatted_address"]
            return (loc["lat"], loc["lng"]), addr
    except:
        pass

    return None, None

# ==================== UI ====================
col1, col2 = st.columns(2)
with col1:
    depart_input = st.text_input("Départ (tape 3 lettres → suggestions)", placeholder="ex: Bastille, Gare du Nord...")
with col2:
    arrivee_input = st.text_input("Arrivée (tape 3 lettres → suggestions)", placeholder="ex: Tour Eiffel, République...")

mode = st.radio("Mode de déplacement", ["Marche", "Vélo"], horizontal=True)
google_mode = "walking" if mode == "Marche" else "bicycling"

if st.button("Prédire Route Verte", type="primary", use_container_width=True):
    if not depart_input.strip() or not arrivee_input.strip():
        st.error("Remplis les deux champs !")
    else:
        with st.spinner("Recherche en cours…"):
            coords1, addr1 = autocomplete_and_geocode(depart_input)
            coords2, addr2 = autocomplete_and_geocode(arrivee_input)

            if not coords1 or not coords2:
                st.error("Un des lieux n’a pas été trouvé. Essaie avec plus de lettres ou une adresse exacte.")
            else:
                lat1, lng1 = coords1
                lat2, lng2 = coords2

                # Distance Matrix
                url = f"https://maps.googleapis.com/maps/api/distancematrix/json"
                params = {
                    "origins": f"{lat1},{lng1}",
                    "destinations": f"{lat2},{lng2}",
                    "mode": google_mode,
                    "key": google_key
                }
                try:
                    resp = requests.get(url, params=params, timeout=20)
                    data = resp.json()
                    if data["rows"][0]["elements"][0]["status"] == "OK":
                        dist_m = data["rows"][0]["elements"][0]["distance"]["value"]
                        dur_sec = data["rows"][0]["elements"][0]["duration"]["value"]
                        distance_km = round(dist_m / 1000, 2)
                        duration_min = round(dur_sec / 60, 1)

                        pred = model.predict(np.array([[live_no2, live_pm25]]))[0]
                        green_score = round((distance_km / 10) * (1 - pred), 3)

                        st.markdown(f"<div class='success-box'>Trouvé ! {addr1.split(',')[0]} → {addr2.split(',')[0]}</div>", unsafe_allow_html=True)

                        # AQI Paris
                        if live_aqi <= 50:
                            st.markdown(f"<div class='success-box'>Leaf AQI Paris : <strong>{live_aqi}</strong> → Air très bon</div>", unsafe_allow_html=True)
                        elif live_aqi <= 100:
                            st.markdown(f"<div class='warning-box'>Face neutral AQI Paris : <strong>{live_aqi}</strong> → Air modéré</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div class='danger-box'>Pollution AQI Paris : <strong>{live_aqi}</strong> → Air mauvais</div>", unsafe_allow_html=True)

                        # Green Score
                        if green_score < 0.4:
                            st.markdown(f"<div class='success-box'>Leaf Green Score : <strong>{green_score}</strong> → Air excellent – fonce !</div>", unsafe_allow_html=True)
                        elif green_score <= 0.7:
                            st.markdown(f"<div class='warning-box'>Face neutral Green Score : <strong>{green_score}</strong> → Air moyen – surveille</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div class='danger-box'>Pollution Green Score : <strong>{green_score}</strong> → Air pollué – évite !</div>", unsafe_allow_html=True)

                        col1, col2 = st.columns(2)
                        col1.metric("Distance", f"{distance_km} km")
                        col2.metric("Temps estimé", f"{duration_min} min")

                        st.bar_chart({"AQI": [live_aqi], "Green Score ×100": [green_score*100]}, height=320)
                    else:
                        st.error("Pas de trajet trouvé entre ces deux points.")
                except:
                    st.error("Erreur réseau Google. Vérifie ta clé.")

# ==================== FOOTER ====================
st.divider()
st.markdown("""
<div style='text-align:center; color:#ffffff; font-size:1.1em; padding:20px;'>
    © 2025 <strong>Trajets Verts Paris</strong> – Créé par <strong>Raymond Gadji</strong><br>
    Données : waqi.info • Google Maps • Airparif
</div>
""", unsafe_allow_html=True)
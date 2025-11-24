import streamlit as st
import pandas as pd
from sklearn.linear_model import LinearRegression
import requests
from geopy.geocoders import Nominatim
import numpy as np
import time
from difflib import get_close_matches

# ==================== CONFIG & STYLE ====================
st.set_page_config(page_title="Trajets Verts Paris", page_icon="Bicycle")
st.markdown("""
<style>
    .stApp {background: none !important;}
    .stButton > button {background-color: #1b5b00 !important; color: white !important; border: none !important; border-radius: 16px !important; height: 3.8em !important; font-size: 1.3em !important; font-weight: bold !important;}
    .stButton > button:hover {background-color: #256b00 !important;}
    div[role="radiogroup"] > label > div:first-child {background-color: #e0e0e0 !important;}
    div[role="radiogroup"] > label[data-checked="true"] > div:first-child {background-color: #1b5b00 !important;}
    div[role="radiogroup"] label {color: #1b5b00 !important; font-weight: bold;}
    .stTextInput > div > div > input {border: 2px solid #1b5b00 !important; border-radius: 8px;}
    .success-box {background-color: #1b5b00; color: white; padding: 1.6rem; border-radius: 16px; text-align: center; font-size: 1.6em; font-weight: bold;}
    .warning-box {background-color: #e65100; color: white; padding: 1.6rem; border-radius: 16px; text-align: center; font-size: 1.6em; font-weight: bold;}
    .danger-box {background-color: #c62828; color: white; padding: 1.6rem; border-radius: 16px; text-align: center; font-size: 1.6em; font-weight: bold;}
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

# ==================== AUTOCOMPLÉTION GOOGLE PLACES ====================
def get_place_suggestions(input_text):
    if not input_text or len(input_text) < 3:
        return []
    url = f"https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = {
        "input": input_text + " Paris",
        "key": google_key,
        "types": "geocode",
        "components": "country:fr"
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        predictions = resp.json().get("predictions", [])
        return [p["description"] for p in predictions[:5]]
    except:
        return []

# ==================== GÉOCODAGE À PARTIR D'ADRESSE COMPLÈTE ====================
def geocode_address(address):
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": google_key}
    try:
        resp = requests.get(url, params=params, timeout=10)
        results = resp.json().get("results", [])
        if results:
            loc = results[0]["geometry"]["location"]
            return loc["lat"], loc["lng"], results[0]["formatted_address"]
    except:
        pass
    return None

# ==================== UI ====================
col1, col2 = st.columns(2)
with col1:
    depart_input = st.text_input("Départ", "Daumesnil", help="Commence à taper → suggestions Google")
    if depart_input:
        suggestions_depart = get_place_suggestions(depart_input)
        if suggestions_depart:
            depart = st.selectbox("Suggestions Départ", [""] + suggestions_depart, key="dep_select")
            depart = depart or depart_input
        else:
            depart = depart_input
    else:
        depart = ""

with col2:
    arrivee_input = st.text_input("Arrivée", "Montmartre", help="Commence à taper → suggestions Google")
    if arrivee_input:
        suggestions_arrivee = get_place_suggestions(arrivee_input)
        if suggestions_arrivee:
            arrivee = st.selectbox("Suggestions Arrivée", [""] + suggestions_arrivee, key="arr_select")
            arrivee = arrivee or arrivee_input
        else:
            arrivee = arrivee_input
    else:
        arrivee = ""

mode = st.radio("Mode de déplacement", ["Marche", "Vélo"], horizontal=True)
google_mode = "walking" if mode == "Marche" else "bicycling"

if st.button("Prédire Route Verte", type="primary", use_container_width=True):
    if not depart or not arrivee:
        st.error("Remplis les deux champs !")
    else:
        with st.spinner("Calcul en cours…"):
            # Géocodage précis via Google
            coord1 = geocode_address(depart)
            coord2 = geocode_address(arrivee)

            if not coord1 or not coord2:
                st.error("Un des lieux n’a pas été trouvé. Essaie une adresse plus précise.")
            else:
                lat1, lng1, addr1 = coord1
                lat2, lng2, addr2 = coord2

                origins = f"{lat1},{lng1}"
                destinations = f"{lat2},{lng2}"
                url = f"https://maps.googleapis.com/maps/api/distancematrix/json?origins={origins}&destinations={destinations}&mode={google_mode}&key={google_key}"

                try:
                    resp = requests.get(url, timeout=20)
                    data = resp.json()

                    if data['rows'][0]['elements'][0]['status'] == 'OK':
                        distance_m = data['rows'][0]['elements'][0]['distance']['value']
                        distance_km = round(distance_m / 1000, 2)
                        duration_min = round(data['rows'][0]['elements'][0]['duration']['value'] / 60, 1)

                        pred = model.predict(np.array([[live_no2, live_pm25]]))[0]
                        green_score = round((distance_km / 10) * (1 - pred), 3)

                        st.markdown(f"<div class='success-box'>Trouvé ! {addr1.split(',')[0]} → {addr2.split(',')[0]}</div>", unsafe_allow_html=True)

                        # === AQI PARIS avec icône ===
                        if live_aqi <= 50:
                            aqi_class, aqi_icon, aqi_text = "success-box", "Leaf", "Air très bon"
                        elif live_aqi <= 100:
                            aqi_class, aqi_icon, aqi_text = "warning-box", "Face neutral", "Air modéré"
                        else:
                            aqi_class, aqi_icon, aqi_text = "danger-box", "Pollution", "Air mauvais"

                        st.markdown(f"""
                        <div class='{aqi_class}' style='margin: 20px 0; padding: 1.6rem; font-size: 1.7em;'>
                            {aqi_icon} AQI Paris : <strong>{live_aqi}</strong> → {aqi_text}
                        </div>
                        """, unsafe_allow_html=True)

                        # === GREEN SCORE avec icône ===
                        if green_score < 0.4:
                            gs_class, gs_icon, gs_text = "success-box", "Leaf", "Air excellent – fonce !"
                        elif green_score <= 0.7:
                            gs_class, gs_icon, gs_text = "warning-box", "Face neutral", "Air moyen – surveille"
                        else:
                            gs_class, gs_icon, gs_text = "danger-box", "Pollution", "Air pollué – évite !"

                        st.markdown(f"""
                        <div class='{gs_class}' style='margin: 20px 0; padding: 1.6rem; font-size: 1.7em;'>
                            {gs_icon} Green Score : <strong>{green_score}</strong> → {gs_text}
                        </div>
                        """, unsafe_allow_html=True)

                        # === Infos trajet ===
                        c1, c2 = st.columns(2)
                        c1.metric("Distance", f"{distance_km} km")
                        c2.metric("Temps estimé", f"{duration_min} min en {mode.lower()}")

                        st.bar_chart({"AQI": [live_aqi], "Green Score ×100": [green_score*100]}, height=320)
                    else:
                        st.error("Google n’a pas trouvé de trajet.")
                except:
                    st.error("Erreur réseau Google. Vérifie ta clé.")

# ==================== FOOTER ====================
st.divider()
st.markdown("""
<div style='text-align:center; color:#ffffff; font-size:1.1em; padding:20px;'>
    © 2025 <strong>Trajets Verts Paris</strong> – Créé par <strong>Raymond Gadji</strong><br>
    Données : waqi.info • Google Maps • OpenStreetMap • Airparif
</div>
""", unsafe_allow_html=True)
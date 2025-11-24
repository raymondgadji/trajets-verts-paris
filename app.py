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
    .success-box {background-color: #1b5b00; color: white; padding: 1.4rem; border-radius: 16px; text-align: center; font-size: 1.5em; font-weight: bold;}
    .warning-box {background-color: #e65100; color: white; padding: 1rem; border-radius: 12px; text-align: center;}
    .danger-box {background-color: #c62828; color: white; padding: 1rem; border-radius: 12px; text-align: center;}
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

# ==================== GÉOCODEUR ROBUSTE ====================
@st.cache_resource
def get_geolocator():
    return Nominatim(user_agent="trajets_verts_paris_v2_2025", timeout=15)

geolocator = get_geolocator()

LIEUX_PARIS = ["Bastille","République","Nation","Daumesnil","Montmartre","Sacré Coeur","Pigalle","Châtelet","Les Halles","Opéra","Gare de Lyon","Gare du Nord","Gare de l'Est","Invalides","Tour Eiffel","Trocadéro","Champs-Élysées","Arc de Triomphe","Louvre","Notre-Dame","Saint-Michel","Oberkampf","Belleville","Ménilmontant","La Villette","Buttes-Chaumont","Canal Saint-Martin","Marais","Saint-Germain","Odéon","Montparnasse","Denfert-Rochereau","Porte d'Orléans","Concorde","Luxembourg","Place Vendôme"]

def geocode_smart(query):
    query = query.strip().title()
    matches = get_close_matches(query, LIEUX_PARIS, n=1, cutoff=0.7)
    if matches:
        query = matches[0]
    
    full_query = f"{query}, Paris, France"
    try:
        time.sleep(1.2)  # respect de la politique Nominatim
        location = geolocator.geocode(
            full_query,
            country_codes="fr",
            exactly_one=True,
            timeout=15
        )
        if location:
            return location, query
    except:
        pass
    return None, query

# ==================== UI ====================
col1, col2 = st.columns(2)
with col1:
    depart = st.text_input("Départ", "Daumesnil")
with col2:
    arrivee = st.text_input("Arrivée", "Montmartre")

mode = st.radio("Mode de déplacement", ["Marche", "Vélo"], horizontal=True)
google_mode = "walking" if mode == "Marche" else "bicycling"

if st.button("Prédire Route Verte", type="primary", use_container_width=True):
    with st.spinner("Recherche des lieux…"):
        loc1, nom1 = geocode_smart(depart)
        loc2, nom2 = geocode_smart(arrivee)

        if not loc1 or not loc2:
            st.error("Lieu non trouvé. Essaie « Bastille », « République », « Nation », « Montmartre »…")
        else:
            aff_depart = nom1 if nom1 != depart.strip().title() else depart
            aff_arrivee = nom2 if nom2 != arrivee.strip().title() else arrivee

            origins = f"{loc1.latitude},{loc1.longitude}"
            destinations = f"{loc2.latitude},{loc2.longitude}"
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

                    st.markdown(f"<div class='success-box'>Trouvé ! {aff_depart} → {aff_arrivee}</div>", unsafe_allow_html=True)

                    c1, c2 = st.columns(2)
                    c1.metric("Distance", f"{distance_km} km")
                    c2.metric("Temps estimé", f"{duration_min} min en {mode.lower()}")

                    c3, c4 = st.columns(2)
                    c3.metric("AQI Paris", live_aqi,
                            help="Indice de qualité de l’air en temps réel (waqi.info)\n"
                            "• 0–50 : Bon (vert)\n"
                            "• 51–100 : Modéré (jaune)\n"
                            "• 101–150 : Mauvais pour les sensibles (orange)\n"
                            "• >150 : Mauvais (rouge)")
                    c4.metric("Green Score", green_score,
                              help="Plus le score est bas → plus l’air est sain !\n• < 0.4 : Air excellent\n• 0.4–0.7 : Air moyen – surveille\n• > 0.7 : Air pollué – évite")

                    if green_score > 0.7:
                        st.markdown("<div class='danger-box'>Air pollué – évite ce trajet !</div>", unsafe_allow_html=True)
                    elif green_score > 0.4:
                        st.markdown("<div class='warning-box'>Air moyen – surveille</div>", unsafe_allow_html=True)
                    else:
                        st.success("Air excellent – fonce à vélo ou à pied !")

                    st.bar_chart({"AQI": [live_aqi], "Green Score ×100": [green_score*100]}, height=320)
                else:
                    st.error("Google Distance Matrix : pas de trajet trouvé.")
            except Exception as e:
                st.error("Erreur réseau Google. Vérifie ta clé ou la connexion.")

# ==================== FOOTER ====================
st.divider()
st.markdown("""
<div style='text-align:center; color:#ffffff; font-size:1.1em; padding:20px;'>
    © 2025 <strong>Trajets Verts Paris</strong> – Créé par <strong>Raymond Gadji</strong><br>
    Données : waqi.info • Google Maps • OpenStreetMap • Airparif
</div>
""", unsafe_allow_html=True)
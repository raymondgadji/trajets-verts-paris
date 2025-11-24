import streamlit as st
import pandas as pd
from sklearn.linear_model import LinearRegression
import requests
from geopy.geocoders import Nominatim
import numpy as np
import time
from difflib import get_close_matches

# ==================== STYLE + RADIO BLANC ====================
st.set_page_config(page_title="Trajets Verts Paris", page_icon="Bicycle")
st.markdown("""
<style>
    .stApp {background:none!important;}
    .stButton>button {background:#1b5b00!important;color:white!important;border:none!important;border-radius:16px!important;height:3.8em!important;font-size:1.3em!important;font-weight:bold!important;}
    .stTextInput>div>div>input {border:2px solid #1b5b00!important;border-radius:8px;}
    .success-box {background:#1b5b00;color:white;padding:1.6rem;border-radius:16px;text-align:center;font-size:1.7em;font-weight:bold;}
    .warning-box {background:#e65100;color:white;padding:1.6rem;border-radius:16px;text-align:center;font-size:1.7em;font-weight:bold;}
    .danger-box {background:#c62828;color:white;padding:1.6rem;border-radius:16px;text-align:center;font-size:1.7em;font-weight:bold;}
    [data-baseweb="radio"] [data-checked="true"] > div:first-child::after {background:white!important;}
    [data-baseweb="radio"] [data-checked="true"] > div:first-child {border-color:white!important;}
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align:center;color:white;font-size:3.2em;margin:0;'>Trajets Verts Paris 🚴‍♂️🌳🚲🌳🚴‍♂️🌳🚲</h1>", True)

# ==================== SECRETS ====================
token_aqi = st.secrets["token_aqi"]
google_key = st.secrets["google_key"]

# ==================== AQI + MODÈLE ====================
try:
    aqi = requests.get(f"https://api.waqi.info/feed/paris/?token={token_aqi}").json()["data"]
    live_aqi = int(aqi["aqi"])
    live_pm25 = aqi["iaqi"].get("pm25", {}).get("v", 15)
    live_no2 = aqi["iaqi"].get("no2", {}).get("v", 30)
except:
    live_aqi, live_pm25, live_no2 = 50, 15, 30

@st.cache_resource
def load_model():
    df = pd.read_csv("paris_air.csv", delimiter=";")
    df["score"] = (df["NO2 Fond-urbain Moyenne annuelle - Airparif"]*0.5 + df["PM2-5 Fond urbain Moyenne annuelle - Airparif"]*0.5)/100
    X = df[["NO2 Fond-urbain Moyenne annuelle - Airparif","PM2-5 Fond urbain Moyenne annuelle - Airparif"]]
    return LinearRegression().fit(X, df["score"])
model = load_model()

# ==================== GÉOCODEUR STABLE ====================
@st.cache_resource
def get_geo():
    return Nominatim(user_agent="trajets_verts_paris_2025", timeout=10)
geo = get_geo()

LIEUX = ["Bastille","République","Nation","Daumesnil","Montmartre","Tour Eiffel","Louvre","Châtelet","Gare du Nord","Gare de Lyon","Opéra","Invalides","Trocadéro","Saint-Michel","Odéon","Les Halles","Porte d'Orléans","Denfert-Rochereau","Buttes-Chaumont","Sacré-Coeur","Pigalle","Concorde","Champs-Élysées"]

def find_place(q):
    q = q.strip().title()
    match = get_close_matches(q, LIEUX, n=1, cutoff=0.6)
    if match: q = match[0]
    time.sleep(1)
    loc = geo.geocode(q + ", Paris, France", country_codes="fr", exactly_one=True)
    if loc: return (loc.latitude, loc.longitude), q
    return None, q

# ==================== UI ====================
c1, c2 = st.columns(2)
with c1: depart = st.text_input("Départ", "Daumesnil")
with c2: arrivee = st.text_input("Arrivée", "Montmartre")

mode = st.radio("Mode", ["Marche", "Vélo"], horizontal=True)
gmode = "walking" if mode == "Marche" else "bicycling"

if st.button("Prédire Route Verte", type="primary", use_container_width=True):
    with st.spinner("Recherche…"):
        p1, n1 = find_place(depart)
        p2, n2 = find_place(arrivee)
        if not p1 or not p2:
            st.error("Lieu non trouvé – essaie Bastille, Tour Eiffel, République, Montmartre…")
        else:
            url = f"https://maps.googleapis.com/maps/api/distancematrix/json?origins={p1[0]},{p1[1]}&destinations={p2[0]},{p2[1]}&mode={gmode}&key={google_key}"
            r = requests.get(url, timeout=15).json()
            el = r["rows"][0]["elements"][0]
            if el["status"] == "OK":
                km = round(el["distance"]["value"]/1000, 2)
                mins = round(el["duration"]["value"]/60, 1)
                score = round((km/10)*(1-model.predict(np.array([[live_no2, live_pm25]]))[0]), 3)

                st.markdown(f"<div class='success-box'>Trouvé ! {n1} → {n2}</div>", True)

                # === AQI avec vraie feuille ===
                if live_aqi <= 50:
                    st.markdown(f"<div class='success-box'>Leaf AQI Paris : <strong>{live_aqi}</strong> → Air très bon</div>", True)
                elif live_aqi <= 100:
                    st.markdown(f"<div class='warning-box'>Face neutral AQI Paris : <strong>{live_aqi}</strong> → Air modéré</div>", True)
                else:
                    st.markdown(f"<div class='danger-box'>Pollution AQI Paris : <strong>{live_aqi}</strong> → Air mauvais</div>", True)

                # === GREEN SCORE avec vraie feuille ===
                if score < 0.4:
                    st.markdown(f"<div class='success-box'>Leaf Green Score : <strong>{score}</strong> → Air excellent – fonce !</div>", True)
                elif score <= 0.7:
                    st.markdown(f"<div class='warning-box'>Face neutral Green Score : <strong>{score}</strong> → Air moyen – surveille</div>", True)
                else:
                    st.markdown(f"<div class='danger-box'>Pollution Green Score : <strong>{score}</strong> → Air pollué – évite !</div>", True)

                # === Métriques + BAR CHART (de retour !) ===
                ca, cb = st.columns(2)
                ca.metric("Distance", f"{km} km")
                cb.metric("Temps estimé", f"{mins} min")

                st.bar_chart({"AQI Paris": [live_aqi], "Green Score ×100": [score*100]}, height=320)
            else:
                st.error("Google n’a pas pu calculer le trajet")

# ==================== FOOTER ====================
st.divider()
st.markdown("""
<div style='text-align:center; color:#ffffff; font-size:1.1em; padding:20px;'>
    © 2025 <strong>Trajets Verts Paris</strong> – Créé par <strong>Raymond Gadji</strong>(AI_Y) Artificial Intelligence  Yedidia<br>
    Données : waqi.info • Google Maps • OpenStreetMap • Airparif
</div>
""", unsafe_allow_html=True)

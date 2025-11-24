import streamlit as st
import pandas as pd
from sklearn.linear_model import LinearRegression
import requests
import numpy as np

# ==================== STYLE FIXÉ UNE FOIS POUR TOUTES ====================
st.set_page_config(page_title="Trajets Verts Paris", page_icon="Bicycle")
st.markdown("""
<style>
    .stApp {background: none !important;}
    .stButton>button {background:#1b5b00!important;color:white!important;border:none!important;border-radius:16px!important;height:3.8em!important;font-size:1.3em!important;font-weight:bold!important;}
    .stTextInput>div>div>input {border:2px solid #1b5b00!important;border-radius:8px;}
    .success-box {background:#1b5b00;color:white;padding:1.6rem;border-radius:16px;text-align:center;font-size:1.7em;font-weight:bold;}
    .warning-box {background:#e65100;color:white;padding:1.6rem;border-radius:16px;text-align:center;font-size:1.7em;font-weight:bold;}
    .danger-box {background:#c62828;color:white;padding:1.6rem;border-radius:16px;text-align:center;font-size:1.7em;font-weight:bold;}

    /* CERCLE COCHÉ 100% BLANC — FONCTIONNE EN 2025 */
    section[data-testid="stSidebar"] [data-baseweb="radio"] [data-checked="true"] > div:first-child::after,
    [data-baseweb="radio"] [data-checked="true"] > div:first-child::after {
        background-color: white !important;
    }
    [data-baseweb="radio"] [data-checked="true"] > div:first-child {
        border-color: white !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align:center;color:white;font-size:3.2em;margin-bottom:0;'>Trajets Verts Paris 🚴‍♂️🌳🚲🌳🚴‍♂️🌳🚲</h1>", True)

# ==================== SECRETS ====================
token_aqi = st.secrets["token_aqi"]
google_key = st.secrets["google_key"]

# ==================== AQI + MODEL ====================
try:
    aqi = requests.get(f"https://api.waqi.info/feed/paris/?token={token_aqi}", timeout=10).json()
    live_aqi = int(aqi["data"]["aqi"])
    live_pm25 = aqi["data"]["iaqi"].get("pm25", {}).get("v", 15)
    live_no2 = aqi["data"]["iaqi"].get("no2", {}).get("v", 30)
except:
    live_aqi, live_pm25, live_no2 = 50, 15, 30

@st.cache_resource
def get_model():
    df = pd.read_csv("paris_air.csv", delimiter=";")
    df["score"] = (df["NO2 Fond-urbain Moyenne annuelle - Airparif"]*0.5 + df["PM2-5 Fond urbain Moyenne annuelle - Airparif"]*0.5)/100
    X = df[["NO2 Fond-urbain Moyenne annuelle - Airparif","PM2-5 Fond urbain Moyenne annuelle - Airparif"]]
    y = df["score"]
    return LinearRegression().fit(X, y)
model = get_model()

# ==================== GÉOCODAGE SIMPLE ET FIABLE (PLUS DE BUG) ====================
def geocode(query):
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": f"{query}, Paris, France", "key": google_key}
    try:
        r = requests.get(url, params=params, timeout=10).json()
        if r["results"]:
            loc = r["results"][0]["geometry"]["location"]
            addr = r["results"][0]["formatted_address"]
            return (loc["lat"], loc["lng"]), addr.split(",")[0]
    except:
        pass
    return None, None

# ==================== UI ====================
c1, c2 = st.columns(2)
with c1:
    depart = st.text_input("Départ", placeholder="Bastille, Tour Eiffel, Gare du Nord…")
with c2:
    arrivee = st.text_input("Arrivée", placeholder="République, Louvre…")

mode = st.radio("Mode", ["Marche", "Vélo"], horizontal=True)
gmode = "walking" if mode == "Marche" else "bicycling"

if st.button("Prédire Route Verte", type="primary", use_container_width=True):
    if not depart.strip() or not arrivee.strip():
        st.error("Remplis les deux champs")
    else:
        with st.spinner("Calcul…"):
            p1, name1 = geocode(depart)
            p2, name2 = geocode(arrivee)
            if not p1 or not p2:
                st.error("Lieu non trouvé — tape le nom complet (ex: Bastille, Tour Eiffel)")
            else:
                url = "https://maps.googleapis.com/maps/api/distancematrix/json"
                params = {"origins": f"{p1[0]},{p1[1]}", "destinations": f"{p2[0]},{p2[1]}", "mode": gmode, "key": google_key}
                r = requests.get(url, params=params, timeout=15).json()
                el = r["rows"][0]["elements"][0]
                if el["status"] == "OK":
                    km = round(el["distance"]["value"]/1000, 2)
                    mins = round(el["duration"]["value"]/60, 1)
                    score = round((km/10)*(1-model.predict(np.array([[live_no2, live_pm25]]))[0]), 3)

                    st.markdown(f"<div class='success-box'>Trouvé ! {name1} → {name2}</div>", True)

                    # AQI
                    if live_aqi <= 50:
                        st.markdown(f"<div class='success-box'>Leaf AQI Paris : <strong>{live_aqi}</strong> → Air très bon</div>", True)
                    elif live_aqi <= 100:
                        st.markdown(f"<div class='warning-box'>Face neutral AQI Paris : <strong>{live_aqi}</strong> → Air modéré</div>", True)
                    else:
                        st.markdown(f"<div class='danger-box'>Pollution AQI Paris : <strong>{live_aqi}</strong> → Air mauvais</div>", True)

                    # Green Score
                    if score < 0.4:
                        st.markdown(f"<div class='success-box'>Leaf Green Score : <strong>{score}</strong> → Air excellent !</div>", True)
                    elif score <= 0.7:
                        st.markdown(f"<div class='warning-box'>Face neutral Green Score : <strong>{score}</strong> → Air moyen</div>", True)
                    else:
                        st.markdown(f"<div class='danger-box'>Pollution Green Score : <strong>{score}</strong> → Air pollué</div>", True)

                    ca, cb = st.columns(2)
                    ca.metric("Distance", f"{km} km")
                    cb.metric("Temps", f"{mins} min")
                else:
                    st.error("Pas de trajet trouvé")

# ==================== FOOTER ====================
st.divider()
st.markdown("""
<div style='text-align:center; color:#1b5b00; font-size:1.1em; padding:20px;'>
    © 2025 <strong>Trajets Verts Paris</strong> – Créé par <strong>Raymond Gadji</strong>  Artificial Intelligence  Yedidia (AI_Y)<br>
    Données : waqi.info • Google Maps • OpenStreetMap • Airparif
</div>
""", unsafe_allow_html=True)

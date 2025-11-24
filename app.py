import streamlit as st
import pandas as pd
from sklearn.linear_model import LinearRegression
import requests
import numpy as np

# ==================== CONFIG & STYLE (cercle blanc garanti) ====================
st.set_page_config(page_title="Trajets Verts Paris", page_icon="Bicycle")
st.markdown("""
<style>
    .stApp {background: none !important;}
    .stButton>button {background-color:#1b5b00!important;color:white!important;border:none!important;border-radius:16px!important;height:3.8em!important;font-size:1.3em!important;font-weight:bold!important;}
    .stButton>button:hover {background-color:#256b00!important;}
    .stTextInput>div>div>input {border:2px solid #1b5b00!important;border-radius:8px;}
    .success-box {background-color:#1b5b00;color:white;padding:1.6rem;border-radius:16px;text-align:center;font-size:1.7em;font-weight:bold;}
    .warning-box {background-color:#e65100;color:white;padding:1.6rem;border-radius:16px;text-align:center;font-size:1.7em;font-weight:bold;}
    .danger-box {background-color:#c62828;color:white;padding:1.6rem;border-radius:16px;text-align:center;font-size:1.7em;font-weight:bold;}

    /* CERCLE COCHÉ BLANC — VERSION QUI MARCHE À 1000% EN 2025 */
    [data-baseweb="radio"] [data-checked="true"] > div:first-child {
        border-color: white !important;
    }
    [data-baseweb="radio"] [data-checked="true"] > div:first-child::after {
        background-color: white !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<h1 style="text-align:center;color:#ffffff;font-size:3.2em;margin-bottom:0;">
    Trajets Verts Paris 🚴‍♂️🌳🚲🌳🚴‍♂️🌳🚲
</h1>
""", unsafe_allow_html=True)

# ==================== SECRETS ====================
token_aqi = st.secrets["token_aqi"]
google_key = st.secrets["google_key"]

# ==================== AQI LIVE ====================
try:
    resp = requests.get(f'https://api.waqi.info/feed/paris/?token={token_aqi}', timeout=10)
    live_aqi = int(resp.json()['data'].get('aqi', 50))
    live_pm25 = resp.json()['data']['iaqi'].get('pm25', {}).get('v', 15)
    live_no2 = resp.json()['data']['iaqi'].get('no2', {}).get('v', 30)
except:
    live_aqi, live_pm25, live_no2 = 50, 15, 30

# ==================== MODÈLE ====================
@st.cache_resource
def load_model():
    df = pd.read_csv('paris_air.csv', delimiter=';')
    df['score'] = (df['NO2 Fond-urbain Moyenne annuelle - Airparif']*0.5 + df['PM2-5 Fond urbain Moyenne annuelle - Airparif']*0.5)/100
    X = df[['NO2 Fond-urbain Moyenne annuelle - Airparif','PM2-5 Fond urbain Moyenne annuelle - Airparif']]
    y = df['score']
    return LinearRegression().fit(X, y)
model = load_model()

# ==================== AUTOCOMPLÉTION + GÉOCODAGE (ultra-fiable) ====================
def search_place(query):
    if len(query) < 2: return None, None
    url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = {"input": query + " Paris", "key": google_key, "language": "fr", "components": "country:fr"}
    try:
        r = requests.get(url, params=params, timeout=8)
        pred = r.json()["predictions"]
        if pred:
            place_id = pred[0]["place_id"]
            # Détails du lieu
            detail_url = "https://maps.googleapis.com/maps/api/place/details/json"
            r2 = requests.get(detail_url, params={"place_id": place_id, "key": google_key, "fields": "geometry,formatted_address"}, timeout=8)
            data = r2.json()
            if data["status"] == "OK":
                loc = data["result"]["geometry"]["location"]
                addr = data["result"]["formatted_address"]
                return (loc["lat"], loc["lng"]), addr
    except:
        pass
    return None, None

# ==================== UI ====================
c1, c2 = st.columns(2)
with c1:
    depart = st.text_input("Départ", placeholder="ex: Bastille, Tour Eiffel…")
with c2:
    arrivee = st.text_input("Arrivée", placeholder="ex: République, Louvre…")

mode = st.radio("Mode", ["Marche", "Vélo"], horizontal=True)
gmode = "walking" if mode == "Marche" else "bicycling"

if st.button("Prédire Route Verte", type="primary", use_container_width=True):
    if not depart.strip() or not arrivee.strip():
        st.error("Remplis les deux champs")
    else:
        with st.spinner("Recherche…"):
            coord1, addr1 = search_place(depart)
            coord2, addr2 = search_place(arrivee)
            if not coord1 or not coord2:
                st.error("Lieu non trouvé – tape un peu plus de lettres")
            else:
                lat1, lon1 = coord1
                lat2, lon2 = coord2
                url = "https://maps.googleapis.com/maps/api/distancematrix/json"
                params = {"origins": f"{lat1},{lon1}", "destinations": f"{lat2},{lon2}", "mode": gmode, "key": google_key}
                r = requests.get(url, params=params, timeout=15).json()
                el = r["rows"][0]["elements"][0]
                if el["status"] == "OK":
                    dist_km = round(el["distance"]["value"]/1000, 2)
                    duree_min = round(el["duration"]["value"]/60, 1)
                    pred = model.predict(np.array([[live_no2, live_pm25]]))[0]
                    green_score = round((dist_km/10)*(1-pred), 3)

                    st.markdown(f"<div class='success-box'>Trouvé ! {addr1.split(',')[0]} → {addr2.split(',')[0]}</div>", unsafe_allow_html=True)

                    # AQI
                    if live_aqi <= 50:
                        st.markdown("<div class='success-box'>Leaf AQI Paris : <strong>{}</strong> → Air très bon</div>".format(live_aqi), True)
                    elif live_aqi <= 100:
                        st.markdown("<div class='warning-box'>Face neutral AQI Paris : <strong>{}</strong> → Air modéré</div>".format(live_aqi), True)
                    else:
                        st.markdown("<div class='danger-box'>Pollution AQI Paris : <strong>{}</strong> → Air mauvais</div>".format(live_aqi), True)

                    # Green Score
                    if green_score < 0.4:
                        st.markdown("<div class='success-box'>Leaf Green Score : <strong>{}</strong> → Air excellent – fonce !</div>".format(green_score), True)
                    elif green_score <= 0.7:
                        st.markdown("<div class='warning-box'>Face neutral Green Score : <strong>{}</strong> → Air moyen – surveille</div>".format(green_score), True)
                    else:
                        st.markdown("<div class='danger-box'>Pollution Green Score : <strong>{}</strong> → Air pollué – évite !</div>".format(green_score), True)

                    ca, cb = st.columns(2)
                    ca.metric("Distance", f"{dist_km} km")
                    cb.metric("Temps", f"{duree_min} min")

                    st.bar_chart({"AQI": [live_aqi], "Green Score ×100": [green_score*100]}, height=320)
                else:
                    st.error("Pas de trajet trouvé")

# ==================== FOOTER ====================
st.divider()
st.markdown("""
<div style='text-align:center;color:#ffffff;font-size:1.1em;padding:20px;'>
    © 2025 <strong>Trajets Verts Paris</strong> – Raymond Gadji (AI_Y) Artificial Intelligence Yedidia<br>
    Données : waqi.info • Google Maps • Airparif
</div>
""", unsafe_allow_html=True)
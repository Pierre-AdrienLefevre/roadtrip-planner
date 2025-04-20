import streamlit as st
import pandas as pd
import folium
import json
from streamlit_folium import st_folium
from core import calculate_routes_osrm


st.set_page_config(layout="wide")
st.title("🗺️ Carte interactive du Roadtrip 🚗")

# Charger le fichier parquet
uploaded_file = 'data/hebergements_chemins.parquet'
df = pd.read_parquet(uploaded_file)


# Calculer les distances et les trajets
distances, routes, df = calculate_routes_osrm(df)

# **Création de la carte Folium**
start_lat = df.iloc[0]["Latitude"]
start_lon = df.iloc[0]["Longitude"]
m = folium.Map(location=[start_lat, start_lon], zoom_start=6, width="100%", height="100%")

# Ajouter les tracés des routes entre chaque point
for i in range(len(df) - 1):
    if pd.notna(df.iloc[i]["Chemin"]):
        route_coords = json.loads(df.iloc[i]["Chemin"])  # Charger le tracé sauvegardé
        if route_coords:  # Vérifier que le tracé n'est pas vide
            folium.PolyLine(
                locations=route_coords,
                color="blue",
                weight=4,
                opacity=0.7
            ).add_to(m)

# Ajouter les marqueurs pour les points de départ et d'arrivée
folium.Marker(
    location=[df.iloc[0]["Latitude"], df.iloc[0]["Longitude"]],
    popup=f"Départ: {df.iloc[0]['Adresse']}",
    icon=folium.Icon(color="red", icon="info-sign")
).add_to(m)

folium.Marker(
    location=[df.iloc[-1]["Latitude"], df.iloc[-1]["Longitude"]],
    popup=f"Arrivée: {df.iloc[-1]['Adresse']}",
    icon=folium.Icon(color="green", icon="flag")
).add_to(m)

# Ajouter des marqueurs pour toutes les autres étapes
for i in range(1, len(df) - 1):
    folium.Marker(
        location=[df.iloc[i]["Latitude"], df.iloc[i]["Longitude"]],
        popup=f"Étape {i}: {df.iloc[i]['Adresse']}",
        icon=folium.Icon(color="blue", icon="cloud")
    ).add_to(m)

# **Afficher la carte en plein écran**
st_folium(m, width=None, height=800, zoom=6)
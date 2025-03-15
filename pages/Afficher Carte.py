import streamlit as st
import pandas as pd
import requests
import polyline
import folium
import json
from streamlit_folium import st_folium

st.set_page_config(layout="wide")
st.title("🗺️ Carte interactive du Roadtrip 🚗")

# Charger le fichier CSV
uploaded_file = 'data/hebergements_chemins.parquet'
df = pd.read_parquet(uploaded_file)

# Vérifier si les colonnes Latitude et Longitude existent
if "Latitude" not in df.columns or "Longitude" not in df.columns:
    st.error("Les colonnes 'Latitude' et 'Longitude' sont absentes du fichier CSV. Vérifiez votre fichier.")
    st.stop()


# Ajouter les colonnes manquantes
if "Chemin" not in df.columns:
    df["Chemin"] = None
if "Distance (km)" not in df.columns:
    df["Distance (km)"] = None

# Fonction pour interroger l'API OSRM entre deux points
def get_osrm_route(lat1, lon1, lat2, lon2):
    """ Interroge OSRM pour obtenir le tracé et la distance entre deux points """
    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{lon1},{lat1};{lon2},{lat2}"
        "?overview=full&geometries=polyline"
    )
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data["routes"]:
            route = data["routes"][0]
            distance_km = route["distance"] / 1000  # Conversion en km
            route_coords = polyline.decode(route["geometry"])  # Liste (lat, lon)
            return distance_km, json.dumps(route_coords)  # Sauvegarde en JSON
    return None, None

@st.cache_data
def calculate_routes_osrm(df):
    """ Calcule les distances et les trajets avec OSRM si non enregistrés """
    distances = []
    route_geoms = []
    for i in range(len(df) - 1):
        lat1, lon1 = df.iloc[i]["Latitude"], df.iloc[i]["Longitude"]
        lat2, lon2 = df.iloc[i + 1]["Latitude"], df.iloc[i + 1]["Longitude"]

        # Vérifier si le chemin est déjà dans le CSV
        if pd.notna(df.iloc[i]["Chemin"]):
            route_coords = json.loads(df.iloc[i]["Chemin"])  # Charger le tracé depuis le CSV
            distance = df.iloc[i]["Distance (km)"]
        else:
            distance, route_coords = get_osrm_route(lat1, lon1, lat2, lon2)
            df.at[i, "Distance (km)"] = distance  # Mettre à jour la DataFrame
            df.at[i, "Chemin"] = route_coords if route_coords else json.dumps([])  # Sauvegarder proprement

        distances.append(distance)
        route_geoms.append(route_coords)

    return distances, route_geoms

# Calculer les distances et les trajets
distances, routes = calculate_routes_osrm(df)

# Ajouter une valeur vide pour la dernière ligne pour correspondre à df
distances.append(None)
routes.append(json.dumps([]))

# Mettre à jour la DataFrame
df["Distance (km)"] = distances
df["Chemin"] = routes

# Sauvegarder les trajets mis à jour dans Parquet # Assurer que tout est bien JSON
df["Chemin"] = df["Chemin"].apply(lambda x: json.dumps(x) if isinstance(x, list) else x)
df.to_parquet('data/hebergements_chemins.parquet')


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
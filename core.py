import pandas as pd
import streamlit as st
import json
from opencage.geocoder import OpenCageGeocode
import polyline
import requests

def add_lat_lon(df, address_column="Adresse"):
    try:
        api_key = st.secrets["opencage"]["api_key"]
    except KeyError:
        st.error("Clé API OpenCage manquante. Vérifiez le fichier .streamlit/secrets.toml.")
        return df

    geocoder = OpenCageGeocode(api_key)

    # Créer les colonnes Latitude et Longitude si elles n'existent pas
    if "Latitude" not in df.columns:
        df["Latitude"] = None
    if "Longitude" not in df.columns:
        df["Longitude"] = None

    def get_coordinates(address):
        try:
            result = geocoder.geocode(address)
            if result:
                return result[0]["geometry"]["lat"], result[0]["geometry"]["lng"]
        except Exception as e:
            st.error(f"Erreur pour {address} : {e}")
        return None, None

    for index, row in df.iterrows():
        if pd.isna(row["Latitude"]) or pd.isna(row["Longitude"]):
            lat, lon = get_coordinates(row[address_column])
            df.at[index, "Latitude"] = lat
            df.at[index, "Longitude"] = lon

    st.info("✅ Latitude et Longitude ajoutées avec succès !")
    return df

def get_osrm_route(lat1, lon1, lat2, lon2):
    """Interroge OSRM pour obtenir le tracé et la distance entre deux points."""
    # Vérifier que les coordonnées sont valides
    if None in (lat1, lon1, lat2, lon2):
        print("Coordonnées invalides, impossible de calculer l'itinéraire.")
        return None, None

    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{lon1},{lat1};{lon2},{lat2}"
        "?overview=full&geometries=polyline"
    )
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data.get("routes"):
            route = data["routes"][0]
            distance_km = route["distance"] / 1000  # Conversion en km
            route_coords = polyline.decode(route["geometry"])  # Liste de (lat, lon)
            return distance_km, json.dumps(route_coords)  # Sauvegarde en JSON
    return None, None


@st.cache_data
def calculate_routes_osrm(df):
    """Calcule les distances et les trajets avec OSRM si non enregistrés."""
    # Créer une copie du DataFrame pour éviter de modifier l'original
    df = df.copy()

    # S'assurer que les colonnes nécessaires existent
    for col in ["Latitude", "Longitude"]:
        if col not in df.columns:
            df[col] = None

    if "Chemin" not in df.columns:
        df["Chemin"] = None
    if "Distance (km)" not in df.columns:
        df["Distance (km)"] = None

    # Vérifier s'il y a des coordonnées manquantes et les ajouter
    missing_coords = df[df["Latitude"].isna() | df["Longitude"].isna()].index
    if len(missing_coords) > 0:
        # Appliquer add_lat_lon seulement aux lignes avec coordonnées manquantes
        df_missing = df.loc[missing_coords].copy()
        df_missing = add_lat_lon(df_missing)

        # Mettre à jour le DataFrame original avec les nouvelles coordonnées
        for idx in missing_coords:
            df.loc[idx, "Latitude"] = df_missing.loc[idx, "Latitude"]
            df.loc[idx, "Longitude"] = df_missing.loc[idx, "Longitude"]

    # Initialiser les listes pour stocker les résultats
    distances = []
    route_geoms = []

    # Calculer les itinéraires pour chaque segment
    for i in range(len(df) - 1):  # On parcourt jusqu'à l'avant-dernier point
        lat1, lon1 = df.iloc[i]["Latitude"], df.iloc[i]["Longitude"]
        lat2, lon2 = df.iloc[i + 1]["Latitude"], df.iloc[i + 1]["Longitude"]

        # Vérifier si toutes les coordonnées sont valides
        valid_coords = pd.notna(lat1) and pd.notna(lon1) and pd.notna(lat2) and pd.notna(lon2)

        # Si les coordonnées sont valides et le tracé est déjà calculé, on le récupère
        if valid_coords and pd.notna(df.iloc[i]["Chemin"]) and pd.notna(df.iloc[i]["Distance (km)"]):
            try:
                route_coords = df.iloc[i]["Chemin"]
                if isinstance(route_coords, str):
                    route_coords = json.loads(route_coords)
                distance = df.iloc[i]["Distance (km)"]
            except Exception as e:
                st.warning(f"Erreur lors de la lecture du chemin à l'index {i}: {e}")
                distance, route_coords = get_osrm_route(lat1, lon1, lat2, lon2)
        # Sinon, on calcule un nouveau tracé si les coordonnées sont valides
        elif valid_coords:
            distance, route_coords = get_osrm_route(lat1, lon1, lat2, lon2)
        # Si les coordonnées sont invalides, on ne peut pas calculer de tracé
        else:
            st.warning(f"Coordonnées manquantes pour le segment {i} à {i + 1}, impossible de calculer l'itinéraire.")
            distance = None
            route_coords = json.dumps([])

        # Mettre à jour le DataFrame directement
        df.at[i, "Distance (km)"] = distance

        # S'assurer que route_coords est au format JSON
        if isinstance(route_coords, list):
            route_coords = json.dumps(route_coords)
        df.at[i, "Chemin"] = route_coords

        # Stocker pour retour de fonction
        distances.append(distance)
        route_geoms.append(route_coords)

    # Ajouter une dernière valeur pour correspondre à la taille du DataFrame
    distances.append(None)
    route_geoms.append(json.dumps([]))

    # Sauvegarder le DataFrame
    df.to_parquet('data/hebergements_chemins.parquet')

    return distances, route_geoms, df
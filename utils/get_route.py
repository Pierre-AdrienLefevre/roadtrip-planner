import json
from math import atan2, cos, radians, sin, sqrt

import pandas as pd
import requests
import streamlit as st
from opencage.geocoder import OpenCageGeocode


def add_lat_lon(df, address_column="Adresse"):
    """Ajoute les coordonnées géographiques (latitude, longitude) pour chaque adresse"""
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


def get_route(start_coords, end_coords, type_deplacement="Marche"):
    """
    Calcule un itinéraire en utilisant l'API OpenRouteService.
    Pour les points très proches (<50m), crée une ligne directe.

    Args:
        start_coords: Tuple (latitude, longitude) du point de départ
        end_coords: Tuple (latitude, longitude) du point d'arrivée
        type_deplacement: Type de déplacement ('Marche' ou 'Voiture')

    Returns:
        Un tuple (distance_km, duration_hours, coords_json) ou (None, None, None) en cas d'erreur
    """

    # Vérifier que les coordonnées sont valides
    if None in (start_coords[0], start_coords[1], end_coords[0], end_coords[1]):
        print("Coordonnées invalides, impossible de calculer l'itinéraire.")
        return None, None, None

    # Calculer la distance haversine entre les deux points
    def haversine_distance(lat1, lon1, lat2, lon2):
        # Rayon de la Terre en mètres
        R = 6371000

        # Conversion en radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

        # Différence de latitude et longitude
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        # Formule Haversine
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        distance = R * c

        return distance

    # Calculer la distance directe
    direct_distance = haversine_distance(start_coords[0], start_coords[1], end_coords[0], end_coords[1])

    # Si les points sont très proches (moins de 50m), connecter directement
    if direct_distance <= 50:  # 50 mètres comme seuil
        print(f"Points très proches ({direct_distance:.2f}m), création d'une ligne directe")

        # Créer un itinéraire simple avec juste les deux points
        route_coords = [
            [start_coords[0], start_coords[1]],
            [end_coords[0], end_coords[1]],
        ]

        # Estimer la durée (pour la randonnée: ~3.5 km/h)
        vitesse_km_h = 3.5 if type_deplacement == "Marche" else 50
        distance_km = direct_distance / 1000
        duration_hours = distance_km / vitesse_km_h

        return distance_km, duration_hours, json.dumps(route_coords)

    # Déterminer le profil ORS en fonction du type de déplacement
    if not isinstance(type_deplacement, str):
        print(f"Type de déplacement invalide: {type_deplacement} (type: {type(type_deplacement)})")
        return None, None, None

    if type_deplacement == "Marche":
        profile = "foot-hiking"  # Utilise le profil randonnée
    elif type_deplacement == "Voiture":
        profile = "driving-car"
    else:
        print(f"Type de déplacement non reconnu: {type_deplacement}")
        return None, None, None

    # Votre clé API OpenRouteService (inscription gratuite nécessaire)
    api_key = token = st.secrets["openrouteservices"]["token"]

    # Construire la requête
    base_url = "https://api.openrouteservice.org/v2/directions/" + profile

    # Notez que ORS attend les coordonnées en [longitude, latitude]
    body = {
        "coordinates": [
            [start_coords[1], start_coords[0]],  # [lon, lat]
            [end_coords[1], end_coords[0]],  # [lon, lat]
        ],
        "format": "json",
        "units": "km",
        "language": "fr",
    }

    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json; charset=utf-8",
    }

    try:
        response = requests.post(base_url, json=body, headers=headers)
        response.raise_for_status()

        data = response.json()

        if "routes" in data and len(data["routes"]) > 0:
            route = data["routes"][0]

            # Extraire les informations pertinentes
            distance_km = route["summary"]["distance"]  # Déjà en km
            duration_hours = route["summary"]["duration"] / 3600  # Conversion de secondes en heures

            # Extraire les coordonnées du chemin - ORS utilise format différent de GH
            geometry = route["geometry"]
            if isinstance(geometry, str):
                # Si c'est encodé, décoder avec polyline
                import polyline

                route_coords = polyline.decode(geometry)
            else:
                # Sinon, extraire directement
                route_coords = []
                for point in geometry["coordinates"]:
                    # OpenRouteService retourne [lon, lat], on inverse pour [lat, lon]
                    route_coords.append([point[1], point[0]])

            # Convertir en JSON pour stockage
            route_coords_json = json.dumps(route_coords)

            return distance_km, duration_hours, route_coords_json
        else:
            print("Aucun itinéraire trouvé dans la réponse OpenRouteService")
            return None, None, None

    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la requête OpenRouteService: {e}")
        if "response" in locals():
            print(f"Réponse: {response.text}")
        return None, None, None
    except (KeyError, IndexError, ValueError) as e:
        print(f"Erreur lors du traitement de la réponse OpenRouteService: {e}")
        return None, None, None


def calculate_routes(df):
    """Calcule les distances, durées et les trajets avec  si non enregistrés."""

    # Créer une copie du DataFrame pour éviter de modifier l'original
    df = df.copy()

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
    durations = []
    route_geoms = []

    # Variable pour suivre les itinéraires déjà calculés entre des paires de points
    routes_cache = {}

    # Calculer les itinéraires pour chaque segment
    for i in range(len(df) - 1):  # On parcourt jusqu'à l'avant-dernier point
        lat1, lon1 = df.iloc[i]["Latitude"], df.iloc[i]["Longitude"]
        lat2, lon2 = df.iloc[i + 1]["Latitude"], df.iloc[i + 1]["Longitude"]

        # Récupérer le type de déplacement
        if "Type_Deplacement" in df.columns and pd.notna(df.iloc[i]["Type_Deplacement"]):
            type_deplacement = df.iloc[i]["Type_Deplacement"]
        else:
            print(f"Type de déplacement non spécifié pour le segment {i} à {i + 1}")
            type_deplacement = None

        # Vérifier si toutes les coordonnées sont valides
        valid_coords = pd.notna(lat1) and pd.notna(lon1) and pd.notna(lat2) and pd.notna(lon2)

        # Créer une clé unique pour cette paire de coordonnées et type de déplacement
        if valid_coords and type_deplacement is not None:
            route_key = f"{lat1},{lon1}|{lat2},{lon2}|{type_deplacement}"

            # Vérifier si l'itinéraire est déjà dans le cache
            if route_key in routes_cache:
                distance, duration, route_coords = routes_cache[route_key]
            # Si déjà calculé dans le DataFrame et type de déplacement identique, on utilise cette valeur
            elif pd.notna(df.iloc[i]["Chemin"]) and pd.notna(df.iloc[i]["Distance (km)"]):
                try:
                    route_coords = df.iloc[i]["Chemin"]
                    if isinstance(route_coords, str):
                        route_coords = json.loads(route_coords)
                    distance = df.iloc[i]["Distance (km)"]
                    duration = df.iloc[i]["Durée (h)"] if pd.notna(df.iloc[i]["Durée (h)"]) else None

                    # Si la durée n'est pas disponible, on calcule l'itinéraire
                    if duration is None:
                        start_coords = (lat1, lon1)
                        end_coords = (lat2, lon2)
                        distance, duration, route_coords = get_route(start_coords, end_coords, type_deplacement)
                        # Mettre en cache
                        routes_cache[route_key] = (distance, duration, route_coords)
                except Exception as e:
                    print(f"Erreur lors de la lecture du chemin à l'index {i}: {e}")
                    start_coords = (lat1, lon1)
                    end_coords = (lat2, lon2)
                    distance, duration, route_coords = get_route(start_coords, end_coords, type_deplacement)
                    # Mettre en cache
                    routes_cache[route_key] = (distance, duration, route_coords)
            else:
                # Sinon on calcule un nouveau tracé
                start_coords = (lat1, lon1)
                end_coords = (lat2, lon2)
                distance, duration, route_coords = get_route(start_coords, end_coords, type_deplacement)
                # Mettre en cache
                routes_cache[route_key] = (distance, duration, route_coords)
        else:
            # Coordonnées invalides ou type de déplacement non défini
            if not valid_coords:
                print(f"Coordonnées manquantes pour le segment {i} à {i + 1}, impossible de calculer l'itinéraire.")
            else:
                print(
                    f"Type de déplacement non défini pour le segment {i} à {i + 1}, impossible de calculer l'itinéraire."
                )
            distance = None
            duration = None
            route_coords = json.dumps([])

        # Mettre à jour le DataFrame directement
        df.at[i, "Distance (km)"] = distance
        df.at[i, "Durée (h)"] = duration

        # S'assurer que route_coords est au format JSON
        if isinstance(route_coords, list):
            route_coords = json.dumps(route_coords)
        df.at[i, "Chemin"] = route_coords

        # Stocker pour retour de fonction
        distances.append(distance)
        durations.append(duration)
        route_geoms.append(route_coords)

    # Ajouter une dernière valeur pour correspondre à la taille du DataFrame
    distances.append(None)
    durations.append(None)
    route_geoms.append(json.dumps([]))

    return distances, durations, route_geoms, df

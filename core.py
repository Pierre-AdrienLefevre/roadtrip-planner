from opencage.geocoder import OpenCageGeocode
import streamlit as st
import pandas as pd
import json
import base64
from github import Github, GithubException
from io import BytesIO
from streamlit_pdf_viewer import pdf_viewer

@st.cache_data
def charger_donnees(nom_fichier="data/hebergements_chemins.parquet", format=None, branche="main"):
    """
    Fonction pour charger des données depuis un dépôt GitHub privé.

    Args:
        nom_fichier: Chemin du fichier relatif à la racine du dépôt
        format: Format de conversion souhaité
        branche: Nom de la branche (par défaut: "main")
    """
    try:
        # Récupérer les identifiants depuis les secrets Streamlit
        token = st.secrets["github"]["token"]
        repo_name = st.secrets["github"]["repo_name"]

        # Initialiser le client GitHub
        g = Github(token)
        repo = g.get_repo(repo_name)

        try:
            # Récupérer le contenu du fichier à partir de la branche spécifiée
            contents = repo.get_contents(nom_fichier, ref=branche)

            # Décoder le contenu du fichier
            decoded_content = base64.b64decode(contents.content)

            # Créer un objet BytesIO pour lire le contenu
            buffer = BytesIO(decoded_content)

            # Convertir selon le format demandé
            if format == 'parquet':
                return pd.read_parquet(buffer)
            else:
                buffer.seek(0)
                return buffer

        except Exception as e:
            st.warning(f"Erreur lors de l'accès au fichier {nom_fichier} sur la branche {branche}: {e}")
            return None

    except Exception as e:
        st.error(f"Erreur lors de l'accès au dépôt GitHub: {e}")
        return None


def sauvegarder_donnees(contenu, nom_fichier, message_commit="Mise à jour des données", branche="main"):
    """
    Fonction pour sauvegarder des données dans un dépôt GitHub privé sans créer de copie locale.

    Args:
        contenu: Contenu à sauvegarder (DataFrame, dict, str, bytes, ou BytesIO)
        nom_fichier: Nom du fichier à sauvegarder
        message_commit: Message pour le commit GitHub
        branche: Nom de la branche (par défaut: "main")

    Returns:
        bool: True si la sauvegarde a réussi, False sinon
    """
    try:
        # Récupérer les identifiants depuis les secrets Streamlit
        token = st.secrets["github"]["token"]
        repo_name = st.secrets["github"]["repo_name"]

        # Convertir le contenu en bytes selon son type
        if isinstance(contenu, pd.DataFrame):
            # Pour un DataFrame pandas
            buffer = BytesIO()
            if nom_fichier.endswith('.parquet'):
                contenu.to_parquet(buffer, index=False)
            elif nom_fichier.endswith('.csv'):
                contenu.to_csv(buffer, index=False)
            else:
                contenu.to_csv(buffer, index=False)  # CSV par défaut
            buffer.seek(0)
            github_content = buffer.read()

        elif isinstance(contenu, dict) or isinstance(contenu, list):
            # Pour un dictionnaire ou une liste (format JSON)
            github_content = json.dumps(contenu).encode('utf-8')

        elif isinstance(contenu, str):
            # Pour une chaîne de caractères
            github_content = contenu.encode('utf-8')

        elif isinstance(contenu, bytes):
            # Pour des données binaires
            github_content = contenu

        elif isinstance(contenu, BytesIO):
            # Pour un BytesIO
            contenu.seek(0)
            github_content = contenu.read()

        else:
            st.error(f"Type de contenu non pris en charge: {type(contenu)}")
            return False

        # Initialiser le client GitHub
        g = Github(token)
        repo = g.get_repo(repo_name)

        try:
            # Vérifier si le fichier existe déjà
            contents = repo.get_contents(nom_fichier, ref=branche)
            # Mettre à jour le fichier existant
            repo.update_file(
                path=contents.path,
                message=message_commit,
                content=github_content,
                sha=contents.sha,
                branch=branche
            )
        except GithubException as e:
            if e.status == 404:
                # Si le fichier n'existe pas, le créer
                repo.create_file(
                    path=nom_fichier,
                    message=message_commit,
                    content=github_content,
                    branch=branche
                )
            else:
                raise e

        # Invalider le cache pour forcer un rechargement des données
        if 'charger_donnees' in globals() and hasattr(charger_donnees, 'clear'):
            charger_donnees.clear()

        st.success(f"✅ Fichier {nom_fichier} sauvegardé sur GitHub")
        return True

    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde sur GitHub: {e}")
        import traceback
        st.error(traceback.format_exc())
        return False


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


def get_graphhopper_route(start_coords, end_coords, type_deplacement="Marche"):
    """
    Calcule un itinéraire en utilisant l'API GraphHopper.

    Args:
        start_coords: Tuple (latitude, longitude) du point de départ
        end_coords: Tuple (latitude, longitude) du point d'arrivée
        type_deplacement: Type de déplacement ('Marche' ou 'Voiture')

    Returns:
        Un tuple (distance_km, duration_hours, coords_json) ou (None, None, None) en cas d'erreur
    """
    import requests
    import json

    # Vérifier que les coordonnées sont valides
    if None in (start_coords[0], start_coords[1], end_coords[0], end_coords[1]):
        print("Coordonnées invalides, impossible de calculer l'itinéraire.")
        return None, None, None

    # Déterminer le profil GraphHopper en fonction du type de déplacement
    if not isinstance(type_deplacement, str):
        print(f"Type de déplacement invalide: {type_deplacement} (type: {type(type_deplacement)})")
        return None, None, None

    if type_deplacement == "Marche":
        profile = "foot"  # Utiliser "foot" au lieu de "hike" car "hike" n'est pas standard
    elif type_deplacement == "Voiture":
        profile = "car"
    else:
        print(f"Type de déplacement non reconnu: {type_deplacement}")
        return None, None, None

    # Ta clé API GraphHopper
    api_key = st.secrets["graphhopper"]["token"]

    # Construire l'URL de l'API GraphHopper
    base_url = "https://graphhopper.com/api/1/route"

    # Formatage correct des paramètres selon la documentation
    params = {
        "key": api_key,
        "profile": profile,  # Utiliser "profile" au lieu de "vehicle"
        "points_encoded": "false",
        "instructions": "false",
        "calc_points": "true",
        "locale": "fr"
    }

    # Ajouter les points de manière correcte (séparément pour chaque point)
    params["point"] = [
        f"{start_coords[0]},{start_coords[1]}",
        f"{end_coords[0]},{end_coords[1]}"
    ]

    try:
        response = requests.get(base_url, params=params)

        # Imprimer l'URL complète pour le débogage
        print(f"URL de la requête: {response.url}")

        response.raise_for_status()  # Lève une exception si le statut n'est pas 2xx

        data = response.json()

        if "paths" in data and len(data["paths"]) > 0:
            path = data["paths"][0]

            # Extraire les informations pertinentes
            distance_km = path["distance"] / 1000  # Conversion en km
            duration_hours = path["time"] / 3600000  # Conversion de ms en heures

            # Extraire les coordonnées du chemin
            route_coords = []
            for point in path["points"]["coordinates"]:
                # GraphHopper retourne les coordonnées dans l'ordre [longitude, latitude, élévation]
                # Nous voulons [latitude, longitude] pour être compatible avec le reste du code
                route_coords.append([point[1], point[0]])

            # Convertir en JSON pour stockage
            route_coords_json = json.dumps(route_coords)

            return distance_km, duration_hours, route_coords_json
        else:
            print("Aucun itinéraire trouvé dans la réponse GraphHopper")
            return None, None, None

    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la requête GraphHopper: {e}")
        print(f"Réponse: {response.text if 'response' in locals() else 'N/A'}")
        return None, None, None
    except (KeyError, IndexError, ValueError) as e:
        print(f"Erreur lors du traitement de la réponse GraphHopper: {e}")
        return None, None, None


def calculate_routes_graphhopper(df):
    """Calcule les distances, durées et les trajets avec GraphHopper si non enregistrés."""


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
                        distance, duration, route_coords = get_graphhopper_route(start_coords, end_coords,
                                                                                 type_deplacement)
                        # Mettre en cache
                        routes_cache[route_key] = (distance, duration, route_coords)
                except Exception as e:
                    print(f"Erreur lors de la lecture du chemin à l'index {i}: {e}")
                    start_coords = (lat1, lon1)
                    end_coords = (lat2, lon2)
                    distance, duration, route_coords = get_graphhopper_route(start_coords, end_coords, type_deplacement)
                    # Mettre en cache
                    routes_cache[route_key] = (distance, duration, route_coords)
            else:
                # Sinon on calcule un nouveau tracé
                start_coords = (lat1, lon1)
                end_coords = (lat2, lon2)
                distance, duration, route_coords = get_graphhopper_route(start_coords, end_coords, type_deplacement)
                # Mettre en cache
                routes_cache[route_key] = (distance, duration, route_coords)
        else:
            # Coordonnées invalides ou type de déplacement non défini
            if not valid_coords:
                print(f"Coordonnées manquantes pour le segment {i} à {i + 1}, impossible de calculer l'itinéraire.")
            else:
                print(
                    f"Type de déplacement non défini pour le segment {i} à {i + 1}, impossible de calculer l'itinéraire.")
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

@st.cache_data()
def identifier_sejours_multiples(df):
    """Identifie les séjours multiples au même endroit et met à jour les durées"""
    # Créer une copie pour éviter de modifier le DataFrame original
    df_avec_duree = df.copy()

    # Initialiser les colonnes pour la durée du séjour et la date de fin
    df_avec_duree['Duree_Sejour'] = 1
    df_avec_duree['Date_Fin'] = None

    # Première passe pour identifier les groupes de séjour
    groupes_sejour = []
    groupe_actuel = [0]  # Commencer avec la première ligne

    for i in range(1, len(df_avec_duree)):
        # Comparer avec le dernier élément du groupe actuel
        dernier_index = groupe_actuel[-1]

        # Vérifier si l'adresse actuelle est la même que celle du dernier élément du groupe
        meme_adresse = df_avec_duree.iloc[dernier_index]['Adresse'] == df_avec_duree.iloc[i]['Adresse']
        memes_coords = (df_avec_duree.iloc[dernier_index]['Latitude'] == df_avec_duree.iloc[i]['Latitude'] and
                        df_avec_duree.iloc[dernier_index]['Longitude'] == df_avec_duree.iloc[i]['Longitude'])

        if meme_adresse or memes_coords:
            # Même endroit, ajouter à ce groupe
            groupe_actuel.append(i)
        else:
            # Nouvel endroit, terminer le groupe actuel et en coammencer un nouveau
            groupes_sejour.append(groupe_actuel)
            groupe_actuel = [i]

    # Ajouter le dernier groupe
    groupes_sejour.append(groupe_actuel)

    # Deuxième passe pour mettre à jour les durées et dates
    for groupe in groupes_sejour:
        if len(groupe) > 1:  # Séjour multiple
            premier_index = groupe[0]
            dernier_index = groupe[-1]

            # Mettre à jour le premier élément du groupe
            df_avec_duree.at[premier_index, 'Duree_Sejour'] = len(groupe)
            df_avec_duree.at[premier_index, 'Date_Fin'] = df_avec_duree.iloc[dernier_index]['Nuit']

            # Marquer les autres éléments du groupe comme à fusionner
            for i in groupe[1:]:
                df_avec_duree.at[i, 'Duree_Sejour'] = -1

    return df_avec_duree

@st.cache_data
def charger_routes_existantes(df):
    """
    Charge les routes, distances et durées existantes dans le DataFrame
    sans recalculer les valeurs manquantes.

    Args:
        df: DataFrame avec les données du voyage

    Returns:
        distances, durations, routes, df
    """
    import json
    import pandas as pd

    # Créer une copie du DataFrame pour éviter de modifier l'original
    df = df.copy()

    # Initialiser les listes pour stocker les résultats
    distances = []
    durations = []
    routes = []

    # Parcourir le DataFrame pour extraire les informations existantes
    for i in range(len(df) - 1):  # On parcourt jusqu'à l'avant-dernier point
        # Récupérer les valeurs existantes
        distance = df.iloc[i]["Distance (km)"] if "Distance (km)" in df.columns else None
        duration = df.iloc[i]["Durée (h)"] if "Durée (h)" in df.columns else None

        # Récupérer les coordonnées du chemin
        route_coords = df.iloc[i]["Chemin"] if "Chemin" in df.columns else None

        # Convertir les coordonnées JSON en liste si nécessaire
        if isinstance(route_coords, str) and route_coords:
            try:
                route_coords = json.loads(route_coords)
            except json.JSONDecodeError:
                route_coords = []

        # Ajouter aux listes
        distances.append(distance)
        durations.append(duration)
        routes.append(route_coords if isinstance(route_coords, list) else route_coords)

    # Ajouter une dernière valeur pour correspondre à la taille du DataFrame
    distances.append(None)
    durations.append(None)
    routes.append([])

    return distances, durations, routes, df


def ouvrir_pdf(chemin_pdf, use_expander = False):

    """
    Affiche un PDF en utilisant streamlit-pdf-viewer

    Args:
        chemin_pdf: Chemin du fichier PDF dans le dépôt GitHub
    """
    import os

    # Charger le fichier PDF depuis GitHub en utilisant votre fonction existante
    contenu_pdf = charger_donnees(nom_fichier=chemin_pdf, format="binary")

    if not contenu_pdf:
        st.error(f"Impossible de charger le fichier PDF: {chemin_pdf}")
        return

    # Récupérer les données binaires du PDF
    if hasattr(contenu_pdf, 'read'):
        contenu_pdf.seek(0)
        pdf_data = contenu_pdf.read()
    else:
        pdf_data = contenu_pdf

    # Afficher le PDF avec streamlit-pdf-viewer
    pdf_viewer(
        input=pdf_data,  # Données binaires du PDF
        width="100%",    # Utiliser toute la largeur disponible
        render_text=True, # Activer la sélection de texte
    )
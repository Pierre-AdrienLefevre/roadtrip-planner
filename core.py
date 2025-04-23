from opencage.geocoder import OpenCageGeocode
import polyline
import requests
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

    return distances, route_geoms, df


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
            # Nouvel endroit, terminer le groupe actuel et en commencer un nouveau
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
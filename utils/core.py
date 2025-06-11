import base64
import json
from io import BytesIO

import pandas as pd
import streamlit as st
from github import Github, GithubException
from streamlit_pdf_viewer import pdf_viewer


def appliquer_types_colonnes(df):
    """
    Applique les bons types de données aux colonnes du DataFrame
    """
    try:
        # Conversion de la colonne Nuit en datetime
        if "Nuit" in df.columns:
            df["Nuit"] = pd.to_datetime(df["Nuit"], errors="coerce")

        # Colonnes texte
        colonnes_texte = ["Ville", "Nom", "Adresse", "Lien", "Type_Hebergement", "Type_Deplacement"]
        for col in colonnes_texte:
            if col in df.columns:
                df[col] = df[col].astype("string")

        # Colonnes numériques
        if "Prix" in df.columns:
            df["Prix"] = pd.to_numeric(df["Prix"], errors="coerce")

        if "Longitude" in df.columns:
            df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

        if "Latitude" in df.columns:
            df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")

        if "Distance (km)" in df.columns:
            df["Distance (km)"] = pd.to_numeric(df["Distance (km)"], errors="coerce")

        if "Durée (h)" in df.columns:
            df["Durée (h)"] = pd.to_numeric(df["Durée (h)"], errors="coerce")

        # Colonne booléenne
        if "Afficher PDF" in df.columns:
            df["Afficher PDF"] = df["Afficher PDF"].astype("bool")

        # La colonne 'Chemin' reste en object (contient du JSON)

    except Exception as e:
        st.warning(f"Erreur lors de l'application des types de colonnes: {e}")

    return df


@st.cache_data
def charger_donnees(nom_fichier="data/hebergements_chemins.csv", format=None, branche="main"):
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
            if format == "csv" or nom_fichier.endswith(".csv"):
                df = pd.read_csv(buffer)
                # Appliquer les bons types de colonnes
                df = appliquer_types_colonnes(df)
                return df
            elif format == "parquet" or nom_fichier.endswith(".parquet"):
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
            if nom_fichier.endswith(".parquet"):
                contenu.to_parquet(buffer, index=False)
            elif nom_fichier.endswith(".csv"):
                contenu.to_csv(buffer, index=False)
            else:
                # CSV par défaut (changement principal ici)
                contenu.to_csv(buffer, index=False)
            buffer.seek(0)
            github_content = buffer.read()

        elif isinstance(contenu, dict) or isinstance(contenu, list):
            # Pour un dictionnaire ou une liste (format JSON)
            github_content = json.dumps(contenu).encode("utf-8")

        elif isinstance(contenu, str):
            # Pour une chaîne de caractères
            github_content = contenu.encode("utf-8")

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
                path=contents.path, message=message_commit, content=github_content, sha=contents.sha, branch=branche
            )
        except GithubException as e:
            if e.status == 404:
                # Si le fichier n'existe pas, le créer
                repo.create_file(path=nom_fichier, message=message_commit, content=github_content, branch=branche)
            else:
                raise e

        # Invalider le cache pour forcer un rechargement des données
        if "charger_donnees" in globals() and hasattr(charger_donnees, "clear"):
            charger_donnees.clear()

        st.success(f"✅ Fichier {nom_fichier} sauvegardé sur GitHub")
        return True

    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde sur GitHub: {e}")
        import traceback

        st.error(traceback.format_exc())
        return False


@st.cache_data()
def identifier_sejours_multiples(df):
    """Identifie les séjours multiples au même endroit et met à jour les durées"""
    # Créer une copie pour éviter de modifier le DataFrame original
    df_avec_duree = df.copy()

    # Initialiser les colonnes pour la durée du séjour et la date de fin
    df_avec_duree["Duree_Sejour"] = 1
    df_avec_duree["Date_Fin"] = None

    # Première passe pour identifier les groupes de séjour
    groupes_sejour = []
    groupe_actuel = [0]  # Commencer avec la première ligne

    for i in range(1, len(df_avec_duree)):
        # Comparer avec le dernier élément du groupe actuel
        dernier_index = groupe_actuel[-1]

        # Vérifier si l'adresse actuelle est la même
        # que celle du dernier élément du groupe
        meme_adresse = df_avec_duree.iloc[dernier_index]["Adresse"] == df_avec_duree.iloc[i]["Adresse"]
        memes_coords = (
            df_avec_duree.iloc[dernier_index]["Latitude"] == df_avec_duree.iloc[i]["Latitude"]
            and df_avec_duree.iloc[dernier_index]["Longitude"] == df_avec_duree.iloc[i]["Longitude"]
        )

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
            df_avec_duree.at[premier_index, "Duree_Sejour"] = len(groupe)
            df_avec_duree.at[premier_index, "Date_Fin"] = df_avec_duree.iloc[dernier_index]["Nuit"]

            # Marquer les autres éléments du groupe comme à fusionner
            for i in groupe[1:]:
                df_avec_duree.at[i, "Duree_Sejour"] = -1

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


def ouvrir_pdf(chemin_pdf, use_expander=False):
    """
    Affiche un PDF en utilisant streamlit-pdf-viewer

    Args:
        chemin_pdf: Chemin du fichier PDF dans le dépôt GitHub
    """

    # Charger le fichier PDF depuis GitHub en utilisant votre fonction existante
    contenu_pdf = charger_donnees(nom_fichier=chemin_pdf, format="binary")

    if not contenu_pdf:
        st.error(f"Impossible de charger le fichier PDF: {chemin_pdf}")
        return

    # Récupérer les données binaires du PDF
    if hasattr(contenu_pdf, "read"):
        contenu_pdf.seek(0)
        pdf_data = contenu_pdf.read()
    else:
        pdf_data = contenu_pdf

    # Afficher le PDF avec streamlit-pdf-viewer
    pdf_viewer(
        input=pdf_data,  # Données binaires du PDF
        width="100%",  # Utiliser toute la largeur disponible
        render_text=True,  # Activer la sélection de texte
    )

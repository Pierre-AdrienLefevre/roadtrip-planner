import streamlit as st
import pandas as pd
import folium
import json
from streamlit_folium import st_folium
from folium.plugins import MiniMap
from core import calculate_routes_osrm, charger_donnees, sauvegarder_donnees
from datetime import datetime

st.set_page_config(layout="wide")
st.title("🗺️ Carte interactive du Roadtrip 🚗")

# Charger le fichier parquet
uploaded_file = 'data/hebergements_chemins.parquet'
df = charger_donnees(nom_fichier=uploaded_file, format="parquet")

# Calculer les distances et les trajets
distances, routes, df = calculate_routes_osrm(df)


def identifier_sejours_multiples(df):
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


# Identifier les séjours multiples
df_avec_duree = identifier_sejours_multiples(df)

# **Création de la carte Folium avec style amélioré**
start_lat = df.iloc[0]["Latitude"]
start_lon = df.iloc[0]["Longitude"]

# Créer une carte avec un thème moderne
m = folium.Map(
    location=[start_lat, start_lon],
    zoom_start=6,
    tiles="CartoDB positron",
    attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    width="100%",
    height="100%"
)


# Fonction pour formater l'affichage de la durée du séjour
def formater_date_sejour(row):
    date_debut = row["Nuit"] if "Nuit" in row and pd.notna(row["Nuit"]) else ""
    date_fin = row["Date_Fin"] if "Date_Fin" in row and pd.notna(row["Date_Fin"]) else ""
    duree = row["Duree_Sejour"] if "Duree_Sejour" in row else 1

    if duree > 1 and date_debut and date_fin:
        return f"du {date_debut} au {date_fin} ({duree} nuits)"
    else:
        return f"{date_debut}"


# Ajouter les tracés des routes entre chaque point
for i in range(len(df) - 1):
    if pd.notna(df.iloc[i]["Chemin"]):
        route_coords = json.loads(df.iloc[i]["Chemin"])
        if route_coords:
            # Calculer la distance
            distance_text = ""
            if "Distance (km)" in df.columns and pd.notna(df.iloc[i]["Distance (km)"]):
                distance_text = f"{df.iloc[i]['Distance (km)']} km"
            elif i < len(distances) and pd.notna(distances[i]):
                distance_text = f"{round(distances[i] / 1000, 1)} km"

            # Tracer la route
            route = folium.PolyLine(
                locations=route_coords,
                color="#4169E1",  # Bleu royal
                weight=4,
                opacity=0.8,
                tooltip=f"Distance: {distance_text}"
            )
            route.add_to(m)

# Créer des icônes personnalisées
etape_icon = folium.Icon(
    color="blue",
    icon="bed",
    prefix="fa"
)

depart_icon = folium.Icon(
    color="red",
    icon="play",
    prefix="fa"
)

arrivee_icon = folium.Icon(
    color="green",
    icon="flag-checkered",
    prefix="fa"
)

sejour_icon = folium.Icon(
    color="purple",
    icon="home",
    prefix="fa"
)

# Parcourir le DataFrame traité pour afficher les marqueurs
for i, row in df_avec_duree.iterrows():
    # Ignorer les lignes qui ont été fusionnées avec une étape précédente
    if row["Duree_Sejour"] == -1:
        continue

    # Déterminer le type de point
    if i == 0:
        point_type = "départ"
    elif i == len(df) - 1 or row["Adresse"] == df.iloc[-1]["Adresse"]:
        point_type = "arrivée"
    else:
        point_type = "étape" if row["Duree_Sejour"] == 1 else "séjour"

    # Récupérer les informations
    date_info = formater_date_sejour(row)
    ville = row["Ville"] if "Ville" in row and pd.notna(row["Ville"]) else ""
    nom = row["Nom"] if "Nom" in row and pd.notna(row["Nom"]) else ""
    prix = row["Prix"] if "Prix" in row and pd.notna(row["Prix"]) else ""
    type_heb = row["Type"] if "Type" in row and pd.notna(row["Type"]) else ""

    # Déterminer l'icône à utiliser
    if point_type == "départ":
        icon = depart_icon
        title = "Point de départ"
        color = "#DC143C"  # Rouge
    elif point_type == "arrivée":
        icon = arrivee_icon
        title = "Point d'arrivée"
        color = "#228B22"  # Vert
    elif point_type == "séjour":
        icon = sejour_icon
        title = f"Séjour de {row['Duree_Sejour']} nuits"
        color = "#800080"  # Violet
    else:
        icon = etape_icon
        title = f"Étape {i}"
        color = "#1E90FF"  # Bleu

    # Créer le contenu de la popup
    html_content = f"""
    <div style="min-width: 180px;">
        <h4 style="color: {color}; margin-bottom: 5px;">{title}</h4>
        <strong>{ville}</strong><br>
        <em>{date_info}</em><br>
        <strong>Hébergement:</strong> {nom}<br>
        <strong>Type:</strong> {type_heb}<br>
        <strong>Prix:</strong> {prix}
    </div>
    """

    # Créer le texte du tooltip
    if point_type == "départ":
        tooltip_text = f"Départ: {ville} ({date_info})"
    elif point_type == "arrivée":
        tooltip_text = f"Arrivée: {ville} ({date_info})"
    elif point_type == "séjour":
        tooltip_text = f"{ville} - Séjour de {row['Duree_Sejour']} nuits ({date_info})"
    else:
        tooltip_text = f"{ville} ({date_info})"

    # Ajouter le marqueur
    folium.Marker(
        location=[row["Latitude"], row["Longitude"]],
        popup=folium.Popup(html_content, max_width=300),
        tooltip=tooltip_text,
        icon=icon
    ).add_to(m)

# Ajouter une mini-carte
folium.plugins.MiniMap().add_to(m)

# Afficher la carte
st_folium(m, width=None, height=700)


df = charger_donnees(nom_fichier=uploaded_file, format="parquet")

# Définir les colonnes à cacher
colonnes_cachees = ['Chemin', 'Longitude', 'Latitude', 'Type']
df_visible = df.drop(columns=colonnes_cachees, errors="ignore")

# Sauvegarde d'une copie des adresses actuelles pour détecter les changements
adresses_actuelles = df_visible["Adresse"].copy() if "Adresse" in df_visible.columns else pd.Series([])

# Édition interactive du tableau
edited_df = st.data_editor(df_visible,
                           num_rows="dynamic",
                           use_container_width=True,
                           height=800,
                           hide_index=True,
                           )

# Afficher le budget total
total_budget = edited_df["Prix"].sum(skipna=True)
st.sidebar.subheader("💰 Récapitulatif budget et distance")
st.sidebar.write(f"**Budget total pour les hébergements :** {total_budget:.2f} $")

# Calculer et afficher la distance totale
distance_totale = df["Distance (km)"].sum(skipna=True)
st.sidebar.write(f"**Distance totale :** {distance_totale:.2f} km")

# Bouton pour appliquer les modifications et recalculer les distances
if st.sidebar.button("🔄 Appliquer les modifications"):
    # Trouver les lignes modifiées
    modifications = edited_df.compare(df_visible)

    if not modifications.empty:
        indices_modifiés = modifications.index.tolist()

        # Identifier spécifiquement les modifications d'adresses
        adresses_modifiées = set()
        if "Adresse" in edited_df.columns and "Adresse" in df_visible.columns:
            for idx in indices_modifiés:
                if idx < len(adresses_actuelles) and idx < len(edited_df):
                    if edited_df.loc[idx, "Adresse"] != adresses_actuelles.loc[idx]:
                        adresses_modifiées.add(idx)

        # Mettre à jour les valeurs modifiées dans le DataFrame complet
        for idx in indices_modifiés:
            for col in edited_df.columns:
                df.loc[idx, col] = edited_df.loc[idx, col]

        # Réinitialiser les coordonnées et chemins pour les adresses modifiées
        for idx in adresses_modifiées:
            # Réinitialiser les colonnes géographiques
            df.loc[idx, "Latitude"] = None
            df.loc[idx, "Longitude"] = None
            df.loc[idx, "Chemin"] = None
            df.loc[idx, "Distance (km)"] = None

            # Réinitialiser aussi le chemin précédent si ce n'est pas la première ligne
            if idx > 0:
                df.loc[idx - 1, "Chemin"] = None
                df.loc[idx - 1, "Distance (km)"] = None

        # Recalculer les routes et distances pour tout le DataFrame
        # Cela permettra de recalculer automatiquement les coordonnées manquantes
        with st.spinner("Recalcul des itinéraires et des distances..."):
            distances_list, route_geoms, df_updated = calculate_routes_osrm(df)

            # Mettre à jour le DataFrame avec les résultats recalculés
            df = df_updated

            # Sauvegarder le DataFrame mis à jour
            sauvegarder_donnees(df, nom_fichier=uploaded_file)

        # Calculer la distance totale mise à jour
        distance_totale_maj = df["Distance (km)"].sum(skipna=True)

        st.success("✅ Modifications appliquées et distances recalculées !")
        st.sidebar.write(f"**Distance totale mise à jour :** {distance_totale_maj:.2f} km")

        # Recharger la page pour refléter les changements
        st.rerun()
    else:
        st.info("Aucune modification détectée.")
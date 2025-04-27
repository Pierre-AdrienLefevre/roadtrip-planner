import json

import folium
import pandas as pd
import streamlit as st


def formater_date_sejour(row):
    """Formate l'affichage de la durée du séjour"""
    # Conversion des objets Timestamp en chaînes de caractères (date uniquement)
    if "Nuit" in row and pd.notna(row["Nuit"]):
        # Si c'est un Timestamp, le convertir en chaîne au format YYYY-MM-DD
        if isinstance(row["Nuit"], pd.Timestamp):
            date_debut = row["Nuit"].strftime("%Y-%m-%d")
        else:
            # Si c'est déjà une chaîne, prendre juste la partie date
            date_debut = str(row["Nuit"]).split()[0]
    else:
        date_debut = ""

    if "Date_Fin" in row and pd.notna(row["Date_Fin"]):
        if isinstance(row["Date_Fin"], pd.Timestamp):
            date_fin = row["Date_Fin"].strftime("%Y-%m-%d")
        else:
            date_fin = str(row["Date_Fin"]).split()[0]
    else:
        date_fin = ""

    duree = row["Duree_Sejour"] if "Duree_Sejour" in row else 1

    if duree > 1 and date_debut and date_fin:
        return f"du {date_debut} au {date_fin} ({duree} nuits)"
    else:
        return f"{date_debut}"


def creer_icones():
    """Crée et retourne les icônes pour les différents types de points sur la carte"""
    # Icônes de base
    icons = {
        "depart": folium.Icon(color="red", icon="play", prefix="fa"),
        "arrivee": folium.Icon(color="green", icon="flag-checkered", prefix="fa"),
        "activite": folium.Icon(color="orange", icon="car", prefix="fa"),
    }

    # Icônes pour les types d'hébergement avec couleurs selon le nombre de nuits
    # Pour 1 nuit
    icons["hotel_1"] = folium.Icon(color="lightblue", icon="bed", prefix="fa")
    icons["camping_1"] = folium.Icon(color="lightblue", icon="campground", prefix="fa")

    # Pour 2 nuits
    icons["hotel_2"] = folium.Icon(color="blue", icon="bed", prefix="fa")
    icons["camping_2"] = folium.Icon(color="blue", icon="campground", prefix="fa")

    # Pour 3 nuits
    icons["hotel_3"] = folium.Icon(color="cadetblue", icon="bed", prefix="fa")
    icons["camping_3"] = folium.Icon(color="cadetblue", icon="campground", prefix="fa")

    # Pour 4 nuits ou plus
    icons["hotel_4"] = folium.Icon(color="darkblue", icon="bed", prefix="fa")
    icons["camping_4"] = folium.Icon(color="darkblue", icon="campground", prefix="fa")

    # Pour les cas non spécifiés (durée par défaut = 1)
    icons["sejour_1"] = folium.Icon(color="lightblue", icon="bed", prefix="fa")
    icons["sejour_2"] = folium.Icon(color="blue", icon="bed", prefix="fa")
    icons["sejour_3"] = folium.Icon(color="cadetblue", icon="bed", prefix="fa")
    icons["sejour_4"] = folium.Icon(color="darkblue", icon="bed", prefix="fa")

    # Couleurs pour les popups selon le nombre de nuits (une couleur par durée)
    colors = {
        "départ": "#DC143C",  # Rouge
        "arrivée": "#228B22",  # Vert
        "activité": "#FFA500",  # Orange pour les activités
        "séjour_1": "#87CEFA",  # Bleu clair (1 nuit)
        "séjour_2": "#1E90FF",  # Bleu (2 nuits)
        "séjour_3": "#4682B4",  # Bleu acier (3 nuits)
        "séjour_4": "#0000CD",  # Bleu foncé (4 nuits)
    }

    return icons, colors


def initialiser_carte(start_lat, start_lon):
    """Initialise la carte Folium avec les couches de base Mapbox"""
    # Créer une carte sans tuile de base pour pouvoir alterner entre les vues
    m = folium.Map(
        location=[start_lat, start_lon],
        zoom_start=6,
        tiles=None,
        width="100%",
        height="100%",
    )

    mapbox_token = st.secrets["mapbox"]["token"]

    # Ajouter la couche satellite Mapbox
    folium.TileLayer(
        tiles=f"https://api.mapbox.com/styles/v1/mapbox/satellite-streets-v12/tiles/{{z}}/{{x}}/{{y}}?access_token={mapbox_token}",
        name="Satellite",
        attr="© Mapbox © OpenStreetMap",
    ).add_to(m)

    # Ajouter la couche outdoors Mapbox
    folium.TileLayer(
        tiles=f"https://api.mapbox.com/styles/v1/mapbox/outdoors-v12/tiles/{{z}}/{{x}}/{{y}}?access_token={mapbox_token}",
        name="Carte Outdoor",
        attr="© Mapbox © OpenStreetMap",
    ).add_to(m)

    return m


def ajouter_routes(m, df, distances=None, durations=None):
    """Ajoute les routes entre les points sur la carte"""
    for i in range(len(df) - 1):
        if pd.notna(df.iloc[i]["Chemin"]):
            route_coords = json.loads(df.iloc[i]["Chemin"])
            if route_coords:
                # Déterminer si c'est un déplacement à pied
                is_marche = False
                if "Type_Deplacement" in df.columns and pd.notna(
                    df.iloc[i]["Type_Deplacement"]
                ):
                    is_marche = df.iloc[i]["Type_Deplacement"].lower() == "marche"

                # Calculer la distance et la durée
                distance_text = ""
                duration_text = ""
                if "Distance (km)" in df.columns and pd.notna(
                    df.iloc[i]["Distance (km)"]
                ):
                    distance_text = f"{df.iloc[i]['Distance (km)']:.2f} km"
                elif (
                    distances is not None
                    and i < len(distances)
                    and pd.notna(distances[i])
                ):
                    distance_text = f"{(distances[i] / 1000):.2f} km"

                if "Durée (h)" in df.columns and pd.notna(df.iloc[i]["Durée (h)"]):
                    # Convertir la durée en heures:minutes
                    duree_heures = df.iloc[i]["Durée (h)"]
                    heures = int(duree_heures)
                    minutes = int((duree_heures - heures) * 60)
                    duration_text = f"{heures}h{minutes:02d}"
                elif (
                    durations is not None
                    and i < len(durations)
                    and pd.notna(durations[i])
                ):
                    duree_heures = durations[i]
                    heures = int(duree_heures)
                    minutes = int((duree_heures - heures) * 60)
                    duration_text = f"{heures}h{minutes:02d}"

                # Tracer la route avec distance et durée
                tooltip = f"Distance: {distance_text}"
                if duration_text:
                    tooltip += f" - Durée: {duration_text}"

                # Définir le style de ligne selon le type de déplacement
                dash_array = "10, 10" if is_marche else None

                # Tracer la route
                route = folium.PolyLine(
                    locations=route_coords,
                    color="#4169E1",  # Bleu royal
                    weight=4,
                    opacity=0.8,
                    tooltip=tooltip,
                    dash_array=dash_array,  # Ligne pointillée pour la marche
                )
                route.add_to(m)

    return m


def determiner_type_point(i, row, df, icons, colors, duree_sejour, type_hebergement):
    """Détermine le type de point et ses caractéristiques pour le marqueur"""
    if i == 0:
        point_type = "départ"
        icon = icons["depart"]
        title = "Point de départ"
        color = colors["départ"]
    elif i == len(df) - 1 or (
        row["Adresse"] == df.iloc[-1]["Adresse"] if "Adresse" in row else False
    ):
        point_type = "arrivée"
        icon = icons["arrivee"]
        title = "Point d'arrivée"
        color = colors["arrivée"]
    # Traitement pour les activités basé sur Type_Hebergement
    elif (
        type_hebergement.lower() == "activité" or type_hebergement.lower() == "activite"
    ):
        point_type = "activité"
        icon = icons["activite"]
        title = "Point d'activité"
        color = colors["activité"]
    # Traitement pour le passage (ne pas afficher)
    elif type_hebergement.lower() == "passage":
        return None  # Indique qu'on doit ignorer ce point
    else:
        # Déterminer la catégorie de séjour en fonction de la durée
        if duree_sejour == 1:
            sejour_category = "1"
            point_type = "séjour_1"
        elif duree_sejour == 2:
            sejour_category = "2"
            point_type = "séjour_2"
        elif duree_sejour == 3:
            sejour_category = "3"
            point_type = "séjour_3"
        elif duree_sejour >= 4:
            sejour_category = "4"
            point_type = "séjour_4"
        else:
            # Valeur par défaut si la durée n'est pas spécifiée
            sejour_category = "1"
            point_type = "séjour_1"

        # Déterminer l'icône en fonction du type d'hébergement ET de la durée
        if "hôtel" in type_hebergement.lower():
            icon = icons[f"hotel_{sejour_category}"]
            title = f"Hôtel ({duree_sejour} nuits)"
        elif "camping" in type_hebergement.lower():
            icon = icons[f"camping_{sejour_category}"]
            title = f"Camping ({duree_sejour} nuits)"
        else:
            # Type d'hébergement non spécifié, on utilise l'icône de séjour générique
            icon = icons[f"sejour_{sejour_category}"]
            title = f"Séjour de {duree_sejour} nuits"

        # La couleur est déterminée uniquement par la durée du séjour
        color = colors[point_type]

    return {"point_type": point_type, "icon": icon, "title": title, "color": color}


def creer_html_popup(ville, date_info, nom, type_heb, prix, title, color):
    """Crée le contenu HTML de la popup pour un marqueur"""
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
    return html_content


def creer_tooltip(point_type, ville, date_info, type_hebergement, duree_sejour):
    """Crée le texte du tooltip pour un marqueur"""
    if point_type == "départ":
        return f"Départ: {ville} ({date_info})"
    elif point_type == "arrivée":
        return f"Arrivée: {ville} ({date_info})"
    elif point_type == "activité":
        return f"{ville} - Activité/Parking ({date_info})"
    elif "camping" in type_hebergement.lower():
        return f"{ville} - Camping ({date_info})"
    elif "hôtel" in type_hebergement.lower():
        return f"{ville} - Hôtel ({date_info})"
    else:
        return f"{ville} - Séjour de {duree_sejour} nuits ({date_info})"


def ajouter_marqueurs(m, df_avec_duree, df, icons, colors):
    """Ajoute les marqueurs sur la carte"""
    for i, row in df_avec_duree.iterrows():
        # Ignorer les lignes qui ont été fusionnées avec une étape précédente
        if row["Duree_Sejour"] == -1:
            continue

        # Déterminer le type d'hébergement et le nombre de nuits
        duree_sejour = (
            row["Duree_Sejour"]
            if "Duree_Sejour" in row and pd.notna(row["Duree_Sejour"])
            else 0
        )
        type_hebergement = (
            row["Type_Hebergement"]
            if "Type_Hebergement" in row and pd.notna(row["Type_Hebergement"])
            else ""
        )

        # Déterminer le type de point et ses caractéristiques
        point_info = determiner_type_point(
            i, row, df, icons, colors, duree_sejour, type_hebergement
        )

        # Si point_info est None, c'est un point de passage à ignorer
        if point_info is None:
            continue

        # Récupérer les informations
        date_info = formater_date_sejour(row)
        ville = row["Ville"] if "Ville" in row and pd.notna(row["Ville"]) else ""
        nom = row["Nom"] if "Nom" in row and pd.notna(row["Nom"]) else ""
        prix = row["Prix"] if "Prix" in row and pd.notna(row["Prix"]) else ""
        type_heb = row["Type"] if "Type" in row and pd.notna(row["Type"]) else ""

        # Créer le contenu de la popup
        html_content = creer_html_popup(
            ville,
            date_info,
            nom,
            type_heb,
            prix,
            point_info["title"],
            point_info["color"],
        )

        # Créer le texte du tooltip
        tooltip_text = creer_tooltip(
            point_info["point_type"], ville, date_info, type_hebergement, duree_sejour
        )

        # Ajouter le marqueur
        folium.Marker(
            location=[row["Latitude"], row["Longitude"]],
            popup=folium.Popup(html_content, max_width=300),
            tooltip=tooltip_text,
            icon=point_info["icon"],
        ).add_to(m)

    return m


def creer_carte(df, df_avec_duree, distances=None, durations=None):
    """Crée et configure la carte Folium avec les routes et marqueurs"""
    # Initialiser la carte
    start_lat = df.iloc[0]["Latitude"]
    start_lon = df.iloc[0]["Longitude"]
    m = initialiser_carte(start_lat, start_lon)

    # Ajouter les tracés des routes
    m = ajouter_routes(m, df, distances, durations)

    # Obtenir les icônes
    icons, colors = creer_icones()

    # Ajouter les marqueurs
    m = ajouter_marqueurs(m, df_avec_duree, df, icons, colors)

    # Ajouter le contrôle des couches pour basculer entre carte et satellite
    folium.LayerControl().add_to(m)

    return m

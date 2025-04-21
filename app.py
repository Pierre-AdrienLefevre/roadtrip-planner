import streamlit as st
import pandas as pd
import folium
import json
from streamlit_folium import st_folium
from folium.plugins import MiniMap
from core import (
    charger_donnees,
    sauvegarder_donnees,
    calculate_routes_osrm,
    identifier_sejours_multiples,
    ouvrir_email
)
from dataframe_with_button import editable_dataframe


def configurer_page():
    """Configuration initiale de la page Streamlit"""
    st.set_page_config(layout="wide")
    st.title("🗺️ Carte interactive du Roadtrip 🚗")


def formater_date_sejour(row):
    """Formate l'affichage de la durée du séjour"""
    date_debut = row["Nuit"] if "Nuit" in row and pd.notna(row["Nuit"]) else ""
    date_fin = row["Date_Fin"] if "Date_Fin" in row and pd.notna(row["Date_Fin"]) else ""
    duree = row["Duree_Sejour"] if "Duree_Sejour" in row else 1

    if duree > 1 and date_debut and date_fin:
        return f"du {date_debut} au {date_fin} ({duree} nuits)"
    else:
        return f"{date_debut}"


def creer_icones():
    """Crée et retourne les icônes pour les différents types de points sur la carte"""
    icons = {
        "etape": folium.Icon(color="blue", icon="bed", prefix="fa"),
        "depart": folium.Icon(color="red", icon="play", prefix="fa"),
        "arrivee": folium.Icon(color="green", icon="flag-checkered", prefix="fa"),
        "sejour": folium.Icon(color="purple", icon="home", prefix="fa")
    }

    return icons


def creer_carte(df, df_avec_duree, distances=None):
    """Crée et configure la carte Folium avec les routes et marqueurs"""
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

    # Ajouter les tracés des routes entre chaque point
    for i in range(len(df) - 1):
        if pd.notna(df.iloc[i]["Chemin"]):
            route_coords = json.loads(df.iloc[i]["Chemin"])
            if route_coords:
                # Calculer la distance (limitée à 2 décimales)
                distance_text = ""
                if "Distance (km)" in df.columns and pd.notna(df.iloc[i]["Distance (km)"]):
                    distance_text = f"{df.iloc[i]['Distance (km)']:.2f} km"
                elif distances is not None and i < len(distances) and pd.notna(distances[i]):
                    distance_text = f"{(distances[i] / 1000):.2f} km"

                # Tracer la route
                route = folium.PolyLine(
                    locations=route_coords,
                    color="#4169E1",  # Bleu royal
                    weight=4,
                    opacity=0.8,
                    tooltip=f"Distance: {distance_text}"
                )
                route.add_to(m)

    # Obtenir les icônes
    icons = creer_icones()

    # Couleurs pour les popups
    colors = {
        "départ": "#DC143C",  # Rouge
        "arrivée": "#228B22",  # Vert
        "séjour": "#800080",  # Violet
        "étape": "#1E90FF"  # Bleu
    }

    # Parcourir le DataFrame traité pour afficher les marqueurs
    for i, row in df_avec_duree.iterrows():
        # Ignorer les lignes qui ont été fusionnées avec une étape précédente
        if row["Duree_Sejour"] == -1:
            continue

        # Déterminer le type de point
        if i == 0:
            point_type = "départ"
            icon = icons["depart"]
            title = "Point de départ"
        elif i == len(df) - 1 or row["Adresse"] == df.iloc[-1]["Adresse"]:
            point_type = "arrivée"
            icon = icons["arrivee"]
            title = "Point d'arrivée"
        elif row["Duree_Sejour"] > 1:
            point_type = "séjour"
            icon = icons["sejour"]
            title = f"Séjour de {row['Duree_Sejour']} nuits"
        else:
            point_type = "étape"
            icon = icons["etape"]
            title = f"Étape {i}"

        color = colors[point_type]

        # Récupérer les informations
        date_info = formater_date_sejour(row)
        ville = row["Ville"] if "Ville" in row and pd.notna(row["Ville"]) else ""
        nom = row["Nom"] if "Nom" in row and pd.notna(row["Nom"]) else ""
        prix = row["Prix"] if "Prix" in row and pd.notna(row["Prix"]) else ""
        type_heb = row["Type"] if "Type" in row and pd.notna(row["Type"]) else ""

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

    return m


def afficher_recapitulatif_sidebar(df, distance_totale=None):
    """Affiche le récapitulatif du budget et de la distance dans la sidebar"""
    st.sidebar.subheader("💰 Récapitulatif budget et distance")

    # Afficher le budget total
    total_budget = df["Prix"].sum(skipna=True)
    st.sidebar.write(f"**Budget total pour les hébergements :** {total_budget:.2f} $")

    # Afficher la distance totale
    if distance_totale is None:
        distance_totale = df["Distance (km)"].sum(skipna=True)
    st.sidebar.write(f"**Distance totale :** {distance_totale:.2f} km")


def creer_editeur_donnees(df):
    """Crée un éditeur de données pour modifier les informations du roadtrip"""
    # Initialiser la variable de session pour les emails
    if "email_a_ouvrir" not in st.session_state:
        st.session_state.email_a_ouvrir = None

    # Définir les colonnes à cacher
    colonnes_cachees = ['Chemin', 'Longitude', 'Latitude', 'Type', 'Distance (km)']
    df_visible = df.drop(columns=colonnes_cachees, errors="ignore")

    # Sauvegarde d'une copie des adresses actuelles
    adresses_actuelles = df_visible["Adresse"].copy() if "Adresse" in df_visible.columns else pd.Series([])

    # Configuration des colonnes pour l'éditeur
    column_config = {
        "Adresse": st.column_config.TextColumn("Adresse", width="large"),
        "Ville": st.column_config.TextColumn("Ville", width="medium"),
        "Nom": st.column_config.TextColumn("Hébergement", width="medium"),
        "Prix": st.column_config.NumberColumn("Prix ($)", format="%.2f"),
        "Nuit": st.column_config.DateColumn("Date", width="medium")
    }

    # Édition interactive du tableau
    edited_df = st.data_editor(
        df_visible,
        num_rows="fixed",
        use_container_width=True,
        height=400,  # Hauteur réduite pour faire de la place aux emails en-dessous
        hide_index=True,
        column_config=column_config
    )

    # Section pour les emails en-dessous du tableau d'édition
    if "Lien" in df.columns:
        # Filtrer les lignes qui ont un lien d'email
        emails_df = df[pd.notna(df["Lien"])]

        if not emails_df.empty:
            st.write("### 📧 Emails de confirmation")

            # Créer un conteneur pour les emails
            email_container = st.container()

            # Afficher les liens d'emails sous forme de boutons
            n_cols = 3  # Nombre de boutons par ligne
            emails_rows = [emails_df.iloc[i:i + n_cols] for i in range(0, len(emails_df), n_cols)]

            for row_of_emails in emails_rows:
                cols = st.columns(n_cols)
                for i, (idx, email_row) in enumerate(row_of_emails.iterrows()):
                    if i < len(cols):  # S'assurer que nous avons assez de colonnes
                        nom_hebergement = email_row.get("Nom", f"Hébergement {idx + 1}")
                        ville = email_row.get("Ville", "")
                        button_text = f"📧 {nom_hebergement} ({ville})"

                        if cols[i].button(button_text, key=f"email_btn_{idx}"):
                            st.session_state.email_a_ouvrir = email_row["Lien"]
                            st.rerun()

    # Afficher l'email sélectionné
    if st.session_state.email_a_ouvrir:
        with st.expander("📧 Email de confirmation", expanded=True):
            # Appeler ouvrir_email avec use_expander=False pour éviter l'imbrication d'expanders
            ouvrir_email(st.session_state.email_a_ouvrir, use_expander=False)
            if st.button("Fermer l'email"):
                st.session_state.email_a_ouvrir = None
                st.rerun()

    return edited_df, df_visible, adresses_actuelles


def traiter_modifications(edited_df, df_visible, df, adresses_actuelles, uploaded_file):
    """Traite les modifications apportées aux données et recalcule les distances si nécessaire"""
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


def main():
    """Fonction principale qui gère l'application Streamlit"""

    # Configuration de la page
    configurer_page()

    # Charger le fichier parquet
    uploaded_file = 'data/hebergements_chemins.parquet'
    df = charger_donnees(nom_fichier=uploaded_file, format="parquet")

    # Onglets pour différentes sections de l'application
    tab1, tab2 = st.tabs(["🗺️ Carte", "📝 Données"])

    with tab1:
        # Calculer les distances et les trajets
        distances, routes, df = calculate_routes_osrm(df)

        # Identifier les séjours multiples
        df_avec_duree = identifier_sejours_multiples(df)

        # Créer et afficher la carte
        m = creer_carte(df, df_avec_duree, distances)
        st_folium(m, width=None, height=700)

        # Afficher le récapitulatif dans la sidebar (seulement dans l'onglet carte)
        afficher_recapitulatif_sidebar(df)

    with tab2:
        # Créer l'éditeur de données (qui gère aussi les emails)
        edited_df, df_visible, adresses_actuelles = creer_editeur_donnees(df)

        # Bouton pour appliquer les modifications
        if st.button("🔄 Appliquer les modifications"):
            traiter_modifications(edited_df, df_visible, df, adresses_actuelles, uploaded_file)


if __name__ == "__main__":
    main()
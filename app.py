import streamlit as st
import pandas as pd
import folium
import json
from streamlit_folium import st_folium
from folium.plugins import MiniMap
from core import (
    charger_donnees,
    sauvegarder_donnees,
    calculate_routes_graphhopper,
    identifier_sejours_multiples,
    ouvrir_pdf,
    charger_routes_existantes
)


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
    # Icônes de base
    icons = {
        "depart": folium.Icon(color="red", icon="play", prefix="fa"),
        "arrivee": folium.Icon(color="green", icon="flag-checkered", prefix="fa"),
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
        "séjour_1": "#87CEFA",  # Bleu clair (1 nuit)
        "séjour_2": "#1E90FF",  # Bleu (2 nuits)
        "séjour_3": "#4682B4",  # Bleu acier (3 nuits)
        "séjour_4": "#0000CD",  # Bleu foncé (4 nuits)
    }

    return icons, colors


def creer_carte(df, df_avec_duree, distances=None, durations=None):
    """Crée et configure la carte Folium avec les routes et marqueurs"""
    start_lat = df.iloc[0]["Latitude"]
    start_lon = df.iloc[0]["Longitude"]

    # Créer une carte sans tuile de base pour pouvoir alterner entre les vues
    m = folium.Map(
        location=[start_lat, start_lon],
        zoom_start=6,
        tiles=None,
        width="100%",
        height="100%"
    )

    # Ajouter la couche satellite
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        name="Satellite",
        attr='Esri',
    ).add_to(m)

    # Ajouter la couche de carte normale
    folium.TileLayer(
        tiles="CartoDB positron",
        name="Carte",
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    ).add_to(m)

    # Ajouter les tracés des routes entre chaque point
    for i in range(len(df) - 1):
        if pd.notna(df.iloc[i]["Chemin"]):
            route_coords = json.loads(df.iloc[i]["Chemin"])
            if route_coords:
                # Calculer la distance et la durée
                distance_text = ""
                duration_text = ""
                if "Distance (km)" in df.columns and pd.notna(df.iloc[i]["Distance (km)"]):
                    distance_text = f"{df.iloc[i]['Distance (km)']:.2f} km"
                elif distances is not None and i < len(distances) and pd.notna(distances[i]):
                    distance_text = f"{(distances[i] / 1000):.2f} km"

                if "Durée (h)" in df.columns and pd.notna(df.iloc[i]["Durée (h)"]):
                    # Convertir la durée en heures:minutes
                    duree_heures = df.iloc[i]["Durée (h)"]
                    heures = int(duree_heures)
                    minutes = int((duree_heures - heures) * 60)
                    duration_text = f"{heures}h{minutes:02d}"
                elif durations is not None and i < len(durations) and pd.notna(durations[i]):
                    duree_heures = durations[i]
                    heures = int(duree_heures)
                    minutes = int((duree_heures - heures) * 60)
                    duration_text = f"{heures}h{minutes:02d}"

                # Tracer la route avec distance et durée
                tooltip = f"Distance: {distance_text}"
                if duration_text:
                    tooltip += f" - Durée: {duration_text}"

                # Tracer la route
                route = folium.PolyLine(
                    locations=route_coords,
                    color="#4169E1",  # Bleu royal
                    weight=4,
                    opacity=0.8,
                    tooltip=tooltip
                )
                route.add_to(m)

    # Obtenir les icônes
    icons, colors = creer_icones()

    # Parcourir le DataFrame traité pour afficher les marqueurs
    for i, row in df_avec_duree.iterrows():
        # Ignorer les lignes qui ont été fusionnées avec une étape précédente
        if row["Duree_Sejour"] == -1:
            continue

        # Déterminer le type d'hébergement et le nombre de nuits
        duree_sejour = row["Duree_Sejour"] if "Duree_Sejour" in row and pd.notna(row["Duree_Sejour"]) else 0
        type_hebergement = row["Type_Hebergement"].lower() if "Type_Hebergement" in row and pd.notna(
            row["Type_Hebergement"]) else ""

        # Déterminer le type de point
        if i == 0:
            point_type = "départ"
            icon = icons["depart"]
            title = "Point de départ"
            color = colors["départ"]
        elif i == len(df) - 1 or (row["Adresse"] == df.iloc[-1]["Adresse"] if "Adresse" in row else False):
            point_type = "arrivée"
            icon = icons["arrivee"]
            title = "Point d'arrivée"
            color = colors["arrivée"]
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
            if "hôtel" in type_hebergement:
                icon = icons[f"hotel_{sejour_category}"]
                title = f"Hôtel ({duree_sejour} nuits)"
            elif "camping" in type_hebergement:
                icon = icons[f"camping_{sejour_category}"]
                title = f"Camping ({duree_sejour} nuits)"
            else:
                # Type d'hébergement non spécifié, on utilise l'icône de séjour générique
                icon = icons[f"sejour_{sejour_category}"]
                title = f"Séjour de {duree_sejour} nuits"

            # La couleur est déterminée uniquement par la durée du séjour
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
        elif "camping" in type_hebergement:
            tooltip_text = f"{ville} - Camping ({date_info})"
        elif "hôtel" in type_hebergement:
            tooltip_text = f"{ville} - Hôtel ({date_info})"
        else:
            tooltip_text = f"{ville} - Séjour de {duree_sejour} nuits ({date_info})"

        # Ajouter le marqueur
        folium.Marker(
            location=[row["Latitude"], row["Longitude"]],
            popup=folium.Popup(html_content, max_width=300),
            tooltip=tooltip_text,
            icon=icon
        ).add_to(m)

    # Ajouter le contrôle des couches pour basculer entre carte et satellite
    folium.LayerControl().add_to(m)

    return m


def afficher_pdfs_selectbox(df):
    """
    Affiche une liste déroulante pour sélectionner un hébergement et voir son PDF automatiquement

    Args:
        df: DataFrame contenant les données des hébergements avec les liens de PDF
    """
    # Initialiser les variables d'état de session
    if "carte_pdf_selectbox" not in st.session_state:
        st.session_state.carte_pdf_selectbox = None

    # Filtrer pour ne garder que les lignes avec des liens PDF valides
    df_with_pdfs = df[pd.notna(df["Lien"]) & (df["Lien"] != "")].copy()

    if not df_with_pdfs.empty:
        # Créer les options pour la liste déroulante
        options = []
        pdf_links = {}

        for i, row in df_with_pdfs.iterrows():
            # Récupérer les informations pour l'affichage
            ville = row["Ville"] if "Ville" in row and pd.notna(row["Ville"]) else ""
            nom = row["Nom"] if "Nom" in row and pd.notna(row["Nom"]) else ""
            nuit = row["Nuit"] if "Nuit" in row and pd.notna(row["Nuit"]) else ""

            # Créer un label descriptif
            label = f"{ville} - {nom} ({nuit})"
            options.append(label)
            pdf_links[label] = row["Lien"]

        # Créer un titre et un séparateur
        st.markdown("---")
        st.subheader("📄 Documents PDF")

        # Sélection de l'hébergement avec st.selectbox
        selected_option = st.selectbox(
            "Sélectionner un hébergement pour voir son document PDF:",
            options,
            index=None,
            placeholder="Choisir un hébergement...",
            key="carte_pdf_selectbox"  # Cette clé permettra de suivre la sélection
        )

        # Si une option est sélectionnée, afficher immédiatement le PDF
        if selected_option:
            pdf_link = pdf_links[selected_option]
            with st.expander("Document PDF", expanded=True):
                # Appeler ouvrir_pdf avec use_expander=False pour éviter l'imbrication d'expanders
                ouvrir_pdf(pdf_link, use_expander=False)

                # Ajouter un bouton pour fermer le PDF si nécessaire
                if st.button("Fermer le PDF", key="carte_pdf_close_button"):
                    # Réinitialiser la sélection
                    st.session_state.carte_pdf_selectbox = None
                    st.rerun()
    else:
        st.info("Aucun hébergement avec document PDF disponible.")

@st.cache_data()
def afficher_recapitulatif_metrics(df, distance_totale=None, duree_totale=None):
    """Affiche le récapitulatif du budget, de la distance et de la durée en utilisant st.metrics"""

    # Créer une ligne avec trois colonnes pour les métriques
    col1, col2, col3 = st.columns(3)

    # Afficher le budget total dans la première colonne
    total_budget = df["Prix"].sum(skipna=True)
    with col1:
        st.metric(
            label="💰 Budget total hébergements",
            value=f"{total_budget:.2f} $"
        )

    # Afficher la distance totale dans la seconde colonne
    if distance_totale is None:
        distance_totale = df["Distance (km)"].sum(skipna=True)
    with col2:
        st.metric(
            label="🚗 Distance totale",
            value=f"{distance_totale:.2f} km"
        )

    # Afficher la durée totale dans la troisième colonne
    if duree_totale is None and "Durée (h)" in df.columns:
        duree_totale = df["Durée (h)"].sum(skipna=True)

    if duree_totale is not None:
        # Convertir en heures et minutes
        heures = int(duree_totale)
        minutes = int((duree_totale - heures) * 60)
        with col3:
            st.metric(
                label="⏱️ Temps total de conduite",
                value=f"{heures}h{minutes:02d}"
            )


def creer_editeur_donnees(df):
    """Crée un éditeur de données pour modifier les informations du roadtrip"""
    # Initialiser les variables de session
    if "pdf_a_ouvrir" not in st.session_state:
        st.session_state.pdf_a_ouvrir = None
    if "previous_checked_idx" not in st.session_state:
        st.session_state.previous_checked_idx = None

    # Définir les colonnes à cacher
    colonnes_cachees = ['Chemin', 'Longitude', 'Latitude', 'Distance (km)', 'Durée (h)', 'Lien']
    df_visible = df.drop(columns=colonnes_cachees, errors="ignore")

    # Sauvegarde d'une copie des adresses actuelles
    adresses_actuelles = df_visible["Adresse"].copy() if "Adresse" in df_visible.columns else pd.Series([])

    # Ajouter une colonne de checkbox pour les PDF
    if "Lien" in df.columns:
        # Créer une colonne Afficher PDF
        df_visible = df_visible.copy()  # Éviter SettingWithCopyWarning
        df_visible["Afficher PDF"] = False

        # Si un PDF est ouvert, cocher la case correspondante
        if st.session_state.pdf_a_ouvrir is not None and st.session_state.previous_checked_idx is not None:
            if st.session_state.previous_checked_idx in df_visible.index:
                df_visible.loc[st.session_state.previous_checked_idx, "Afficher PDF"] = True

        # Réorganiser les colonnes pour avoir Afficher PDF en premier et Lien en dernier
        cols = list(df_visible.columns)
        # Retirer Afficher PDF et Lien des colonnes (s'ils existent)
        if "Afficher PDF" in cols:
            cols.remove("Afficher PDF")
        if "Lien" in cols:
            cols.remove("Lien")

        # Recréer la liste des colonnes dans le bon ordre
        new_cols = ["Afficher PDF"] + cols
        if "Lien" in df_visible.columns:
            new_cols = new_cols + ["Lien"]

        # Réorganiser le DataFrame
        df_visible = df_visible[new_cols]

    # Configuration des colonnes pour l'éditeur
    column_config = {
        "Afficher PDF": st.column_config.CheckboxColumn("📄", help="Cocher pour afficher le PDF"),
        "Adresse": st.column_config.TextColumn("Adresse", width="large"),
        "Ville": st.column_config.TextColumn("Ville", width="medium"),
        "Nom": st.column_config.TextColumn("Hébergement", width="medium"),
        "Prix": st.column_config.NumberColumn("Prix ($)", format="%.2f", width='small'),
        "Nuit": st.column_config.DatetimeColumn("Nuit", width="small", format="HH[h] DD/MM"),
        "Lien": st.column_config.TextColumn("Lien", width="small")
    }

    # Édition interactive du tableau
    edited_df = st.data_editor(
        df_visible,
        num_rows="dynamic",
        use_container_width=True,
        height=600,
        hide_index=True,
        column_config=column_config,
    )

    # Traiter les changements de checkbox
    if "Lien" in df.columns and "Afficher PDF" in edited_df.columns:
        # Identifier les lignes avec checkbox cochée
        pdf_checked_rows = edited_df[edited_df["Afficher PDF"] == True]

        # Si une nouvelle checkbox est cochée
        if not pdf_checked_rows.empty:
            checked_row_idx = pdf_checked_rows.index[0]

            # Si c'est une nouvelle ligne cochée ou si aucun PDF n'est actuellement ouvert
            if checked_row_idx != st.session_state.previous_checked_idx or st.session_state.pdf_a_ouvrir is None:
                # Récupérer le lien de PDF correspondant
                if checked_row_idx in df.index and pd.notna(df.loc[checked_row_idx, "Lien"]):
                    st.session_state.pdf_a_ouvrir = df.loc[checked_row_idx, "Lien"]
                    st.session_state.previous_checked_idx = checked_row_idx
                    st.rerun()  # Recharger la page pour afficher le PDF

            # Décocher toutes les autres checkboxes
            for idx in edited_df.index:
                if idx != checked_row_idx and edited_df.loc[idx, "Afficher PDF"]:
                    edited_df.loc[idx, "Afficher PDF"] = False

        # Si toutes les checkboxes sont décochées mais qu'un PDF est ouvert
        elif pdf_checked_rows.empty and st.session_state.pdf_a_ouvrir is not None:
            # Si l'utilisateur a décoché la case, fermer le PDF
            st.session_state.pdf_a_ouvrir = None
            st.session_state.previous_checked_idx = None
            st.rerun()  # Recharger la page pour fermer le PDF

    # Afficher le PDF sélectionné
    if st.session_state.pdf_a_ouvrir:
        with st.expander("📄 Document PDF", expanded=True):
            # Appeler ouvrir_pdf avec use_expander=False pour éviter l'imbrication d'expanders
            ouvrir_pdf(st.session_state.pdf_a_ouvrir, use_expander=False)
            if st.button("Fermer le PDF"):
                # Fermer le PDF et décocher la case
                st.session_state.pdf_a_ouvrir = None
                st.session_state.previous_checked_idx = None
                # Cette ligne ne suffit pas car edited_df ne persiste pas après st.rerun()
                # C'est pourquoi nous utilisons previous_checked_idx pour suivre l'état
                if "Afficher PDF" in edited_df.columns:
                    edited_df["Afficher PDF"] = False
                st.rerun()

    return edited_df, df_visible, adresses_actuelles


def traiter_modifications(edited_df, df_visible, df, adresses_actuelles, uploaded_file):
    """Traite les modifications apportées aux données et recalcule les distances si nécessaire"""
    # Vérifier si de nouvelles lignes ont été ajoutées
    if len(edited_df) > len(df_visible):
        st.info(f"Détection de {len(edited_df) - len(df_visible)} nouvelles lignes.")

        # Pour les nouvelles lignes, on ajoute directement au DataFrame principal
        nouvelles_lignes = edited_df.iloc[len(df_visible):]
        for _, nouvelle_ligne in nouvelles_lignes.iterrows():
            # Créer une nouvelle ligne pour df avec toutes les colonnes nécessaires
            nouvelle_ligne_complete = pd.Series(index=df.columns)

            # Copier les valeurs existantes
            for col in nouvelle_ligne.index:
                if col in df.columns:
                    nouvelle_ligne_complete[col] = nouvelle_ligne[col]

            # Ajouter la nouvelle ligne au DataFrame principal
            df = pd.concat([df, pd.DataFrame([nouvelle_ligne_complete])], ignore_index=True)

        # Sauvegarder immédiatement pour les nouvelles lignes
        df = df.sort_values(by="Nuit").reset_index(drop=True)

        _, _, _, df = calculate_routes_graphhopper(df)

        sauvegarder_donnees(df, nom_fichier=uploaded_file)
        st.success("✅ Nouvelles lignes ajoutées avec succès!")
        return

    # Ne comparer que les lignes existantes (pour les modifications)
    if len(edited_df) == len(df_visible):
        # Vérifier les modifications ligne par ligne et colonne par colonne
        routes_a_recalculer = set()
        modifications_detectees = False

        for idx in range(len(edited_df)):
            for col in edited_df.columns:
                # Éviter de comparer la colonne 'Afficher PDF' qui est un état temporaire
                if col == 'Afficher PDF':
                    continue

                # Vérifier si la valeur a été modifiée
                if edited_df.loc[idx, col] != df_visible.loc[idx, col]:
                    modifications_detectees = True

                    # Mettre à jour la valeur dans le DataFrame complet
                    if col in df.columns:
                        df.loc[idx, col] = edited_df.loc[idx, col]

                    # Vérifier les modifications qui nécessitent un recalcul des routes
                    if col == "Adresse":
                        routes_a_recalculer.add(idx)
                        # Réinitialiser les coordonnées
                        df.loc[idx, "Latitude"] = None
                        df.loc[idx, "Longitude"] = None

                    if col == "Type_Deplacement":
                        routes_a_recalculer.add(idx)

        # Pour chaque route à recalculer, réinitialiser les données de chemin
        for idx in routes_a_recalculer:
            df.loc[idx, "Chemin"] = None
            df.loc[idx, "Distance (km)"] = None
            df.loc[idx, "Durée (h)"] = None

            # Réinitialiser aussi le chemin précédent si ce n'est pas la première ligne
            if idx > 0:
                df.loc[idx - 1, "Chemin"] = None
                df.loc[idx - 1, "Distance (km)"] = None
                df.loc[idx - 1, "Durée (h)"] = None

        if modifications_detectees:
            if routes_a_recalculer:
                st.info(f"Recalcul des routes pour les indices : {sorted(routes_a_recalculer)}")

                # Recalculer les routes et distances pour tout le DataFrame
                with st.spinner("Recalcul des itinéraires et des distances..."):
                    distances_list, durations, route_geoms, df_updated = calculate_routes_graphhopper(df)
                    # Mettre à jour le DataFrame avec les résultats recalculés
                    df = df_updated

            # Trier et réinitialiser l'index
            df = df.sort_values(by="Nuit").reset_index(drop=True)

            # Sauvegarder le DataFrame mis à jour
            sauvegarder_donnees(df, nom_fichier=uploaded_file)

            # Calculer la distance totale mise à jour
            distance_totale_maj = df["Distance (km)"].sum(skipna=True)

            st.success("✅ Modifications appliquées avec succès!")
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
        distances,durations, routes, df = charger_routes_existantes(df)

        # Identifier les séjours multiples
        df_avec_duree = identifier_sejours_multiples(df)

        # Afficher le récapitulatif dans la sidebar (seulement dans l'onglet carte)
        afficher_recapitulatif_metrics(df)

        # Créer et afficher la carte
        m = creer_carte(df, df_avec_duree, distances, durations)
        st_folium(m, width=None, height=700)

        # Remplacer la fonction d'affichage d'emails par celle pour les PDF
        afficher_pdfs_selectbox(df)

    with tab2:
        # Afficher le récapitulatif dans la sidebar (seulement dans l'onglet carte)
        afficher_recapitulatif_metrics(df)

        # Créer l'éditeur de données (qui gère aussi les PDF)
        edited_df, df_visible, adresses_actuelles = creer_editeur_donnees(df)

        # Bouton pour appliquer les modifications
        if st.button("🔄 Appliquer les modifications"):
            df = df.sort_values(by="Nuit").reset_index(drop=True)
            traiter_modifications(edited_df, df_visible, df, adresses_actuelles, uploaded_file)


if __name__ == "__main__":
    main()
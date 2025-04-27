import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from utils.core import (
    charger_donnees,
    charger_routes_existantes,
    identifier_sejours_multiples,
    ouvrir_pdf,
    sauvegarder_donnees,
)
from utils.creer_carte import creer_carte
from utils.get_route import calculate_routes


def configurer_page():
    """Configuration initiale de la page Streamlit"""
    st.set_page_config(layout="wide")
    st.title("🗺️ Carte interactive du Roadtrip 🚗")


def afficher_pdfs_selectbox(df):
    """
    Affiche une liste déroulante pour sélectionner un hébergement
    et voir son PDF automatiquement

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
        st.subheader("📄 Documents PDF")

        # Sélection de l'hébergement avec st.selectbox
        selected_option = st.selectbox(
            "Sélectionner un hébergement pour voir son document PDF:",
            options,
            index=None,
            placeholder="Choisir un hébergement...",
            key="carte_pdf_selectbox",  # Cette clé permettra de suivre la sélection
        )

        # Si une option est sélectionnée, afficher immédiatement le PDF
        if selected_option:
            pdf_link = pdf_links[selected_option]
            with st.expander("Document PDF", expanded=True):
                # Appeler ouvrir_pdf avec use_expander=False pour éviter
                # l'imbrication d'expanders
                ouvrir_pdf(pdf_link, use_expander=False)

                # Ajouter un bouton pour fermer le PDF si nécessaire
                if st.button("Fermer le PDF", key="carte_pdf_close_button"):
                    # Réinitialiser la sélection
                    st.session_state.carte_pdf_selectbox = None
                    # st.rerun()
    else:
        st.info("Aucun hébergement avec document PDF disponible.")


@st.cache_data()
def afficher_recapitulatif_metrics(df, distance_totale=None, duree_totale=None):
    """Affiche le récapitulatif du budget, de la distance
    et de la durée en utilisant st.metrics en excluant les déplacements
    à pied des calculs de distance et durée"""

    # Créer une ligne avec trois colonnes pour les métriques
    col1, col2, col3 = st.columns(3)

    # Afficher le budget total dans la première colonne
    total_budget = df["Prix"].sum(skipna=True)
    with col1:
        st.metric(label="💰 Budget total hébergements", value=f"{total_budget:.2f} $")

    # Calculer la distance totale en excluant les déplacements à pied
    if distance_totale is None:
        # Filtrer pour exclure les déplacements à pied
        if "Type_Deplacement" in df.columns:
            df_vehicule = df[df["Type_Deplacement"].fillna("").str.lower() != "marche"]
            distance_totale = df_vehicule["Distance (km)"].sum(skipna=True)
        else:
            distance_totale = df["Distance (km)"].sum(skipna=True)

    with col2:
        st.metric(label="🚗 Distance totale en véhicule", value=f"{distance_totale:.2f} km")

    # Calculer la durée totale en excluant les déplacements à pied
    if duree_totale is None and "Durée (h)" in df.columns:
        if "Type_Deplacement" in df.columns:
            df_vehicule = df[df["Type_Deplacement"].fillna("").str.lower() != "marche"]
            duree_totale = df_vehicule["Durée (h)"].sum(skipna=True)
        else:
            duree_totale = df["Durée (h)"].sum(skipna=True)

    if duree_totale is not None:
        # Convertir en heures et minutes
        heures = int(duree_totale)
        minutes = int((duree_totale - heures) * 60)
        with col3:
            st.metric(label="⏱️ Temps total de conduite", value=f"{heures}h{minutes:02d}")


def creer_editeur_donnees(df):
    """Crée un éditeur de données pour modifier les informations du roadtrip"""
    # Initialiser les variables de session
    if "pdf_a_ouvrir" not in st.session_state:
        st.session_state.pdf_a_ouvrir = None
    if "previous_checked_idx" not in st.session_state:
        st.session_state.previous_checked_idx = None

    # Définir les colonnes à cacher
    colonnes_cachees = [
        "Chemin",
        "Longitude",
        "Latitude",
        "Distance (km)",
        "Durée (h)",
        "Lien",
    ]
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
        "Prix": st.column_config.NumberColumn("Prix ($)", format="%.2f", width="small"),
        "Nuit": st.column_config.DatetimeColumn("Nuit", width="small", format="HH[h] DD/MM"),
        "Lien": st.column_config.TextColumn("Lien", width="small"),
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
        pdf_checked_rows = edited_df[edited_df["Afficher PDF"] is True]

        # Si une nouvelle checkbox est cochée
        if not pdf_checked_rows.empty:
            checked_row_idx = pdf_checked_rows.index[0]

            # Si c'est une nouvelle ligne cochée ou si aucun PDF n'est actuellement ouvert
            if checked_row_idx != st.session_state.previous_checked_idx or st.session_state.pdf_a_ouvrir is None:
                # Récupérer le lien de PDF correspondant
                if checked_row_idx in df.index and pd.notna(df.loc[checked_row_idx, "Lien"]):
                    st.session_state.pdf_a_ouvrir = df.loc[checked_row_idx, "Lien"]
                    st.session_state.previous_checked_idx = checked_row_idx
                    # st.rerun()  # Recharger la page pour afficher le PDF

            # Décocher toutes les autres checkboxes
            for idx in edited_df.index:
                if idx != checked_row_idx and edited_df.loc[idx, "Afficher PDF"]:
                    edited_df.loc[idx, "Afficher PDF"] = False

        # Si toutes les checkboxes sont décochées mais qu'un PDF est ouvert
        elif pdf_checked_rows.empty and st.session_state.pdf_a_ouvrir is not None:
            # Si l'utilisateur a décoché la case, fermer le PDF
            st.session_state.pdf_a_ouvrir = None
            st.session_state.previous_checked_idx = None
            # st.rerun()  # Recharger la page pour fermer le PDF

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
                # st.rerun()

    return edited_df, df_visible, adresses_actuelles


def traiter_modifications(edited_df, df_visible, df, adresses_actuelles, uploaded_file):
    """Traite les modifications apportées aux données et recalcule les distances si nécessaire"""
    # Vérifier si de nouvelles lignes ont été ajoutées
    if len(edited_df) > len(df_visible):
        st.info(f"Détection de {len(edited_df) - len(df_visible)} nouvelles lignes.")

        # Pour les nouvelles lignes, on ajoute directement au DataFrame principal
        nouvelles_lignes = edited_df.iloc[len(df_visible) :]
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

        _, _, _, df = calculate_routes(df)

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
                if col == "Afficher PDF":
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
                    distances_list, durations, route_geoms, df_updated = calculate_routes(df)
                    # Mettre à jour le DataFrame avec les résultats recalculés
                    df = df_updated

            # Trier et réinitialiser l'index
            df = df.sort_values(by="Nuit").reset_index(drop=True)

            # Sauvegarder le DataFrame mis à jour
            sauvegarder_donnees(df, nom_fichier=uploaded_file)

            st.success("✅ Modifications appliquées avec succès!")
        else:
            st.info("Aucune modification détectée.")


def main():
    """Fonction principale qui gère l'application Streamlit"""

    # Configuration de la page
    configurer_page()

    # Charger le fichier parquet
    uploaded_file = "data/hebergements_chemins.parquet"
    df = charger_donnees(nom_fichier=uploaded_file, format="parquet")

    # Onglets pour différentes sections de l'application
    tab1, tab2 = st.tabs(["🗺️ Carte", "📝 Données"])

    with tab1:
        # Calculer les distances et les trajets
        distances, durations, routes, df = charger_routes_existantes(df)

        # Identifier les séjours multiples
        df_avec_duree = identifier_sejours_multiples(df)

        # Afficher le récapitulatif dans la sidebar (seulement dans l'onglet carte)
        afficher_recapitulatif_metrics(df)

        # Créer et afficher la carte
        m = creer_carte(df, df_avec_duree, distances, durations)
        st_folium(m, height=700, use_container_width=True, returned_objects=[])

        # Remplacer la fonction d'affichage d'emails par celle pour les PDF
        afficher_pdfs_selectbox(df)

    with tab2:
        # Afficher le récapitulatif dans la sidebar (seulement dans l'onglet carte)
        afficher_recapitulatif_metrics(df)

        # Créer l'éditeur de données (qui gère aussi les PDF)
        edited_df, df_visible, adresses_actuelles = creer_editeur_donnees(df)

        # Bouton pour appliquer les modifications
        if st.button("🔄 Appliquer les modifications"):
            traiter_modifications(edited_df, df_visible, df, adresses_actuelles, uploaded_file)


if __name__ == "__main__":
    main()

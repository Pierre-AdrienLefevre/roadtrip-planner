import streamlit as st
import pandas as pd
import json
from core import calculate_routes_osrm, charger_donnees, sauvegarder_donnees

st.set_page_config(layout="wide")

# Charger le fichier Parquet existant
uploaded_file = 'data/hebergements_chemins.parquet'
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
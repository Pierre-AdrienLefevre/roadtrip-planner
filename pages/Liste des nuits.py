import streamlit as st
import pandas as pd
import json
from core import calculate_routes_osrm

st.set_page_config(layout="wide")

# Charger le fichier Parquet existant
uploaded_file = 'data/hebergements_chemins.parquet'
df = pd.read_parquet(uploaded_file)

# Définir les colonnes à cacher
colonnes_cachees = ['Chemin', 'Longitude', 'Latitude', 'Type']
df_visible = df.drop(columns=colonnes_cachees, errors="ignore")

# Édition interactive du tableau
edited_df = st.data_editor(df_visible,
                           num_rows="fixed",
                           use_container_width=True,
                           height=800,
                           hide_index=True)

# Afficher le budget total
total_budget = edited_df["Prix"].sum(skipna=True)
st.sidebar.subheader("💰 Récapitulatif budget et distance")
st.sidebar.write(f"**Budget total pour les hébergements :** {total_budget:.2f} $")

# Bouton pour appliquer les modifications et recalculer les distances
if st.sidebar.button("🔄 Appliquer les modifications"):
    # Trouver les lignes modifiées
    modifications = edited_df.compare(df_visible)  # Détecte les changements

    if not modifications.empty:
        indices_modifiés = modifications.index.tolist()

        # Ne recalculer que la ligne modifiée et la ligne immédiatement après
        indices_a_recalculer = set()
        for idx in indices_modifiés:
            indices_a_recalculer.add(idx)
            if idx < len(df) - 1:
                indices_a_recalculer.add(idx + 1)

        # Convertir en liste triée
        indices_a_recalculer = sorted(indices_a_recalculer)

        # Créer un sous-DataFrame avec uniquement les lignes à recalculer
        df_subset = df.loc[indices_a_recalculer].copy()

        with st.spinner(f"Recalcul des distances pour les lignes {indices_a_recalculer}..."):
            # Recalculer les routes pour le sous-DataFrame
            _, _, df_recalc = calculate_routes_osrm(df_subset)

            # Mettre à jour uniquement les lignes concernées dans le DataFrame original
            df.update(df_recalc)
            df.to_parquet(uploaded_file, index=False)

        st.success("✅ Modifications appliquées et distances recalculées !")
    else:
        st.info("Aucune modification détectée.")
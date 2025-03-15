import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")


# Titre de l'application
st.title("🛌 Planification des hébergements - Roadtrip 🚗")

# Charger le fichier Parquet existant
uploaded_file = 'data/hebergements_chemins.parquet'
df = pd.read_parquet(uploaded_file)

# Définir les colonnes à cacher
colonnes_cachees = ['Chemin', 'Longitude', 'Latitude', 'Type', 'Adresse']

# Filtrer le DataFrame pour afficher uniquement les colonnes visibles
colonnes_visibles = [col for col in df.columns if col not in colonnes_cachees]
df_visible = df[colonnes_visibles]

# Édition interactive du tableau avec uniquement les colonnes visibles
edited_df = st.data_editor(df_visible,
                           num_rows="fixed",
                           use_container_width=True,
                           height=800,
                           hide_index=True)

# Calculs : Total km et budget
total_budget = edited_df["Prix"].sum(skipna=True)

with st.sidebar:
    # Afficher les totaux
    st.subheader("💰 Récapitulatif budget et distance")
    st.write(f"**Budget total pour les hébergements :** {total_budget:.2f} $")

    # Bouton pour enregistrer les modifications directement dans le fichier Parquet
    if st.button("💾 Enregistrer les modifications"):
        # Ajouter les colonnes cachées uniquement avant de sauvegarder
        df_sauvegarde = edited_df.copy()
        for col in colonnes_cachees:
            if col in df.columns:
                df_sauvegarde[col] = df[col]

        # Sauvegarde dans le fichier Parquet
        df_sauvegarde.to_parquet(uploaded_file, index=False)
        st.success("✅ Modifications enregistrées dans le fichier Parquet !")
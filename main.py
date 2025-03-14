import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")

# Titre de l'application
st.title("🛌 Planification des hébergements - Roadtrip 🚗")

# Charger le fichier CSV existant
uploaded_file = 'data/hebergements.csv'
df = pd.read_csv(uploaded_file, sep = ';')

df.info()

df["Jour"] = pd.to_datetime(df["Jour"], dayfirst=True).dt.strftime("%Y-%m-%d")
df['Distance'] = df['Distance'].astype(float)
# Remplace les virgules par des points pour éviter les erreurs de conversion
df["Prix"] = df["Prix"].astype(str).str.replace(",", ".").astype(float)

df['Prix'] = df['Prix'].astype(float)

# Édition interactive du tableau
st.subheader("📅 Modifiez vos hébergements")
edited_df = st.data_editor(df, num_rows="fixed", use_container_width=True, height= 800, hide_index=True)

# Calculs : Total km et budget
total_budget = edited_df["Prix"].sum(skipna=True)

# Afficher les totaux
st.subheader("💰 Récapitulatif budget et distance")
st.write(f"**Budget total pour les hébergements :** {total_budget} $")


# Téléchargement du fichier modifié
st.download_button(
    label="💾 Sauvegarder les modifications",
    data=edited_df.to_csv(index=False,sep = ';'),
    file_name="roadtrip_hebergements_modifié.csv",
    mime="text/csv"
)
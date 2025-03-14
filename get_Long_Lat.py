from opencage.geocoder import OpenCageGeocode
import pandas as pd

def add_lat_lon(df, address_column="Adresse", api_key="05f0f1136ddc4ccaa6a88aeb6fffb51b"):
    """Utilise OpenCage API pour géocoder rapidement une liste d'adresses"""

    geocoder = OpenCageGeocode(api_key)

    if "Latitude" not in df.columns:
        df["Latitude"] = None
    if "Longitude" not in df.columns:
        df["Longitude"] = None

    def get_coordinates(address):
        try:
            result = geocoder.geocode(address)
            if result:
                return result[0]["geometry"]["lat"], result[0]["geometry"]["lng"]
        except Exception as e:
            print(f"Erreur pour {address}: {e}")
        return None, None

    for index, row in df.iterrows():
        if pd.isna(row["Latitude"]) or pd.isna(row["Longitude"]):
            lat, lon = get_coordinates(row[address_column])
            df.at[index, "Latitude"] = lat
            df.at[index, "Longitude"] = lon

    return df


# Charger le fichier CSV (exemple)
df = pd.read_csv("data/hebergements.csv", sep=";")

# Appliquer la fonction pour ajouter les coordonnées
df = add_lat_lon(df, address_column="Adresse")

# Sauvegarder le fichier mis à jour
df.to_csv("data/hebergements_avec_coords_open.csv", index=False, sep=";", encoding="utf-8")

print("✅ Latitude et Longitude ajoutées avec succès !")
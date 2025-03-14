import requests
import polyline

# Coordonnées (latitude, longitude) pour Montréal et Winnipeg
montreal = (45.5017, -73.5673)  # Montréal
winnipeg = (49.8951, -97.1384)  # Winnipeg

# Construire l'URL pour l'appel à l'API OSRM
# Note : OSRM attend les coordonnées au format lon,lat
url = (
    f"http://router.project-osrm.org/route/v1/driving/"
    f"{montreal[1]},{montreal[0]};{winnipeg[1]},{winnipeg[0]}"
    "?overview=full&geometries=polyline"
)

# Appel à l'API OSRM
response = requests.get(url)

if response.status_code == 200:
    data = response.json()
    route = data['routes'][0]
    # Récupérer la distance (en mètres) et la durée (en secondes)
    distance_km = route['distance'] / 1000  # Convertir en kilomètres
    duration_min = route['duration'] / 60  # Convertir en minutes

    # Décoder le polyline pour obtenir le tracé (liste de (lat, lon))
    geometry = route['geometry']
    route_coords = polyline.decode(geometry)

    print("Distance :", distance_km, "km")
    print("Durée :", duration_min, "minutes")
    print("Coordonnées du tracé :")
    for coord in route_coords:
        print(coord)
else:
    print("Erreur lors de l'appel à l'API OSRM :", response.status_code)
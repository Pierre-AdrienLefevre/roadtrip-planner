# 🏕️ Roadtrip Planner 🚗

Une application Streamlit permettant de planifier facilement des roadtrips en visualisant les itinéraires sur une carte interactive et en gérant les hébergements.

## 📋 Fonctionnalités

- Visualisation des itinéraires sur une carte interactive
- Calcul automatique des distances entre chaque étape
- Gestion des hébergements et des adresses
- Géocodage automatique des adresses
- Sauvegarde des itinéraires et des données

## 🛠️ Technologies utilisées

- [Python](https://www.python.org/)
- [Streamlit](https://streamlit.io/) - Framework pour applications web
- [Pandas](https://pandas.pydata.org/) - Manipulation de données
- [Folium](https://python-visualization.github.io/folium/) - Création de cartes interactives
- [OSRM](http://project-osrm.org/) - Calcul d'itinéraires
- [OpenCage Geocoder](https://opencagedata.com/) - Géocodage d'adresses
- uv pour la gestion des dépendances

## 🚀 Installation

1. Cloner ce dépôt
```bash
git clone https://github.com/votre-username/roadtrip-planner.git
cd roadtrip-planner
```
2. Installer uv si ce n'est pas fait 
```bash
brew install uv
```

3. Installer les dépendances avec uv
```bash
uv sync
```

4. Configurer les secrets
```bash
mkdir -p .streamlit
echo "opencage_api_key = \"votre-clé-api-opencage\"" > .streamlit/secrets.toml
```

4. Exécuter l'application
```bash
streamlit run app.py
```

## 📂 Structure du projet

```
├── README.md                          # Documentation du projet
├── app.py                             # Point d'entrée de l'application
├── core.py                            # Fonctions principales
├── .streamlit/                        # Configuration Streamlit (non inclus dans le dépôt)
│   └── secrets.toml                   # Secrets (clés API)
├── pages/                             # Pages de l'application Streamlit
│   ├── Afficher Carte.py              # Page d'affichage de la carte
│   └── Liste des nuits.py             # Page de gestion des hébergements
├── data/                              # Données du projet (non inclus dans le dépôt)
│   ├── hebergements.parquet           # Liste des hébergements avec chemins calculés et coordonnées géocodées
├── pyproject.toml                     # Configuration du projet Python
└── .gitignore                         # Fichiers exclus du dépôt
```

## 🧩 Fonctionnement

1. **Page d'accueil** : Introduction à l'application et navigation vers les différentes pages
2. **Afficher Carte** : Visualisation de l'itinéraire complet avec les marqueurs pour chaque étape
3. **Liste des nuits** : Gestion des hébergements et leur ordre dans l'itinéraire

## 🌐 API utilisées

- **OpenCage Geocoder** : Conversion des adresses en coordonnées géographiques (latitude/longitude)
- **OSRM** (Open Source Routing Machine) : Calcul des itinéraires entre les points

## 📈 Améliorations futures

- Ajout d'une fonctionnalité de calcul de budget
- Optimisation de l'itinéraire pour minimiser la distance ou le temps de trajet
- Intégration de points d'intérêt le long du parcours
- Support pour différents modes de transport (voiture, vélo, marche)

## 📜 Licence

Ce projet est distribué sous licence MIT.

## 👤 Auteur

Créé avec passion lors d'une préparation d'un road trip au Canada. 

---

*Note: Cette application utilise une clé API OpenCage pour le géocodage, à configurer dans .streamlit/secrets.toml. Obtenez une clé gratuite sur [opencagedata.com](https://opencagedata.com/).*
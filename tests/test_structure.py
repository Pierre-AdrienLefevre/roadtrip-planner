import os


def test_project_structure():
    """Vérifie que la structure du projet est correcte"""
    # Vérifier que les fichiers principaux existent
    assert os.path.exists("app.py"), "app.py n'existe pas"
    assert os.path.exists("pyproject.toml"), "pyproject.toml n'existe pas"

    # Vérifier que le dossier utils existe et contient les fichiers nécessaires
    assert os.path.exists("utils"), "Le dossier utils n'existe pas"
    assert os.path.exists("utils/core.py"), "utils/core.py n'existe pas"
    assert os.path.exists("utils/creer_carte.py"), "utils/creer_carte.py n'existe pas"
    assert os.path.exists("utils/get_route.py"), "utils/get_route.py n'existe pas"

    # Vérifier que le dossier .streamlit existe
    assert os.path.exists(".streamlit"), "Le dossier .streamlit n'existe pas"

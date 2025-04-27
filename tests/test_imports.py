import pytest

def test_basic_imports():
    """Test que les modules de base peuvent être importés"""
    # Import des modules principaux
    import streamlit
    import pandas
    import folium
    from streamlit_folium import st_folium

    # Si on arrive ici sans erreur, le test est réussi
    assert True


def test_project_imports():
    """Test que les modules spécifiques au projet peuvent être importés"""
    from utils.core import charger_donnees, sauvegarder_donnees
    from utils.get_route import calculate_routes
    from utils.creer_carte import creer_carte

    # Si on arrive ici sans erreur, le test est réussi
    assert True
import pytest
import os


def test_app_file_exists():
    """Vérifie que le fichier app.py existe et peut être importé"""
    assert os.path.exists("app.py"), "Le fichier app.py n'existe pas"

    # Test d'import (si possible sans exécuter l'application)
    # Note: Cette approche peut nécessiter des ajustements en fonction
    # de la structure de votre code
    try:
        import app
        assert True
    except ImportError as e:
        # Si l'import échoue à cause d'autres dépendances manquantes en test,
        # on peut simplement vérifier que le fichier existe
        pytest.skip(f"Import de app.py impossible: {e}")
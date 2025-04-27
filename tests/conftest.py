import os
import sys

import pytest

# Ajouter le répertoire racine du projet au chemin Python pour permettre
# l'importation des modules du projet dans les tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Ces fixtures peuvent être utilisées dans vos tests
@pytest.fixture
def root_dir():
    """Retourne le répertoire racine du projet"""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

@pytest.fixture
def utils_dir():
    """Retourne le répertoire utils du projet"""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '../utils'))
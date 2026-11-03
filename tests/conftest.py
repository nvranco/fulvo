import pytest
from fastapi.testclient import TestClient

from fulvo.app import app
from fulvo.routes.complejos import complejos, ids_complejos
from fulvo.routes.zonas import ids_zonas, zonas


@pytest.fixture
def client():
    """Cliente HTTP de prueba, creado de nuevo para cada test."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def restaurar_listas_en_memoria():
    """Deja las listas en memoria como estaban al terminar cada test.

    Los tests que crean o borran datos no pueden afectar a los demás, que
    corren en orden aleatorio. Se restaura en el mismo lugar ([:]) porque
    las rutas usan esos mismos objetos lista. También se restauran los
    contadores de ids, que si no seguirían avanzando entre tests.
    """
    copia_complejos = complejos.copy()
    copia_zonas = zonas.copy()
    ultimo_complejo = ids_complejos.ultimo
    ultimo_zona = ids_zonas.ultimo
    yield
    complejos[:] = copia_complejos
    zonas[:] = copia_zonas
    ids_complejos.ultimo = ultimo_complejo
    ids_zonas.ultimo = ultimo_zona

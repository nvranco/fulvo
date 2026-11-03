import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from fulvo.app import app
from fulvo.models import table_registry
from fulvo.routes.complejos import complejos, ids_complejos
from fulvo.routes.zonas import ids_zonas, zonas


@pytest.fixture
def session():
    """Sesión sobre una base SQLite en memoria, nueva para cada test.

    `StaticPool` y `check_same_thread=False` hacen que todas las conexiones
    usen la misma base en memoria, también cuando la usan otros hilos (las
    rutas `def` de FastAPI corren en un pool de hilos). Las tablas se crean
    antes y se borran después, así los tests no se afectan entre sí.
    """
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    table_registry.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    table_registry.metadata.drop_all(engine)
    engine.dispose()


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

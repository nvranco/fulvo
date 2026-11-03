import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from fulvo.app import app
from fulvo.carga_inicial import cargar
from fulvo.database import get_session
from fulvo.models import table_registry


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
def datos_iniciales(session):
    """Carga en la base de prueba las zonas y complejos del CSV.

    Es la misma carga que se usa en desarrollo (`fulvo.carga_inicial`). Los
    tests de rutas parten de estos datos: 8 zonas y 51 complejos.
    """
    cargar(session)


@pytest.fixture
def client(session, datos_iniciales):
    """Cliente HTTP de prueba conectado a la base en memoria.

    Reemplaza `get_session` por la sesión de prueba (`dependency_overrides`):
    las rutas escriben y leen en la base en memoria, nunca en `fulvo.db`.
    """

    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()

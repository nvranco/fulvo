import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from fulvo.app import app
from fulvo.carga_inicial import cargar, cargar_roles
from fulvo.database import get_session
from fulvo.models import ROL_ADMIN, ROL_USUARIO, Rol, table_registry
from fulvo.security import crear_token_acceso
from tests.datos import EMAIL, EMAIL_ADMIN, EMAIL_OTRO
from tests.factories import UsuarioFactory


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
    """Carga en la base de prueba los roles base y las zonas y complejos.

    Es la misma carga que se usa en desarrollo (`fulvo.carga_inicial`). Los
    tests de rutas parten de estos datos: 8 zonas y 51 complejos.
    """
    cargar_roles(session)
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


def guardar_usuario(session, email, nombre_rol):
    """Guarda un usuario con el rol indicado (contraseña CONTRASENA).

    La factory arma el objeto con datos válidos; acá solo se resuelve el
    `rol_id` (depende de los roles cargados) y se persiste.
    """
    rol_id = session.scalars(
        select(Rol.id).where(Rol.nombre == nombre_rol)
    ).one()
    usuario = UsuarioFactory(email=email, rol_id=rol_id)
    session.add(usuario)
    session.commit()
    return usuario


@pytest.fixture
def usuario(session, datos_iniciales):
    """Usuario común ya guardado (email EMAIL, contraseña CONTRASENA)."""
    return guardar_usuario(session, EMAIL, ROL_USUARIO)


@pytest.fixture
def otro_usuario(session, datos_iniciales):
    """Segundo usuario común, para probar lo que cada uno ve del otro."""
    return guardar_usuario(session, EMAIL_OTRO, ROL_USUARIO)


@pytest.fixture
def token(usuario):
    """Token válido del usuario de la fixture `usuario`."""
    return crear_token_acceso({'sub': usuario.email})


@pytest.fixture
def admin(session, datos_iniciales):
    """Usuario con rol admin ya guardado."""
    return guardar_usuario(session, EMAIL_ADMIN, ROL_ADMIN)


@pytest.fixture
def client_admin(client, admin):
    """El mismo `client`, pero con el token del admin en cada pedido.

    Para los tests que crean, editan o borran zonas y complejos, que
    exigen rol admin.
    """
    token = crear_token_acceso({'sub': admin.email})
    client.headers['Authorization'] = f'Bearer {token}'
    return client


@pytest.fixture
def client_usuario(client, token):
    """El mismo `client`, con el token de un usuario común (sin rol admin)."""
    client.headers['Authorization'] = f'Bearer {token}'
    return client

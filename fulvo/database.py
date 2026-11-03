from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fulvo.settings import Settings

# Un solo engine para toda la app: administra las conexiones a la base. No
# se conecta al crearlo sino la primera vez que se usa.
engine = create_engine(Settings().DATABASE_URL)


def get_session():
    """Entrega una sesión por request y la cierra al terminar.

    Se usa con `Depends`. El `with` cierra la sesión aunque la ruta falle,
    y los tests reemplazan esta función por una sesión sobre SQLite en
    memoria (`app.dependency_overrides`).

    Como en la cátedra, cada archivo de `routes/` define su alias:
    `Session = Annotated[Session, Depends(get_session)]`.
    """
    with Session(engine) as session:
        yield session

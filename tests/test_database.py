import pytest
from sqlalchemy.orm import Session

from fulvo.database import get_session


def test_get_session_entrega_una_sesion_y_la_cierra_al_terminar():
    generador = get_session()

    session = next(generador)

    assert isinstance(session, Session)
    # Al agotarse el generador se sale del `with` y la sesión se cierra.
    with pytest.raises(StopIteration):
        next(generador)

from datetime import datetime

import pytest
from sqlalchemy import select

from fulvo.errores import ReglaDeNegocioError
from fulvo.models import Sancion
from tests.factories import guardar_usuario_comun

MOTIVO = 'Insultó a otros jugadores'
AL_BLOQUEAR = datetime(2026, 11, 12, 10, 0)
AL_DESBLOQUEAR = datetime(2026, 11, 20, 18, 30)
MAS_TARDE = datetime(2026, 12, 1, 9, 0)
NO_A_UN_ADMIN = 'No se puede bloquear a un administrador'


def test_bloquear_marca_al_usuario_y_registra_la_sancion(usuario, admin):
    sancion = usuario.bloquear(admin, MOTIVO, AL_BLOQUEAR)

    assert usuario.bloqueado
    assert usuario.sanciones == [sancion]
    assert sancion.usuario is usuario
    assert sancion.aplicada_por_id == admin.id
    assert sancion.motivo == MOTIVO
    assert sancion.desde == AL_BLOQUEAR
    assert sancion.hasta is None
    assert sancion.activa()


def test_la_sancion_se_guarda_con_el_usuario_y_el_admin(
    session, usuario, admin
):
    usuario.bloquear(admin, MOTIVO, AL_BLOQUEAR)
    session.commit()
    session.expire_all()

    guardada = session.scalars(select(Sancion)).one()

    assert guardada.usuario.id == usuario.id
    assert guardada.usuario.bloqueado
    assert guardada.aplicada_por.id == admin.id


def test_no_se_puede_bloquear_a_un_admin(session, admin):
    # La factory guarda un usuario con el rol que se le pase: acá, admin.
    otro_admin = guardar_usuario_comun(session, admin.rol_id)

    with pytest.raises(ReglaDeNegocioError, match=NO_A_UN_ADMIN):
        otro_admin.bloquear(admin, MOTIVO, AL_BLOQUEAR)

    assert not otro_admin.bloqueado
    assert otro_admin.sanciones == []


def test_un_admin_no_puede_bloquearse_a_si_mismo(admin):
    with pytest.raises(ReglaDeNegocioError, match=NO_A_UN_ADMIN):
        admin.bloquear(admin, MOTIVO, AL_BLOQUEAR)

    assert not admin.bloqueado


def test_no_se_bloquea_dos_veces(usuario, admin):
    primera = usuario.bloquear(admin, MOTIVO, AL_BLOQUEAR)

    with pytest.raises(
        ReglaDeNegocioError, match='El usuario ya está bloqueado'
    ):
        usuario.bloquear(admin, 'Otro motivo', MAS_TARDE)

    assert usuario.sanciones == [primera]


def test_desbloquear_cierra_la_sancion_y_quita_el_bloqueo(usuario, admin):
    sancion = usuario.bloquear(admin, MOTIVO, AL_BLOQUEAR)

    usuario.desbloquear(sancion, AL_DESBLOQUEAR)

    assert not usuario.bloqueado
    assert sancion.hasta == AL_DESBLOQUEAR
    assert not sancion.activa()


def test_no_se_cierra_dos_veces_la_misma_sancion(usuario, admin):
    sancion = usuario.bloquear(admin, MOTIVO, AL_BLOQUEAR)
    usuario.desbloquear(sancion, AL_DESBLOQUEAR)

    with pytest.raises(
        ReglaDeNegocioError, match='La sanción ya estaba cerrada'
    ):
        usuario.desbloquear(sancion, MAS_TARDE)

    # La fecha de fin es la del primer desbloqueo.
    assert sancion.hasta == AL_DESBLOQUEAR


def test_volver_a_bloquear_suma_otra_sancion_al_historial(usuario, admin):
    primera = usuario.bloquear(admin, MOTIVO, AL_BLOQUEAR)
    usuario.desbloquear(primera, AL_DESBLOQUEAR)

    segunda = usuario.bloquear(admin, 'Volvió a insultar', MAS_TARDE)

    assert usuario.sanciones == [primera, segunda]
    assert not primera.activa()
    assert segunda.activa()
    assert usuario.bloqueado

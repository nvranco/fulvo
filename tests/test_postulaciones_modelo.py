from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from fulvo.errores import ReglaDeNegocioError
from fulvo.models import (
    EstadoPartido,
    EstadoPostulacion,
    Postulacion,
    ahora_argentina,
)
from tests.factories import guardar_partido, guardar_usuario_comun

CUPOS = 2
NO_ABIERTO = 'El partido no está abierto'
TERMINADO = 'El partido ya se jugó o fue cancelado'
EMPEZADO = 'El partido ya empezó'


@pytest.fixture
def partido(session, usuario):
    """Partido abierto de `usuario`, con 2 cupos y dentro de una semana."""
    return guardar_partido(session, usuario, cupos_faltantes=CUPOS)


@pytest.fixture
def ahora():
    return ahora_argentina()


@pytest.fixture
def postulacion(partido, otro_usuario, ahora):
    """Postulación en espera de `otro_usuario` al partido de la fixture."""
    return partido.postular(otro_usuario, ahora)


def test_postular_crea_una_postulacion_en_espera(
    session, partido, otro_usuario, ahora
):
    postulacion = partido.postular(otro_usuario, ahora)
    session.commit()

    assert postulacion.id is not None
    assert postulacion.estado == EstadoPostulacion.en_espera
    assert postulacion.jugador is otro_usuario
    assert postulacion.created_at == ahora
    assert postulacion.respondida_at is None
    assert partido.postulaciones == [postulacion]


@pytest.mark.parametrize(
    'estado',
    [EstadoPartido.completo, EstadoPartido.cancelado, EstadoPartido.jugado],
)
def test_postular_a_un_partido_no_abierto_falla(
    partido, otro_usuario, ahora, estado
):
    partido.estado = estado

    with pytest.raises(ReglaDeNegocioError, match=NO_ABIERTO):
        partido.postular(otro_usuario, ahora)


@pytest.mark.parametrize('minutos_despues_del_inicio', [0, 30])
def test_postular_a_un_partido_que_ya_empezo_falla(
    partido, otro_usuario, minutos_despues_del_inicio
):
    momento = partido.inicio + timedelta(minutes=minutos_despues_del_inicio)

    with pytest.raises(ReglaDeNegocioError, match='El partido ya empezó'):
        partido.postular(otro_usuario, momento)


def test_el_organizador_no_puede_postularse(partido, usuario, ahora):
    with pytest.raises(ReglaDeNegocioError, match='propio partido'):
        partido.postular(usuario, ahora)


def test_no_se_puede_postular_dos_veces(partido, postulacion, otro_usuario):
    with pytest.raises(ReglaDeNegocioError, match='ya se postuló'):
        partido.postular(otro_usuario, ahora_argentina())


def test_no_se_puede_volver_a_postular_despues_de_retirarse(
    partido, postulacion, otro_usuario, ahora
):
    partido.retirar(postulacion, ahora)

    with pytest.raises(ReglaDeNegocioError, match='ya se postuló'):
        partido.postular(otro_usuario, ahora)


def test_la_base_no_deja_dos_postulaciones_del_mismo_jugador(
    session, partido, otro_usuario, ahora
):
    for _ in range(2):
        session.add(
            Postulacion(
                partido_id=partido.id,
                jugador_id=otro_usuario.id,
                created_at=ahora,
            )
        )

    with pytest.raises(IntegrityError):
        session.commit()


def test_aceptar_resta_un_cupo_y_guarda_la_respuesta(
    partido, postulacion, ahora
):
    partido.aceptar(postulacion, ahora)

    assert postulacion.estado == EstadoPostulacion.aceptada
    assert postulacion.respondida_at == ahora
    assert partido.cupos_faltantes == CUPOS - 1
    assert partido.estado == EstadoPartido.abierto


def test_aceptar_el_ultimo_cupo_completa_y_rechaza_a_los_que_esperan(
    session, usuario, partido, ahora
):
    partido.cupos_faltantes = 1
    aceptado, en_espera = (
        partido.postular(guardar_usuario_comun(session, usuario.rol_id), ahora)
        for _ in range(2)
    )

    partido.aceptar(aceptado, ahora)

    assert partido.estado == EstadoPartido.completo
    assert partido.cupos_faltantes == 0
    assert en_espera.estado == EstadoPostulacion.rechazada
    assert en_espera.respondida_at == ahora


def test_aceptar_en_un_partido_completo_falla(partido, postulacion, ahora):
    partido.estado = EstadoPartido.completo

    with pytest.raises(ReglaDeNegocioError, match=NO_ABIERTO):
        partido.aceptar(postulacion, ahora)


def test_aceptar_una_postulacion_rechazada_falla_sin_tocar_los_cupos(
    partido, postulacion, ahora
):
    partido.rechazar(postulacion, ahora)

    with pytest.raises(ReglaDeNegocioError, match='en espera'):
        partido.aceptar(postulacion, ahora)

    assert partido.cupos_faltantes == CUPOS


def test_rechazar_una_postulacion_en_espera(partido, postulacion, ahora):
    partido.rechazar(postulacion, ahora)

    assert postulacion.estado == EstadoPostulacion.rechazada
    assert postulacion.respondida_at == ahora


def test_rechazar_una_postulacion_aceptada_falla(partido, postulacion, ahora):
    partido.aceptar(postulacion, ahora)

    with pytest.raises(ReglaDeNegocioError, match='en espera'):
        partido.rechazar(postulacion, ahora)


def test_revocar_libera_el_cupo_y_reabre_el_partido(
    partido, postulacion, ahora
):
    partido.cupos_faltantes = 1
    partido.aceptar(postulacion, ahora)
    assert partido.estado == EstadoPartido.completo

    partido.revocar(postulacion, ahora)

    assert postulacion.estado == EstadoPostulacion.revocada
    assert partido.cupos_faltantes == 1
    assert partido.estado == EstadoPartido.abierto


def test_revocar_una_postulacion_en_espera_falla(partido, postulacion, ahora):
    with pytest.raises(ReglaDeNegocioError, match='aceptada'):
        partido.revocar(postulacion, ahora)


def test_retirar_una_postulacion_en_espera_no_cambia_los_cupos(
    partido, postulacion, ahora
):
    partido.retirar(postulacion, ahora)

    assert postulacion.estado == EstadoPostulacion.retirada
    assert postulacion.respondida_at is None
    assert partido.cupos_faltantes == CUPOS


def test_la_baja_de_un_aceptado_libera_el_cupo_y_reabre_el_partido(
    partido, postulacion, ahora
):
    partido.cupos_faltantes = 1
    partido.aceptar(postulacion, ahora)

    partido.retirar(postulacion, ahora)

    assert partido.cupos_faltantes == 1
    assert partido.estado == EstadoPartido.abierto


def test_retirar_dos_veces_falla(partido, postulacion, ahora):
    partido.retirar(postulacion, ahora)

    with pytest.raises(ReglaDeNegocioError, match='en espera o aceptada'):
        partido.retirar(postulacion, ahora)


@pytest.mark.parametrize(
    'estado', [EstadoPartido.jugado, EstadoPartido.cancelado]
)
@pytest.mark.parametrize('accion', ['revocar', 'retirar', 'cancelar'])
def test_con_el_partido_terminado_no_se_puede_revocar_retirar_ni_cancelar(
    partido, postulacion, ahora, estado, accion
):
    partido.aceptar(postulacion, ahora)
    partido.estado = estado
    hacer = {
        'revocar': lambda: partido.revocar(postulacion, ahora),
        'retirar': lambda: partido.retirar(postulacion, ahora),
        'cancelar': lambda: partido.cancelar(ahora),
    }[accion]

    with pytest.raises(ReglaDeNegocioError, match=TERMINADO):
        hacer()


@pytest.mark.parametrize('minutos_despues_del_inicio', [0, 30])
@pytest.mark.parametrize(
    ('accion', 'estado_postulacion'),
    [
        ('aceptar', EstadoPostulacion.en_espera),
        ('rechazar', EstadoPostulacion.en_espera),
        ('retirar', EstadoPostulacion.en_espera),
        ('retirar', EstadoPostulacion.aceptada),
        ('revocar', EstadoPostulacion.aceptada),
        ('cancelar', EstadoPostulacion.aceptada),
    ],
    ids=['aceptar', 'rechazar', 'retirarse', 'bajarse', 'revocar', 'cancelar'],
)
def test_con_el_partido_empezado_no_cambia_nada(
    partido,
    postulacion,
    accion,
    estado_postulacion,
    minutos_despues_del_inicio,
):
    postulacion.estado = estado_postulacion
    momento = partido.inicio + timedelta(minutes=minutos_despues_del_inicio)
    hacer = {
        'aceptar': lambda: partido.aceptar(postulacion, momento),
        'rechazar': lambda: partido.rechazar(postulacion, momento),
        'retirar': lambda: partido.retirar(postulacion, momento),
        'revocar': lambda: partido.revocar(postulacion, momento),
        'cancelar': lambda: partido.cancelar(momento),
    }[accion]

    with pytest.raises(ReglaDeNegocioError, match=EMPEZADO):
        hacer()

    assert postulacion.estado == estado_postulacion
    assert partido.cupos_faltantes == CUPOS
    assert partido.estado == EstadoPartido.abierto


def test_un_minuto_antes_del_inicio_un_aceptado_todavia_se_puede_bajar(
    partido, postulacion, ahora
):
    partido.aceptar(postulacion, ahora)
    un_minuto_antes = partido.inicio - timedelta(minutes=1)

    partido.retirar(postulacion, un_minuto_antes)

    assert postulacion.estado == EstadoPostulacion.retirada
    assert partido.cupos_faltantes == CUPOS


@pytest.mark.parametrize(
    'estado', [EstadoPartido.abierto, EstadoPartido.completo]
)
def test_cancelar_un_partido_en_juego(partido, ahora, estado):
    partido.estado = estado

    partido.cancelar(ahora)

    assert partido.estado == EstadoPartido.cancelado


@pytest.mark.parametrize(
    ('estado_postulacion', 'estado_partido', 'visible'),
    [
        (EstadoPostulacion.en_espera, EstadoPartido.abierto, False),
        (EstadoPostulacion.aceptada, EstadoPartido.abierto, True),
        (EstadoPostulacion.aceptada, EstadoPartido.completo, True),
        (EstadoPostulacion.aceptada, EstadoPartido.jugado, True),
        (EstadoPostulacion.aceptada, EstadoPartido.cancelado, False),
        (EstadoPostulacion.retirada, EstadoPartido.abierto, False),
        (EstadoPostulacion.revocada, EstadoPartido.abierto, False),
    ],
)
def test_el_whatsapp_se_ve_solo_aceptada_y_sin_cancelar(
    partido, postulacion, estado_postulacion, estado_partido, visible
):
    postulacion.estado = estado_postulacion
    partido.estado = estado_partido

    assert postulacion.whatsapp_visible() is visible

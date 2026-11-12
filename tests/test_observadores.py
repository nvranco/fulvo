from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from fulvo.eventos import EventoPartido, TipoEvento
from fulvo.models import Notificacion, TipoNotificacion, ahora_argentina
from fulvo.observadores import (
    FabricaNotificaciones,
    NotificadorPartido,
    describir_partido,
)
from tests.factories import guardar_partido, guardar_usuario_comun

INICIO = datetime(2030, 11, 14, 20, 0)


@pytest.fixture
def partido(session, usuario):
    """Partido de `usuario` del 14/11/2030 a las 20, con su notificador."""
    partido = guardar_partido(
        session, usuario, inicio=INICIO, cupos_faltantes=2
    )
    partido.agregar_observador(NotificadorPartido(session))
    return partido


@pytest.fixture
def jugador(session, usuario):
    return guardar_usuario_comun(session, usuario.rol_id, nombre='Beto')


@pytest.fixture
def postulacion(partido, jugador):
    return partido.postular(jugador, ahora_argentina())


def notificaciones_de(session, usuario) -> list[Notificacion]:
    """Notificaciones del usuario, en el orden en que se crearon.

    La consulta hace autoflush: incluye las que todavía no se confirmaron.
    """
    return list(
        session.scalars(
            select(Notificacion)
            .where(Notificacion.usuario_id == usuario.id)
            .order_by(Notificacion.id)
        )
    )


def tipos_de(session, usuario) -> list[TipoNotificacion]:
    return [n.tipo for n in notificaciones_de(session, usuario)]


def test_describir_partido_muestra_dia_hora_y_complejo(partido):
    esperado = f'14/11 a las 20:00 en {partido.complejo.nombre}'

    assert describir_partido(partido) == esperado


def test_hay_una_plantilla_por_cada_tipo_de_notificacion():
    assert set(FabricaNotificaciones.PLANTILLAS) == set(TipoNotificacion)


@pytest.mark.parametrize(
    ('tipo', 'fragmento'),
    [
        (TipoNotificacion.postulacion_recibida, 'Beto se postuló'),
        (TipoNotificacion.postulacion_aceptada, 'Te aceptaron'),
        (TipoNotificacion.postulacion_rechazada, 'Rechazaron tu postulación'),
        (TipoNotificacion.partido_completo, 'se completó'),
        (TipoNotificacion.postulacion_retirada, 'Beto retiró su postulación'),
        (TipoNotificacion.revocacion, 'te sacó del partido'),
        (TipoNotificacion.partido_cancelado, 'Se canceló el partido'),
        (TipoNotificacion.votaciones_pendientes, 'votaciones pendientes'),
    ],
)
def test_la_fabrica_arma_cada_tipo_con_su_texto(
    partido, postulacion, usuario, tipo, fragmento
):
    notificacion = FabricaNotificaciones().crear(tipo, usuario, postulacion)

    assert fragmento in notificacion.mensaje
    assert describir_partido(partido) in notificacion.mensaje
    assert notificacion.tipo == tipo
    assert notificacion.usuario_id == usuario.id
    assert notificacion.referencia_tipo == 'postulacion'
    assert notificacion.referencia_id == postulacion.id
    assert notificacion.leida is False


def test_con_un_partido_la_referencia_es_el_partido(partido, usuario):
    notificacion = FabricaNotificaciones().crear(
        TipoNotificacion.partido_cancelado, usuario, partido
    )

    assert notificacion.referencia_tipo == 'partido'
    assert notificacion.referencia_id == partido.id
    assert notificacion.mensaje == (
        f'Se canceló el partido del {describir_partido(partido)}.'
    )


def test_la_aceptacion_no_lleva_ningun_whatsapp(postulacion, usuario, jugador):
    notificacion = FabricaNotificaciones().crear(
        TipoNotificacion.postulacion_aceptada, jugador, postulacion
    )

    assert usuario.whatsapp not in notificacion.mensaje
    assert jugador.whatsapp not in notificacion.mensaje


def test_la_fabrica_no_guarda_la_notificacion(session, partido, usuario):
    notificacion = FabricaNotificaciones().crear(
        TipoNotificacion.partido_cancelado, usuario, partido
    )

    assert notificacion not in session


def test_postularse_avisa_al_organizador_con_la_postulacion(
    session, usuario, postulacion
):
    avisos = notificaciones_de(session, usuario)

    assert [a.tipo for a in avisos] == [TipoNotificacion.postulacion_recibida]
    # La postulación recién creada ya tiene id gracias al flush.
    assert avisos[0].referencia_tipo == 'postulacion'
    assert avisos[0].referencia_id == postulacion.id


@pytest.mark.parametrize(
    ('accion', 'tipo'),
    [
        ('aceptar', TipoNotificacion.postulacion_aceptada),
        ('rechazar', TipoNotificacion.postulacion_rechazada),
    ],
)
def test_responder_una_postulacion_avisa_al_jugador(
    session, partido, postulacion, accion, tipo
):
    responder = getattr(partido, accion)  # partido.aceptar o partido.rechazar

    responder(postulacion, ahora_argentina())

    assert tipos_de(session, postulacion.jugador) == [tipo]


def test_revocar_avisa_al_jugador(session, partido, postulacion, jugador):
    ahora = ahora_argentina()
    partido.aceptar(postulacion, ahora)

    partido.revocar(postulacion, ahora)

    assert tipos_de(session, jugador) == [
        TipoNotificacion.postulacion_aceptada,
        TipoNotificacion.revocacion,
    ]


@pytest.mark.parametrize('aceptada', [False, True])
def test_retirarse_o_bajarse_avisa_al_organizador(
    session, partido, postulacion, usuario, aceptada
):
    if aceptada:
        partido.aceptar(postulacion, ahora_argentina())

    partido.retirar(postulacion)

    assert tipos_de(session, usuario) == [
        TipoNotificacion.postulacion_recibida,
        TipoNotificacion.postulacion_retirada,
    ]


def test_completar_avisa_a_cada_postulante_que_quedo_afuera(
    session, usuario, partido
):
    ahora = ahora_argentina()
    partido.cupos_faltantes = 1
    jugadores = [guardar_usuario_comun(session, usuario.rol_id) for _ in '123']
    aceptada, *afuera = (partido.postular(j, ahora) for j in jugadores)

    partido.aceptar(aceptada, ahora)

    assert tipos_de(session, jugadores[0]) == [
        TipoNotificacion.postulacion_aceptada
    ]
    for postulacion in afuera:
        avisos = notificaciones_de(session, postulacion.jugador)
        assert [a.tipo for a in avisos] == [TipoNotificacion.partido_completo]
        assert avisos[0].referencia_id == postulacion.id


def test_cancelar_avisa_solo_a_los_que_esperaban_y_a_los_aceptados(
    session, usuario, partido
):
    ahora = ahora_argentina()
    aceptado, en_espera, rechazado, retirado = (
        guardar_usuario_comun(session, usuario.rol_id) for _ in '1234'
    )
    partido.aceptar(partido.postular(aceptado, ahora), ahora)
    partido.postular(en_espera, ahora)
    partido.rechazar(partido.postular(rechazado, ahora), ahora)
    partido.retirar(partido.postular(retirado, ahora))

    partido.cancelar()

    for avisado in (aceptado, en_espera):
        avisos = notificaciones_de(session, avisado)
        assert avisos[-1].tipo == TipoNotificacion.partido_cancelado
        assert avisos[-1].referencia_tipo == 'partido'
    for sin_aviso in (rechazado, retirado, usuario):
        assert TipoNotificacion.partido_cancelado not in tipos_de(
            session, sin_aviso
        )


def test_el_pase_a_jugado_avisa_las_votaciones_solo_a_los_participantes(
    session, usuario, partido, jugador
):
    ahora = ahora_argentina()
    en_espera = guardar_usuario_comun(session, usuario.rol_id)
    partido.aceptar(partido.postular(jugador, ahora), ahora)
    partido.postular(en_espera, ahora)

    partido.actualizar_estado(partido.fin() + timedelta(minutes=1))

    for participante in (usuario, jugador):
        aviso = notificaciones_de(session, participante)[-1]
        assert aviso.tipo == TipoNotificacion.votaciones_pendientes
        assert aviso.referencia_tipo == 'partido'
        assert aviso.referencia_id == partido.id
    assert TipoNotificacion.votaciones_pendientes not in tipos_de(
        session, en_espera
    )


def test_un_evento_sin_notificacion_no_crea_nada(session, partido):
    NotificadorPartido(session).actualizar(
        EventoPartido(TipoEvento.no_show_marcado, partido)
    )

    assert list(session.scalars(select(Notificacion))) == []


def test_si_la_ruta_no_confirma_no_queda_ninguna_notificacion(
    session, usuario, postulacion
):
    # El notificador solo suma las notificaciones a la sesión: sin commit,
    # un rollback las descarta junto con la postulación que las originó.
    session.rollback()

    assert notificaciones_de(session, usuario) == []

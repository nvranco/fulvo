from datetime import timedelta

import pytest
from sqlalchemy import select

from fulvo.models import (
    EstadoPartido,
    EstadoVotacion,
    Votacion,
    ahora_argentina,
)
from fulvo.observadores import ProcesadorPostPartido
from tests.factories import guardar_partido, guardar_usuario_comun


@pytest.fixture
def partido(session, usuario):
    """Partido de `usuario` con 3 cupos y el procesador ya sumado."""
    partido = guardar_partido(session, usuario, cupos_faltantes=3)
    partido.agregar_observador(ProcesadorPostPartido(session))
    return partido


@pytest.fixture
def jugadores(session, usuario, partido):
    """Dos jugadores aceptados en el partido de la fixture."""
    ahora = ahora_argentina()
    aceptados = [guardar_usuario_comun(session, usuario.rol_id) for _ in '12']
    for jugador in aceptados:
        partido.aceptar(partido.postular(jugador, ahora), ahora)
    return aceptados


def jugar(session, partido) -> None:
    """Pasa el partido a jugado, como si se lo consultara después del fin.

    El `flush` manda las votaciones nuevas a la base, sin confirmarlas:
    SQLAlchemy no carga las relaciones de un objeto que todavía no se mandó,
    y los tests leen el receptor de cada votación.
    """
    partido.actualizar_estado(partido.fin() + timedelta(minutes=1))
    session.flush()


def receptores(usuario) -> list:
    """A quién vota el usuario, en el orden en que se crearon los votos."""
    return [votacion.receptor() for votacion in usuario.votaciones]


def todas_las_votaciones(session) -> list[Votacion]:
    return list(session.scalars(select(Votacion).order_by(Votacion.id)))


def test_al_jugarse_cada_participante_suma_un_partido_jugado(
    session, usuario, partido, jugadores
):
    en_espera = guardar_usuario_comun(session, usuario.rol_id)
    partido.postular(en_espera, ahora_argentina())

    jugar(session, partido)

    assert [p.partidos_jugados for p in (usuario, *jugadores)] == [1, 1, 1]
    assert en_espera.partidos_jugados == 0


def test_al_jugarse_cada_participante_vota_a_los_demas_y_al_complejo(
    session, usuario, partido, jugadores
):
    primero, segundo = jugadores

    jugar(session, partido)

    assert receptores(usuario) == [primero, segundo, partido.complejo]
    assert receptores(primero) == [usuario, segundo, partido.complejo]
    assert receptores(segundo) == [usuario, primero, partido.complejo]


def test_las_votaciones_nacen_pendientes_y_sin_estrellas(
    session, partido, jugadores
):
    jugar(session, partido)

    # 3 participantes: cada uno vota a los otros 2 y al complejo.
    participantes = len(jugadores) + 1
    votaciones = todas_las_votaciones(session)
    assert len(votaciones) == participantes * participantes
    for votacion in votaciones:
        assert votacion.estado == EstadoVotacion.pendiente
        assert votacion.estrellas is None
        assert votacion.emitida_at is None
        assert votacion.partido_id == partido.id


def test_sin_aceptados_el_organizador_no_suma_el_partido_ni_vota(
    session, usuario, partido
):
    # Nadie se sumó: el partido pasa a jugado, pero no hay a quién votar
    # (decisión del equipo del 2026-11-14).
    jugar(session, partido)

    assert partido.estado == EstadoPartido.jugado
    assert usuario.partidos_jugados == 0
    assert todas_las_votaciones(session) == []


def test_consultar_dos_veces_un_partido_terminado_no_duplica_nada(
    session, usuario, partido, jugadores
):
    jugar(session, partido)

    jugar(session, partido)

    assert usuario.partidos_jugados == 1
    participantes = len(jugadores) + 1
    votaciones = todas_las_votaciones(session)
    assert len(votaciones) == participantes * participantes


def test_el_procesador_no_hace_nada_con_los_demas_eventos(
    session, usuario, partido, jugadores
):
    # Postular, aceptar y cancelar emiten eventos, pero ninguno es suyo.
    partido.cancelar(ahora_argentina())

    assert usuario.partidos_jugados == 0
    assert todas_las_votaciones(session) == []


def test_si_la_ruta_no_confirma_no_queda_ninguna_votacion(
    session, usuario, partido, jugadores
):
    session.commit()
    jugar(session, partido)

    # Como el notificador, el procesador solo suma cambios a la sesión: sin
    # commit, el rollback los descarta junto con el pase a jugado.
    session.rollback()

    assert todas_las_votaciones(session) == []
    assert usuario.partidos_jugados == 0


def test_el_no_show_le_resta_el_partido_jugado_y_le_suma_un_cero(
    session, partido, jugadores
):
    ausente = jugadores[0]
    jugar(session, partido)

    partido.marcar_no_show(partido.postulaciones[0])

    assert ausente.partidos_jugados == 0
    assert ausente.puntuacion_promedio == 0
    assert ausente.cantidad_puntuaciones == 1


def test_el_no_show_borra_las_votaciones_pendientes_del_ausente_y_hacia_el(
    session, usuario, partido, jugadores
):
    ausente, presente = jugadores
    jugar(session, partido)

    partido.marcar_no_show(partido.postulaciones[0])

    assert ausente.votaciones == []
    assert receptores(usuario) == [presente, partido.complejo]
    assert receptores(presente) == [usuario, partido.complejo]
    # También en la base: quedan las de los dos presentes, que se
    # votan entre sí y al complejo.
    presentes = [usuario, presente]
    assert len(todas_las_votaciones(session)) == 2 * len(presentes)
    assert ausente.deuda() == 0


def test_el_no_show_no_toca_las_votaciones_ya_emitidas(
    session, usuario, partido, jugadores
):
    ausente, presente = jugadores
    jugar(session, partido)
    al_ausente = usuario.votaciones[0]
    al_ausente.emitir(4, ahora_argentina())
    del_ausente = ausente.votaciones[0]
    del_ausente.emitir(5, ahora_argentina())

    partido.marcar_no_show(partido.postulaciones[0])

    assert al_ausente in todas_las_votaciones(session)
    assert del_ausente in todas_las_votaciones(session)
    # El voto que ya tenía y el 0 del no-show.
    votos_del_ausente = [al_ausente.estrellas, 0]
    assert ausente.puntuacion_promedio == sum(votos_del_ausente) / 2
    assert ausente.cantidad_puntuaciones == len(votos_del_ausente)
    assert usuario.puntuacion_promedio == del_ausente.estrellas


def test_anular_el_no_show_le_devuelve_el_partido_y_le_quita_el_cero(
    session, partido, jugadores
):
    ausente = jugadores[0]
    jugar(session, partido)
    postulacion = partido.postulaciones[0]
    partido.marcar_no_show(postulacion)

    partido.quitar_no_show(postulacion)

    assert ausente.partidos_jugados == 1
    assert ausente.puntuacion_promedio is None
    assert ausente.cantidad_puntuaciones == 0


def test_anular_el_no_show_repone_las_votaciones_del_ausente_y_hacia_el(
    session, usuario, partido, jugadores
):
    ausente, presente = jugadores
    jugar(session, partido)
    postulacion = partido.postulaciones[0]
    partido.marcar_no_show(postulacion)

    partido.quitar_no_show(postulacion)
    session.flush()

    # Las repuestas van al final de cada lista: primero el complejo del
    # ausente, y después las de cada presente con él.
    assert receptores(ausente) == [partido.complejo, usuario, presente]
    assert receptores(usuario) == [presente, partido.complejo, ausente]
    assert receptores(presente) == [usuario, partido.complejo, ausente]
    participantes = len(jugadores) + 1
    votaciones = todas_las_votaciones(session)
    assert len(votaciones) == participantes * participantes
    assert {v.estado for v in votaciones} == {EstadoVotacion.pendiente}
    assert ausente.deuda() == 1


def test_anular_el_no_show_no_repite_las_votaciones_ya_emitidas(
    session, usuario, partido, jugadores
):
    ausente = jugadores[0]
    jugar(session, partido)
    al_ausente = usuario.votaciones[0]
    al_ausente.emitir(4, ahora_argentina())
    del_ausente = ausente.votaciones[0]
    del_ausente.emitir(5, ahora_argentina())
    postulacion = partido.postulaciones[0]
    partido.marcar_no_show(postulacion)

    partido.quitar_no_show(postulacion)
    session.flush()

    hacia_el = [v for v in usuario.votaciones if v.receptor() is ausente]
    de_el = [v for v in ausente.votaciones if v.receptor() is usuario]
    assert hacia_el == [al_ausente]
    assert de_el == [del_ausente]
    participantes = len(jugadores) + 1
    assert len(todas_las_votaciones(session)) == participantes * participantes


def test_anular_un_no_show_no_repone_votaciones_con_otro_ausente(
    session, usuario, partido, jugadores
):
    primero, segundo = jugadores
    jugar(session, partido)
    del_primero, del_segundo = partido.postulaciones
    partido.marcar_no_show(del_primero)
    partido.marcar_no_show(del_segundo)

    partido.quitar_no_show(del_primero)
    session.flush()

    assert receptores(primero) == [partido.complejo, usuario]
    assert receptores(usuario) == [partido.complejo, primero]
    assert segundo.votaciones == []
    assert segundo.partidos_jugados == 0

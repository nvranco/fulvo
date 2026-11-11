from dataclasses import FrozenInstanceError
from datetime import timedelta

import pytest

from fulvo.errores import ReglaDeNegocioError
from fulvo.eventos import EventoPartido, ObservadorPartido, TipoEvento
from fulvo.models import Partido, ahora_argentina
from tests.factories import guardar_partido, guardar_usuario_comun


class ObservadorDePrueba(ObservadorPartido):
    """Observador que solo anota los eventos, para revisarlos en los tests."""

    def __init__(self) -> None:
        self.eventos: list[EventoPartido] = []

    def actualizar(self, evento: EventoPartido) -> None:
        self.eventos.append(evento)

    def tipos(self) -> list[TipoEvento]:
        return [evento.tipo for evento in self.eventos]


@pytest.fixture
def partido(session, usuario):
    """Partido abierto de `usuario`, con 2 cupos y dentro de una semana."""
    return guardar_partido(session, usuario, cupos_faltantes=2)


@pytest.fixture
def observador(partido):
    """Observador de prueba ya sumado al partido de la fixture."""
    observador = ObservadorDePrueba()
    partido.agregar_observador(observador)
    return observador


def nuevo_jugador(session, usuario):
    return guardar_usuario_comun(session, usuario.rol_id)


def test_no_se_puede_crear_un_observador_sin_actualizar():
    class Incompleto(ObservadorPartido):
        pass

    with pytest.raises(TypeError):
        Incompleto()


def test_el_evento_no_se_puede_modificar(partido):
    evento = EventoPartido(TipoEvento.partido_cancelado, partido)

    with pytest.raises(FrozenInstanceError):
        evento.tipo = TipoEvento.partido_jugado


def test_un_partido_leido_de_la_base_arranca_sin_observadores(
    session, partido, observador
):
    # Se saca el partido de la sesión para que `get` lo lea de nuevo de la
    # base: ese objeto no pasa por `__init__`, sino por `@reconstructor`.
    partido_id = partido.id
    session.expunge_all()

    leido = session.get(Partido, partido_id)

    assert leido is not partido
    assert leido.observadores == []


def test_todos_los_observadores_reciben_el_mismo_evento(
    session, usuario, otro_usuario, partido, observador
):
    otro_observador = ObservadorDePrueba()
    partido.agregar_observador(otro_observador)

    partido.postular(otro_usuario, ahora_argentina())

    assert len(observador.eventos) == 1
    assert otro_observador.eventos[0] is observador.eventos[0]


def test_un_observador_quitado_deja_de_recibir_eventos(
    otro_usuario, partido, observador
):
    partido.quitar_observador(observador)

    partido.postular(otro_usuario, ahora_argentina())

    assert observador.eventos == []


def test_postular_emite_postulacion_recibida_con_la_postulacion(
    otro_usuario, partido, observador
):
    postulacion = partido.postular(otro_usuario, ahora_argentina())

    evento = observador.eventos[0]
    assert evento.tipo == TipoEvento.postulacion_recibida
    assert evento.partido is partido
    assert evento.postulacion is postulacion


def test_una_accion_rechazada_no_emite_eventos(usuario, partido, observador):
    with pytest.raises(ReglaDeNegocioError):
        partido.postular(usuario, ahora_argentina())

    assert observador.eventos == []


def test_aceptar_emite_postulacion_aceptada(otro_usuario, partido, observador):
    ahora = ahora_argentina()
    postulacion = partido.postular(otro_usuario, ahora)

    partido.aceptar(postulacion, ahora)

    assert observador.tipos() == [
        TipoEvento.postulacion_recibida,
        TipoEvento.postulacion_aceptada,
    ]


def test_completar_el_partido_emite_un_aviso_por_cada_rechazado(
    session, usuario, partido, observador
):
    ahora = ahora_argentina()
    partido.cupos_faltantes = 1
    primero, segundo, tercero = (
        partido.postular(nuevo_jugador(session, usuario), ahora)
        for _ in range(3)
    )
    observador.eventos.clear()

    partido.aceptar(primero, ahora)

    assert observador.tipos() == [
        TipoEvento.postulacion_aceptada,
        TipoEvento.partido_completo,
        TipoEvento.partido_completo,
    ]
    assert [e.postulacion for e in observador.eventos[1:]] == [
        segundo,
        tercero,
    ]


def test_rechazar_emite_postulacion_rechazada(
    otro_usuario, partido, observador
):
    ahora = ahora_argentina()
    postulacion = partido.postular(otro_usuario, ahora)

    partido.rechazar(postulacion, ahora)

    assert observador.tipos()[-1] == TipoEvento.postulacion_rechazada


def test_revocar_emite_revocacion(otro_usuario, partido, observador):
    ahora = ahora_argentina()
    postulacion = partido.postular(otro_usuario, ahora)
    partido.aceptar(postulacion, ahora)

    partido.revocar(postulacion, ahora)

    assert observador.tipos()[-1] == TipoEvento.revocacion


@pytest.mark.parametrize('aceptada', [False, True])
def test_retirar_o_bajarse_emite_postulacion_retirada(
    otro_usuario, partido, observador, aceptada
):
    ahora = ahora_argentina()
    postulacion = partido.postular(otro_usuario, ahora)
    if aceptada:
        partido.aceptar(postulacion, ahora)

    partido.retirar(postulacion)

    assert observador.tipos()[-1] == TipoEvento.postulacion_retirada
    assert observador.eventos[-1].postulacion is postulacion


def test_cancelar_emite_partido_cancelado_sin_postulacion(partido, observador):
    partido.cancelar()

    assert observador.tipos() == [TipoEvento.partido_cancelado]
    assert observador.eventos[0].postulacion is None


def test_el_pase_a_jugado_emite_partido_jugado_una_sola_vez(
    partido, observador
):
    despues_del_fin = partido.fin() + timedelta(minutes=1)

    partido.actualizar_estado(despues_del_fin)
    partido.actualizar_estado(despues_del_fin)

    assert observador.tipos() == [TipoEvento.partido_jugado]

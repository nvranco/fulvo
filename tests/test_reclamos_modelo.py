from datetime import datetime

import pytest

from fulvo.errores import ReglaDeNegocioError
from fulvo.models import (
    Complejo,
    EstadoReclamo,
    EstadoVotacion,
    Reclamo,
    TipoObjetivo,
)
from tests.factories import guardar_partido_jugado

MOTIVO = 'Fui al partido y jugué todo'
RESOLUCION = 'El organizador confirmó que fue'
AL_ABRIR = datetime(2026, 11, 12, 10, 0)
AL_RESOLVER = datetime(2026, 11, 13, 18, 0)
YA_CERRADO = 'El reclamo ya fue resuelto o rechazado'


@pytest.fixture
def jugado(session, usuario, otro_usuario):
    """Partido jugado de `usuario`, con `otro_usuario` aceptado."""
    return guardar_partido_jugado(session, usuario, [otro_usuario])


@pytest.fixture
def postulacion(jugado):
    """La postulación de `otro_usuario` en el partido jugado."""
    return jugado.postulaciones[0]


@pytest.fixture
def denuncia(session, usuario, otro_usuario):
    """Denuncia guardada de `usuario` contra `otro_usuario`."""
    return guardar(
        session,
        Reclamo.abrir(
            usuario, TipoObjetivo.usuario, otro_usuario, MOTIVO, AL_ABRIR
        ),
    )


@pytest.fixture(params=['usuario', 'complejo'])
def puntuable(request, session, usuario):
    """Un usuario o un complejo: los dos se puntúan con el mismo cálculo."""
    if request.param == 'usuario':
        return usuario
    return session.get(Complejo, 1)


def voto_de(emisor, receptor):
    """La votación del emisor hacia `receptor`."""
    return next(v for v in emisor.votaciones if v.receptor() is receptor)


def guardar(session, reclamo: Reclamo) -> Reclamo:
    """Guarda el reclamo, para que tenga id (lo usa la sanción)."""
    session.add(reclamo)
    session.commit()
    return reclamo


def test_quitar_un_voto_recalcula_el_promedio(puntuable):
    votos = (5, 3)
    for estrellas in votos:
        puntuable.registrar_puntuacion(estrellas)

    puntuable.quitar_puntuacion(votos[1])

    assert puntuable.puntuacion_promedio == votos[0]
    assert puntuable.cantidad_puntuaciones == 1


def test_quitar_el_unico_voto_deja_el_promedio_vacio(puntuable):
    puntuable.registrar_puntuacion(0)

    puntuable.quitar_puntuacion(0)

    assert puntuable.puntuacion_promedio is None
    assert puntuable.cantidad_puntuaciones == 0


def test_quitar_no_show_saca_la_marca(jugado, postulacion):
    jugado.marcar_no_show(postulacion)

    postulacion.quitar_no_show()

    assert postulacion.no_show is False


def test_no_se_quita_un_no_show_que_no_esta(postulacion):
    with pytest.raises(
        ReglaDeNegocioError, match='no tiene un no-show marcado'
    ):
        postulacion.quitar_no_show()


def test_los_presentes_son_los_participantes_sin_no_show(
    jugado, usuario, otro_usuario, postulacion
):
    assert jugado.presentes() == [usuario, otro_usuario]

    jugado.marcar_no_show(postulacion)

    assert jugado.presentes() == [usuario]


def test_anular_una_votacion_la_saca_del_promedio(
    jugado, usuario, otro_usuario
):
    voto = voto_de(usuario, otro_usuario)
    estrellas = 4
    voto.emitir(estrellas, AL_ABRIR)

    voto.anular()

    assert voto.estado == EstadoVotacion.anulada
    assert voto.estrellas == estrellas
    assert otro_usuario.puntuacion_promedio is None
    assert otro_usuario.cantidad_puntuaciones == 0


def test_no_se_anula_una_votacion_pendiente(jugado, usuario, otro_usuario):
    voto = voto_de(usuario, otro_usuario)

    with pytest.raises(
        ReglaDeNegocioError, match='Solo se puede anular una votación emitida'
    ):
        voto.anular()


def test_no_se_anula_dos_veces(jugado, usuario, otro_usuario):
    voto = voto_de(usuario, otro_usuario)
    voto.emitir(4, AL_ABRIR)
    voto.anular()

    with pytest.raises(
        ReglaDeNegocioError, match='Solo se puede anular una votación emitida'
    ):
        voto.anular()

    assert otro_usuario.cantidad_puntuaciones == 0


def test_abrir_un_reclamo_por_un_no_show_propio(
    jugado, otro_usuario, postulacion
):
    jugado.marcar_no_show(postulacion)

    reclamo = Reclamo.abrir(
        otro_usuario, TipoObjetivo.no_show, postulacion, MOTIVO, AL_ABRIR
    )

    assert reclamo.autor_id == otro_usuario.id
    assert reclamo.tipo_objetivo == TipoObjetivo.no_show
    assert reclamo.objetivo_id == postulacion.id
    assert reclamo.motivo == MOTIVO
    assert reclamo.created_at == AL_ABRIR
    assert reclamo.estado == EstadoReclamo.abierto
    assert reclamo.resolucion is None
    assert reclamo.resuelto_por_id is None
    assert reclamo.resuelto_at is None


def test_no_se_reclama_el_no_show_de_otro(jugado, usuario, postulacion):
    jugado.marcar_no_show(postulacion)

    with pytest.raises(
        ReglaDeNegocioError, match='Solo podés reclamar un no-show tuyo'
    ):
        Reclamo.abrir(
            usuario, TipoObjetivo.no_show, postulacion, MOTIVO, AL_ABRIR
        )


def test_no_se_reclama_un_no_show_que_no_esta_marcado(
    otro_usuario, postulacion
):
    with pytest.raises(
        ReglaDeNegocioError, match='no tiene un no-show marcado'
    ):
        Reclamo.abrir(
            otro_usuario, TipoObjetivo.no_show, postulacion, MOTIVO, AL_ABRIR
        )


def test_abrir_un_reclamo_por_una_votacion_recibida(
    jugado, usuario, otro_usuario
):
    voto = voto_de(usuario, otro_usuario)
    voto.emitir(1, AL_ABRIR)

    reclamo = Reclamo.abrir(
        otro_usuario, TipoObjetivo.votacion, voto, MOTIVO, AL_ABRIR
    )

    assert reclamo.tipo_objetivo == TipoObjetivo.votacion
    assert reclamo.objetivo_id == voto.id


def test_no_se_reclama_una_votacion_que_no_recibio(
    jugado, usuario, otro_usuario
):
    voto = voto_de(otro_usuario, usuario)
    voto.emitir(1, AL_ABRIR)

    with pytest.raises(
        ReglaDeNegocioError,
        match='Solo podés reclamar una votación que recibiste',
    ):
        Reclamo.abrir(
            otro_usuario, TipoObjetivo.votacion, voto, MOTIVO, AL_ABRIR
        )


def test_no_se_reclama_una_votacion_pendiente(jugado, usuario, otro_usuario):
    voto = voto_de(usuario, otro_usuario)

    with pytest.raises(
        ReglaDeNegocioError,
        match='Solo se puede reclamar una votación emitida',
    ):
        Reclamo.abrir(
            otro_usuario, TipoObjetivo.votacion, voto, MOTIVO, AL_ABRIR
        )


def test_se_denuncia_a_otro_usuario_o_a_un_complejo(
    session, usuario, otro_usuario
):
    complejo = session.get(Complejo, 1)

    a_usuario = Reclamo.abrir(
        usuario, TipoObjetivo.usuario, otro_usuario, MOTIVO, AL_ABRIR
    )
    a_complejo = Reclamo.abrir(
        usuario, TipoObjetivo.complejo, complejo, MOTIVO, AL_ABRIR
    )

    assert a_usuario.objetivo_id == otro_usuario.id
    assert a_complejo.objetivo_id == complejo.id


def test_nadie_se_denuncia_a_si_mismo(usuario):
    with pytest.raises(
        ReglaDeNegocioError, match='No podés denunciarte a vos mismo'
    ):
        Reclamo.abrir(usuario, TipoObjetivo.usuario, usuario, MOTIVO, AL_ABRIR)


def test_resolver_guarda_la_respuesta_del_admin(admin, denuncia, otro_usuario):
    sancion = denuncia.resolver(admin, RESOLUCION, None, AL_RESOLVER)

    assert sancion is None
    assert denuncia.estado == EstadoReclamo.resuelto
    assert denuncia.resolucion == RESOLUCION
    assert denuncia.resuelto_por_id == admin.id
    assert denuncia.resuelto_at == AL_RESOLVER
    assert not otro_usuario.bloqueado


def test_resolver_una_denuncia_puede_bloquear_al_denunciado(
    admin, denuncia, otro_usuario
):
    sancion = denuncia.resolver(
        admin, RESOLUCION, otro_usuario, AL_RESOLVER, bloquear=True
    )

    assert otro_usuario.bloqueado
    assert sancion.reclamo_id == denuncia.id
    assert sancion.motivo == RESOLUCION
    assert sancion.aplicada_por_id == admin.id
    assert sancion.desde == AL_RESOLVER
    assert denuncia.estado == EstadoReclamo.resuelto


def test_si_no_se_puede_bloquear_el_reclamo_sigue_abierto(
    admin, denuncia, otro_usuario
):
    otro_usuario.bloquear(admin, 'Un bloqueo anterior', AL_ABRIR)

    with pytest.raises(
        ReglaDeNegocioError, match='El usuario ya está bloqueado'
    ):
        denuncia.resolver(
            admin, RESOLUCION, otro_usuario, AL_RESOLVER, bloquear=True
        )

    assert denuncia.estado == EstadoReclamo.abierto
    assert denuncia.resolucion is None


def test_solo_se_bloquea_al_resolver_una_denuncia_a_un_usuario(
    session, admin, usuario
):
    reclamo = guardar(
        session,
        Reclamo.abrir(
            usuario,
            TipoObjetivo.complejo,
            session.get(Complejo, 1),
            MOTIVO,
            AL_ABRIR,
        ),
    )

    with pytest.raises(
        ReglaDeNegocioError,
        match='Solo se puede bloquear al resolver una denuncia a un usuario',
    ):
        reclamo.resolver(admin, RESOLUCION, None, AL_RESOLVER, bloquear=True)

    assert reclamo.estado == EstadoReclamo.abierto


def test_resolver_un_no_show_le_quita_la_marca(
    session, admin, jugado, otro_usuario, postulacion
):
    jugado.marcar_no_show(postulacion)
    reclamo = guardar(
        session,
        Reclamo.abrir(
            otro_usuario, TipoObjetivo.no_show, postulacion, MOTIVO, AL_ABRIR
        ),
    )

    reclamo.resolver(admin, RESOLUCION, postulacion, AL_RESOLVER)

    assert postulacion.no_show is False
    assert reclamo.estado == EstadoReclamo.resuelto


def test_resolver_un_reclamo_por_votacion_la_anula(
    session, admin, jugado, usuario, otro_usuario
):
    voto = voto_de(usuario, otro_usuario)
    voto.emitir(1, AL_ABRIR)
    reclamo = guardar(
        session,
        Reclamo.abrir(
            otro_usuario, TipoObjetivo.votacion, voto, MOTIVO, AL_ABRIR
        ),
    )

    reclamo.resolver(admin, RESOLUCION, voto, AL_RESOLVER)

    assert voto.estado == EstadoVotacion.anulada
    assert otro_usuario.puntuacion_promedio is None


def test_rechazar_no_aplica_ninguna_medida(
    session, admin, jugado, usuario, otro_usuario
):
    voto = voto_de(usuario, otro_usuario)
    voto.emitir(1, AL_ABRIR)
    reclamo = guardar(
        session,
        Reclamo.abrir(
            otro_usuario, TipoObjetivo.votacion, voto, MOTIVO, AL_ABRIR
        ),
    )

    reclamo.rechazar(admin, RESOLUCION, AL_RESOLVER)

    assert reclamo.estado == EstadoReclamo.rechazado
    assert reclamo.resolucion == RESOLUCION
    assert reclamo.resuelto_por_id == admin.id
    assert reclamo.resuelto_at == AL_RESOLVER
    assert voto.estado == EstadoVotacion.emitida
    assert otro_usuario.puntuacion_promedio == 1


@pytest.mark.parametrize('primera', ['resolver', 'rechazar'])
def test_un_reclamo_cerrado_no_se_vuelve_a_responder(admin, denuncia, primera):
    if primera == 'resolver':
        denuncia.resolver(admin, RESOLUCION, None, AL_RESOLVER)
    else:
        denuncia.rechazar(admin, RESOLUCION, AL_RESOLVER)

    with pytest.raises(ReglaDeNegocioError, match=YA_CERRADO):
        denuncia.resolver(admin, 'Otra respuesta', None, AL_RESOLVER)
    with pytest.raises(ReglaDeNegocioError, match=YA_CERRADO):
        denuncia.rechazar(admin, 'Otra respuesta', AL_RESOLVER)

    assert denuncia.resolucion == RESOLUCION

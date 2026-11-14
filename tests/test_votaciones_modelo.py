import pytest
from sqlalchemy.exc import IntegrityError

from fulvo.errores import ReglaDeNegocioError
from fulvo.models import (
    Complejo,
    EstadoPartido,
    EstadoPostulacion,
    EstadoVotacion,
    Votacion,
    ahora_argentina,
)
from fulvo.settings import LIMITE_DEUDA
from tests.factories import (
    guardar_aceptado,
    guardar_partido,
    guardar_partido_jugado,
    guardar_usuario_comun,
)

NO_JUGADO = 'Solo se puede marcar un no-show en un partido jugado'


def deber_partidos(session, usuario, cantidad: int) -> None:
    """Deja al usuario con votaciones pendientes en `cantidad` partidos.

    En cada partido jugado juega con un aceptado, así que le quedan dos
    votos pendientes: al aceptado y al complejo. Sin aceptados no le
    quedaría ninguno: un partido en el que nadie se sumó no deja
    votaciones.
    """
    aceptado = guardar_usuario_comun(session, usuario.rol_id)
    for _ in range(cantidad):
        guardar_partido_jugado(session, usuario, [aceptado])


def voto_de(emisor, receptor) -> Votacion:
    """La votación del emisor hacia `receptor`, un usuario o un complejo."""
    return next(v for v in emisor.votaciones if v.receptor() is receptor)


@pytest.fixture
def jugado(session, usuario, otro_usuario):
    """Partido jugado de `usuario`, con `otro_usuario` como aceptado."""
    return guardar_partido_jugado(session, usuario, aceptados=[otro_usuario])


@pytest.fixture(params=['usuario', 'complejo'])
def puntuable(request, session, usuario):
    """Un usuario o un complejo: los dos se puntúan con el mismo cálculo."""
    if request.param == 'usuario':
        return usuario
    return session.get(Complejo, 1)


def test_sin_votos_no_hay_puntuacion(puntuable):
    assert puntuable.puntuacion_promedio is None
    assert puntuable.cantidad_puntuaciones == 0


def test_el_primer_voto_es_el_promedio(puntuable):
    estrellas = 4

    puntuable.registrar_puntuacion(estrellas)

    assert puntuable.puntuacion_promedio == estrellas
    assert puntuable.cantidad_puntuaciones == 1


def test_cada_voto_recalcula_el_promedio_incluso_uno_de_cero(puntuable):
    votos = (5, 4, 0)

    for estrellas in votos:
        puntuable.registrar_puntuacion(estrellas)

    assert puntuable.puntuacion_promedio == pytest.approx(3)
    assert puntuable.cantidad_puntuaciones == len(votos)


def test_sumar_y_restar_partidos_jugados(usuario):
    usuario.sumar_partido_jugado()
    usuario.sumar_partido_jugado()

    usuario.restar_partido_jugado()

    assert usuario.partidos_jugados == 1


def test_los_participantes_son_el_organizador_y_los_aceptados(
    session, usuario
):
    partido = guardar_partido(session, usuario, cupos_faltantes=3)
    ahora = ahora_argentina()
    aceptado, en_espera, rechazado = (
        guardar_usuario_comun(session, usuario.rol_id) for _ in range(3)
    )
    partido.aceptar(partido.postular(aceptado, ahora), ahora)
    partido.postular(en_espera, ahora)
    partido.rechazar(partido.postular(rechazado, ahora), ahora)

    participantes = partido.participantes()

    assert participantes == [usuario, aceptado]


def test_la_deuda_cuenta_partidos_y_no_votaciones(
    session, usuario, otro_usuario
):
    # Con otro participante, cada partido le deja dos votos pendientes: a
    # `otro_usuario` y al complejo.
    partidos = 2
    for _ in range(partidos):
        guardar_partido_jugado(session, usuario, aceptados=[otro_usuario])

    assert len(usuario.votaciones_pendientes()) == 2 * partidos
    assert usuario.deuda() == partidos


def test_un_partido_sigue_en_la_deuda_hasta_completar_todos_sus_votos(
    session, usuario, otro_usuario, jugado
):
    voto_de(usuario, otro_usuario).emitir(3, ahora_argentina())
    assert usuario.deuda() == 1

    voto_de(usuario, jugado.complejo).emitir(3, ahora_argentina())

    assert usuario.deuda() == 0


@pytest.mark.parametrize(
    ('partidos', 'habilitado'),
    [(0, True), (LIMITE_DEUDA, True), (LIMITE_DEUDA + 1, False)],
)
def test_esta_habilitado_mientras_la_deuda_no_supere_el_limite(
    session, usuario, partidos, habilitado
):
    deber_partidos(session, usuario, partidos)

    assert usuario.deuda() == partidos
    assert usuario.habilitado() is habilitado


def test_exigir_habilitado_sin_deuda_de_mas_no_levanta_nada(session, usuario):
    deber_partidos(session, usuario, LIMITE_DEUDA)

    assert usuario.exigir_habilitado() is None


def test_exigir_habilitado_con_deuda_dice_cuanto_falta(session, usuario):
    deber_partidos(session, usuario, LIMITE_DEUDA + 1)

    with pytest.raises(ReglaDeNegocioError) as error:
        usuario.exigir_habilitado()

    assert str(error.value) == (
        'Tenés votaciones pendientes en 4 partidos y el máximo es 3: '
        'completá las de al menos 1 partido para publicar o postularte '
        '(te faltan 8 votaciones).'
    )


def test_con_dos_partidos_de_mas_el_mensaje_va_en_plural(session, usuario):
    deber_partidos(session, usuario, LIMITE_DEUDA + 2)

    with pytest.raises(ReglaDeNegocioError, match='al menos 2 partidos para'):
        usuario.exigir_habilitado()


def test_con_deuda_de_mas_no_se_puede_postular(session, usuario, otro_usuario):
    deber_partidos(session, otro_usuario, LIMITE_DEUDA + 1)
    partido = guardar_partido(session, usuario)

    with pytest.raises(ReglaDeNegocioError, match='pendientes en 4 partidos'):
        partido.postular(otro_usuario, ahora_argentina())

    assert partido.postulaciones == []


def test_el_receptor_es_el_usuario_o_el_complejo(
    usuario, otro_usuario, jugado
):
    al_jugador, al_complejo = usuario.votaciones

    assert al_jugador.receptor() is otro_usuario
    assert al_complejo.receptor() is jugado.complejo


def test_emitir_guarda_el_voto_y_puntua_al_jugador(
    usuario, otro_usuario, jugado
):
    votacion = voto_de(usuario, otro_usuario)
    ahora = ahora_argentina()
    estrellas = 4

    votacion.emitir(estrellas, ahora)

    assert votacion.estado == EstadoVotacion.emitida
    assert votacion.estrellas == estrellas
    assert votacion.emitida_at == ahora
    assert otro_usuario.puntuacion_promedio == estrellas
    assert otro_usuario.cantidad_puntuaciones == 1


def test_emitir_el_voto_al_complejo_lo_puntua(usuario, jugado):
    votacion = voto_de(usuario, jugado.complejo)
    estrellas = 5

    votacion.emitir(estrellas, ahora_argentina())

    assert jugado.complejo.puntuacion_promedio == estrellas
    assert jugado.complejo.cantidad_puntuaciones == 1


@pytest.mark.parametrize('estrellas', [-1, 6])
def test_emitir_fuera_de_rango_falla_sin_puntuar(
    usuario, otro_usuario, jugado, estrellas
):
    votacion = voto_de(usuario, otro_usuario)

    with pytest.raises(ReglaDeNegocioError, match='van de 0 a 5'):
        votacion.emitir(estrellas, ahora_argentina())

    assert votacion.estado == EstadoVotacion.pendiente
    assert otro_usuario.cantidad_puntuaciones == 0


def test_no_se_puede_emitir_dos_veces(usuario, otro_usuario, jugado):
    votacion = voto_de(usuario, otro_usuario)
    primera = 4
    votacion.emitir(primera, ahora_argentina())

    with pytest.raises(ReglaDeNegocioError, match='ya fue emitida'):
        votacion.emitir(1, ahora_argentina())

    assert votacion.estrellas == primera
    assert otro_usuario.cantidad_puntuaciones == 1


@pytest.mark.parametrize('receptores', ['ninguno', 'los_dos'])
def test_la_base_exige_un_solo_receptor(session, usuario, jugado, receptores):
    # Receptores sin voto en este partido: así lo único que puede fallar es
    # la restricción CHECK, y no la de un voto por receptor.
    tercero = guardar_usuario_comun(session, usuario.rol_id)
    con_receptores = {
        'ninguno': {},
        'los_dos': {
            'receptor_usuario_id': tercero.id,
            'receptor_complejo_id': 2,
        },
    }[receptores]
    usuario.votaciones.append(
        Votacion(
            partido_id=jugado.id,
            emisor_id=usuario.id,
            created_at=ahora_argentina(),
            **con_receptores,
        )
    )

    with pytest.raises(IntegrityError, match='un_solo_receptor'):
        session.commit()


@pytest.mark.parametrize('receptor', ['usuario', 'complejo'])
def test_la_base_no_deja_votar_dos_veces_al_mismo_receptor(
    session, usuario, otro_usuario, jugado, receptor
):
    repetido = {
        'usuario': {'receptor_usuario_id': otro_usuario.id},
        'complejo': {'receptor_complejo_id': jugado.complejo_id},
    }[receptor]
    usuario.votaciones.append(
        Votacion(
            partido_id=jugado.id,
            emisor_id=usuario.id,
            created_at=ahora_argentina(),
            **repetido,
        )
    )

    # Sin distinguir mayúsculas, para que valga con el mensaje de las dos
    # bases: "violates unique constraint" en PostgreSQL (la de los tests) y
    # "UNIQUE constraint failed" en SQLite.
    with pytest.raises(IntegrityError, match='(?i)unique constraint'):
        session.commit()


def test_el_id_de_una_votacion_borrada_no_se_reutiliza(
    session, usuario, otro_usuario, jugado
):
    # Se borra la última votación creada, como puede pasar con un no-show.
    ultima = otro_usuario.votaciones[-1]
    ultimo_id = ultima.id
    otro_usuario.votaciones.remove(ultima)
    session.commit()

    guardar_partido_jugado(session, otro_usuario, [usuario])

    assert otro_usuario.votaciones[-1].id > ultimo_id


def test_marcar_no_show_a_un_aceptado_de_un_partido_jugado(jugado):
    postulacion = jugado.postulaciones[0]

    jugado.marcar_no_show(postulacion)

    assert postulacion.no_show is True


@pytest.mark.parametrize(
    'estado',
    [EstadoPartido.abierto, EstadoPartido.completo, EstadoPartido.cancelado],
)
def test_el_no_show_solo_se_marca_en_un_partido_jugado(
    session, usuario, otro_usuario, estado
):
    partido = guardar_partido(session, usuario, estado=estado)
    postulacion = guardar_aceptado(session, partido, otro_usuario)

    with pytest.raises(ReglaDeNegocioError, match=NO_JUGADO):
        partido.marcar_no_show(postulacion)

    assert postulacion.no_show is False


@pytest.mark.parametrize(
    'estado',
    [
        EstadoPostulacion.en_espera,
        EstadoPostulacion.rechazada,
        EstadoPostulacion.retirada,
        EstadoPostulacion.revocada,
    ],
)
def test_el_no_show_solo_se_marca_a_un_aceptado(jugado, estado):
    postulacion = jugado.postulaciones[0]
    postulacion.estado = estado

    with pytest.raises(ReglaDeNegocioError, match='jugador aceptado'):
        jugado.marcar_no_show(postulacion)

    assert postulacion.no_show is False


def test_no_se_puede_marcar_dos_veces_el_no_show(jugado):
    postulacion = jugado.postulaciones[0]
    jugado.marcar_no_show(postulacion)

    with pytest.raises(ReglaDeNegocioError, match='ya estaba marcado'):
        jugado.marcar_no_show(postulacion)

from datetime import datetime, timedelta
from http import HTTPStatus

import pytest
from freezegun import freeze_time

from fulvo.models import (
    HORA_ARGENTINA,
    Complejo,
    EstadoPostulacion,
    ahora_argentina,
)
from fulvo.settings import LIMITE_DEUDA
from tests.datos import con_token
from tests.factories import (
    guardar_aceptado,
    guardar_partido,
    guardar_partido_jugado,
    guardar_usuario_comun,
)

VOTACIONES = '/votaciones'
MI_PERFIL = '/usuarios/yo'
NO_JUGADO = 'Solo se puede marcar un no-show en un partido jugado'
BLOQUEO_CON_CUATRO = (
    'Tenés votaciones pendientes en 4 partidos y el máximo es 3: completá '
    'las de al menos 1 partido para publicar o postularte (te faltan 4 '
    'votaciones).'
)
# Inicio fijo, en hora de Argentina, para los tests que mueven el reloj.
INICIO = datetime(2026, 11, 20, 20, 0)


def terminado_sin_consultar(session, organizador, aceptados=()):
    """Partido que terminó hace una hora y que nadie consultó todavía.

    Sigue abierto en la base: pasa a jugado, y recién ahí se crean sus
    votaciones, cuando alguna ruta lo pone al día.
    """
    partido = guardar_partido(
        session, organizador, inicio=ahora_argentina() - timedelta(hours=2)
    )
    for jugador in aceptados:
        guardar_aceptado(session, partido, jugador)
    return partido


def deber_partidos(session, usuario, cantidad: int) -> None:
    """Deja al usuario con votaciones pendientes en `cantidad` partidos.

    En cada uno es el único participante: le queda un voto, al complejo.
    """
    for _ in range(cantidad):
        guardar_partido_jugado(session, usuario)


def en_hora_argentina(momento: datetime):
    """Congela el reloj en `momento`, una hora de Argentina sin zona.

    freezegun toma una fecha sin zona como UTC: con la zona de Argentina,
    `ahora_argentina()` devuelve justo `momento`.
    """
    return freeze_time(momento.replace(tzinfo=HORA_ARGENTINA))


def mis_votaciones(client, usuario, **params) -> list[dict]:
    respuesta = client.get(
        VOTACIONES, params=params, headers=con_token(usuario)
    )
    assert respuesta.status_code == HTTPStatus.OK
    return respuesta.json()['votaciones']


def receptor(votacion: dict) -> tuple[str, int]:
    """A quién va el voto: ('usuario', id) o ('complejo', id)."""
    if votacion['receptor_usuario'] is not None:
        return ('usuario', votacion['receptor_usuario']['id'])
    return ('complejo', votacion['receptor_complejo']['id'])


def votacion_a(votaciones: list[dict], usuario) -> dict:
    """La votación de la lista que va hacia `usuario`."""
    buscado = ('usuario', usuario.id)
    return next(v for v in votaciones if receptor(v) == buscado)


def votar(client, votacion_id, usuario, estrellas):
    return client.patch(
        f'{VOTACIONES}/{votacion_id}',
        json={'estrellas': estrellas},
        headers=con_token(usuario),
    )


def responder(client, postulacion, organizador, cuerpo):
    """PATCH del organizador sobre una postulación de su partido."""
    return client.patch(
        f'/partidos/{postulacion.partido_id}/postulaciones/{postulacion.id}',
        json=cuerpo,
        headers=con_token(organizador),
    )


def marcar_no_show(client, postulacion, organizador):
    return responder(client, postulacion, organizador, {'no_show': True})


def publicar(client, usuario):
    inicio = ahora_argentina().replace(microsecond=0) + timedelta(days=7)
    datos = {
        'complejo_id': 1,
        'inicio': inicio.isoformat(),
        'tipo': 'F5',
        'cupos_faltantes': 2,
    }
    return client.post('/partidos', json=datos, headers=con_token(usuario))


def perfil_publico(client, usuario, quien_pregunta) -> dict:
    return client.get(
        f'/usuarios/{usuario.id}', headers=con_token(quien_pregunta)
    ).json()


def test_mis_votaciones_ponen_al_dia_un_partido_terminado(
    client, session, usuario, otro_usuario
):
    partido = terminado_sin_consultar(session, usuario, [otro_usuario])

    votaciones = mis_votaciones(client, usuario)

    assert {receptor(v) for v in votaciones} == {
        ('usuario', otro_usuario.id),
        ('complejo', 1),
    }
    for votacion in votaciones:
        assert votacion['estado'] == 'pendiente'
        assert votacion['estrellas'] is None
        assert votacion['emitida_at'] is None
        assert votacion['partido']['id'] == partido.id
        assert votacion['partido']['estado'] == 'jugado'


def test_cada_votacion_muestra_solo_el_perfil_publico_del_jugador(
    client, session, usuario, otro_usuario
):
    terminado_sin_consultar(session, usuario, [otro_usuario])

    al_jugador = votacion_a(mis_votaciones(client, usuario), otro_usuario)

    # Cuerpo completo: el WhatsApp y el apellido no pueden aparecer.
    assert al_jugador['receptor_usuario'] == {
        'id': otro_usuario.id,
        'nombre': 'Ana',
        'posicion': 'Delantera',
        'puntuacion_promedio': None,
        'partidos_jugados': 1,
    }
    assert al_jugador['receptor_complejo'] is None


def test_la_votacion_al_complejo_trae_el_complejo(client, session, usuario):
    terminado_sin_consultar(session, usuario)

    (al_complejo,) = mis_votaciones(client, usuario)

    assert al_complejo['receptor_usuario'] is None
    assert al_complejo['receptor_complejo']['id'] == 1
    assert al_complejo['receptor_complejo']['cantidad_puntuaciones'] == 0


def test_cada_uno_ve_solo_sus_votaciones(
    client, session, usuario, otro_usuario
):
    terminado_sin_consultar(session, usuario, [otro_usuario])
    del_organizador = {v['id'] for v in mis_votaciones(client, usuario)}

    del_jugador = mis_votaciones(client, otro_usuario)

    assert {receptor(v) for v in del_jugador} == {
        ('usuario', usuario.id),
        ('complejo', 1),
    }
    assert del_organizador.isdisjoint({v['id'] for v in del_jugador})


def test_un_partido_que_no_termino_todavia_no_tiene_votaciones(
    client, session, usuario
):
    en_juego = guardar_partido(
        session, usuario, inicio=ahora_argentina() - timedelta(minutes=30)
    )

    votaciones = mis_votaciones(client, usuario)

    assert votaciones == []
    assert en_juego.estado == 'abierto'


def test_mis_votaciones_filtran_por_estado(
    client, session, usuario, otro_usuario
):
    terminado_sin_consultar(session, usuario, [otro_usuario])
    al_jugador = votacion_a(mis_votaciones(client, usuario), otro_usuario)
    votar(client, al_jugador['id'], usuario, 3)

    pendientes = mis_votaciones(client, usuario, estado='pendiente')
    emitidas = mis_votaciones(client, usuario, estado='emitida')

    assert [receptor(v) for v in pendientes] == [('complejo', 1)]
    assert [v['id'] for v in emitidas] == [al_jugador['id']]


def test_mis_votaciones_se_paginan(client, session, usuario, otro_usuario):
    terminado_sin_consultar(session, usuario, [otro_usuario])
    todas = mis_votaciones(client, usuario)

    pagina = mis_votaciones(client, usuario, offset=1, limit=1)

    assert pagina == todas[1:2]


@pytest.mark.parametrize(
    'params', [{'estado': 'cualquiera'}, {'limit': 0}, {'offset': -1}]
)
def test_mis_votaciones_con_parametros_invalidos_devuelve_error(
    client, usuario, params
):
    respuesta = client.get(
        VOTACIONES, params=params, headers=con_token(usuario)
    )

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.parametrize(
    ('metodo', 'ruta', 'cuerpo'),
    [
        ('GET', VOTACIONES, None),
        ('PATCH', f'{VOTACIONES}/1', {'estrellas': 3}),
    ],
)
def test_sin_token_devuelve_no_autenticado(client, metodo, ruta, cuerpo):
    respuesta = client.request(metodo, ruta, json=cuerpo)

    assert respuesta.status_code == HTTPStatus.UNAUTHORIZED


def test_al_terminar_cada_participante_recibe_el_aviso_de_votar(
    client, session, usuario, otro_usuario
):
    terminado_sin_consultar(session, usuario, [otro_usuario])

    # Lo pone al día el jugador; el aviso le llega también al organizador.
    mis_votaciones(client, otro_usuario)

    for participante in (usuario, otro_usuario):
        avisos = client.get(
            '/notificaciones', headers=con_token(participante)
        ).json()['notificaciones']
        assert [a['tipo'] for a in avisos] == ['votaciones_pendientes']


def test_emitir_una_votacion_la_completa_y_puntua_al_jugador(
    client, session, usuario, otro_usuario
):
    terminado_sin_consultar(session, usuario, [otro_usuario])
    al_jugador = votacion_a(mis_votaciones(client, usuario), otro_usuario)

    estrellas = 4

    respuesta = votar(client, al_jugador['id'], usuario, estrellas)

    assert respuesta.status_code == HTTPStatus.OK
    cuerpo = respuesta.json()
    assert cuerpo['estado'] == 'emitida'
    assert cuerpo['estrellas'] == estrellas
    assert cuerpo['emitida_at'] is not None
    perfil = perfil_publico(client, otro_usuario, usuario)
    assert perfil['puntuacion_promedio'] == estrellas


def test_el_promedio_del_jugador_junta_los_votos_de_varios(
    client, session, usuario, otro_usuario
):
    tercero = guardar_usuario_comun(session, usuario.rol_id)
    terminado_sin_consultar(session, usuario, [otro_usuario, tercero])
    for emisor, estrellas in ((usuario, 5), (tercero, 2)):
        votacion = votacion_a(mis_votaciones(client, emisor), otro_usuario)
        votar(client, votacion['id'], emisor, estrellas)

    perfil = perfil_publico(client, otro_usuario, usuario)

    assert perfil['puntuacion_promedio'] == pytest.approx(3.5)


def test_votar_al_complejo_actualiza_su_puntuacion(client, session, usuario):
    terminado_sin_consultar(session, usuario)
    (al_complejo,) = mis_votaciones(client, usuario)

    estrellas = 5

    votar(client, al_complejo['id'], usuario, estrellas)

    complejo = client.get('/complejos/1').json()
    assert complejo['puntuacion_promedio'] == estrellas
    assert complejo['cantidad_puntuaciones'] == 1


def test_no_se_puede_emitir_la_votacion_de_otro(
    client, session, usuario, otro_usuario
):
    terminado_sin_consultar(session, usuario, [otro_usuario])
    ajena = mis_votaciones(client, usuario)[0]

    respuesta = votar(client, ajena['id'], otro_usuario, 5)

    assert respuesta.status_code == HTTPStatus.FORBIDDEN
    assert respuesta.json()['detail'] == (
        'Solo quien emite la votación puede completarla'
    )


def test_emitir_una_votacion_inexistente_es_no_encontrado(client, usuario):
    respuesta = votar(client, 9999, usuario, 3)

    assert respuesta.status_code == HTTPStatus.NOT_FOUND
    assert respuesta.json()['detail'] == 'Votación no encontrada'


def test_emitir_dos_veces_devuelve_conflicto(client, session, usuario):
    terminado_sin_consultar(session, usuario)
    (votacion,) = mis_votaciones(client, usuario)
    primera = 4
    votar(client, votacion['id'], usuario, primera)

    respuesta = votar(client, votacion['id'], usuario, 1)

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == 'La votación ya fue emitida'
    complejo = client.get('/complejos/1').json()
    assert complejo['puntuacion_promedio'] == primera


@pytest.mark.parametrize('estrellas', [-1, 6, 4.5, 'muchas', None])
def test_las_estrellas_van_de_0_a_5_enteras(
    client, session, usuario, estrellas
):
    terminado_sin_consultar(session, usuario)
    (votacion,) = mis_votaciones(client, usuario)

    respuesta = votar(client, votacion['id'], usuario, estrellas)

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_marcar_no_show_le_resta_el_partido_y_le_suma_un_cero(
    client, session, usuario, otro_usuario
):
    partido = terminado_sin_consultar(session, usuario, [otro_usuario])

    respuesta = marcar_no_show(client, partido.postulaciones[0], usuario)

    assert respuesta.status_code == HTTPStatus.OK
    assert respuesta.json()['no_show'] is True
    perfil = perfil_publico(client, otro_usuario, usuario)
    assert perfil['partidos_jugados'] == 0
    assert perfil['puntuacion_promedio'] == 0


def test_el_no_show_borra_las_votaciones_pendientes_del_ausente_y_hacia_el(
    client, session, usuario, otro_usuario
):
    presente = guardar_usuario_comun(session, usuario.rol_id)
    partido = terminado_sin_consultar(
        session, usuario, [otro_usuario, presente]
    )

    marcar_no_show(client, partido.postulaciones[0], usuario)

    assert mis_votaciones(client, otro_usuario) == []
    assert {receptor(v) for v in mis_votaciones(client, usuario)} == {
        ('usuario', presente.id),
        ('complejo', 1),
    }


def test_el_no_show_se_ve_en_las_postulaciones_de_los_dos(
    client, session, usuario, otro_usuario
):
    partido = terminado_sin_consultar(session, usuario, [otro_usuario])

    marcar_no_show(client, partido.postulaciones[0], usuario)

    del_jugador = client.get(
        '/postulaciones', headers=con_token(otro_usuario)
    ).json()['postulaciones'][0]
    del_organizador = client.get(
        f'/partidos/{partido.id}/postulaciones', headers=con_token(usuario)
    ).json()['postulaciones'][0]
    assert del_jugador['no_show'] is True
    assert del_organizador['no_show'] is True


def test_no_show_en_un_partido_que_no_se_jugo_devuelve_conflicto(
    client, session, usuario, otro_usuario
):
    partido = guardar_partido(session, usuario)
    postulacion = guardar_aceptado(session, partido, otro_usuario)

    respuesta = marcar_no_show(client, postulacion, usuario)

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == NO_JUGADO


def test_el_aceptado_que_no_fue_no_se_puede_bajar_y_recibe_el_no_show(
    client, session, usuario, otro_usuario
):
    partido = guardar_partido(session, usuario, inicio=INICIO)
    postulacion = guardar_aceptado(session, partido, otro_usuario)

    with en_hora_argentina(INICIO + timedelta(minutes=30)):
        baja = client.patch(
            f'/postulaciones/{postulacion.id}',
            json={'estado': 'retirada'},
            headers=con_token(otro_usuario),
        )

    assert baja.status_code == HTTPStatus.CONFLICT
    assert baja.json()['detail'] == 'El partido ya empezó'
    # Sigue aceptado: cuando el partido termina, el organizador le marca
    # el no-show.
    with en_hora_argentina(partido.fin() + timedelta(minutes=1)):
        no_show = marcar_no_show(client, postulacion, usuario)
    assert no_show.status_code == HTTPStatus.OK
    assert no_show.json()['no_show'] is True


def test_no_show_a_un_jugador_no_aceptado_devuelve_conflicto(
    client, session, usuario, otro_usuario
):
    partido = terminado_sin_consultar(session, usuario, [otro_usuario])
    postulacion = partido.postulaciones[0]
    postulacion.estado = EstadoPostulacion.revocada
    session.commit()

    respuesta = marcar_no_show(client, postulacion, usuario)

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == (
        'Solo se puede marcar el no-show de un jugador aceptado'
    )


def test_marcar_dos_veces_el_no_show_devuelve_conflicto(
    client, session, usuario, otro_usuario
):
    partido = terminado_sin_consultar(session, usuario, [otro_usuario])
    marcar_no_show(client, partido.postulaciones[0], usuario)

    respuesta = marcar_no_show(client, partido.postulaciones[0], usuario)

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == 'El no-show ya estaba marcado'
    perfil = perfil_publico(client, otro_usuario, usuario)
    assert perfil['partidos_jugados'] == 0


def test_solo_el_organizador_marca_un_no_show(
    client, session, usuario, otro_usuario
):
    partido = terminado_sin_consultar(session, usuario, [otro_usuario])

    respuesta = marcar_no_show(client, partido.postulaciones[0], otro_usuario)

    assert respuesta.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.parametrize(
    'cuerpo',
    [{}, {'estado': 'aceptada', 'no_show': True}, {'no_show': False}],
    ids=['vacio', 'los_dos', 'desmarcar'],
)
def test_el_organizador_manda_estado_o_no_show_uno_de_los_dos(
    client, session, usuario, otro_usuario, cuerpo
):
    partido = terminado_sin_consultar(session, usuario, [otro_usuario])

    respuesta = responder(client, partido.postulaciones[0], usuario, cuerpo)

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_con_deuda_de_mas_no_se_puede_publicar(client, session, usuario):
    deber_partidos(session, usuario, LIMITE_DEUDA + 1)

    respuesta = publicar(client, usuario)

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == BLOQUEO_CON_CUATRO


def test_con_la_deuda_en_el_limite_todavia_se_puede_publicar(
    client, session, usuario
):
    deber_partidos(session, usuario, LIMITE_DEUDA)

    respuesta = publicar(client, usuario)

    assert respuesta.status_code == HTTPStatus.CREATED


def test_con_deuda_de_mas_no_se_puede_postular(
    client, session, usuario, otro_usuario
):
    deber_partidos(session, otro_usuario, LIMITE_DEUDA + 1)
    partido = guardar_partido(session, usuario)

    respuesta = client.post(
        f'/partidos/{partido.id}/postulaciones',
        headers=con_token(otro_usuario),
    )

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == BLOQUEO_CON_CUATRO


def test_la_deuda_incluye_partidos_terminados_que_nadie_consulto(
    client, session, usuario
):
    for _ in range(LIMITE_DEUDA + 1):
        terminado_sin_consultar(session, usuario)

    respuesta = publicar(client, usuario)

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == BLOQUEO_CON_CUATRO


def test_al_postularse_la_deuda_incluye_partidos_que_nadie_consulto(
    client, session, usuario, otro_usuario
):
    for _ in range(LIMITE_DEUDA + 1):
        terminado_sin_consultar(session, otro_usuario)
    partido = guardar_partido(session, usuario)

    respuesta = client.post(
        f'/partidos/{partido.id}/postulaciones',
        headers=con_token(otro_usuario),
    )

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == BLOQUEO_CON_CUATRO


def test_votar_lo_que_falta_vuelve_a_habilitar(client, session, usuario):
    deber_partidos(session, usuario, LIMITE_DEUDA + 1)
    votacion = mis_votaciones(client, usuario)[0]
    votar(client, votacion['id'], usuario, 3)

    respuesta = publicar(client, usuario)

    assert respuesta.status_code == HTTPStatus.CREATED


@pytest.mark.parametrize(
    ('partidos', 'habilitado'),
    [(LIMITE_DEUDA, True), (LIMITE_DEUDA + 1, False)],
)
def test_mi_perfil_muestra_la_deuda_y_si_estoy_habilitado(
    client, session, usuario, partidos, habilitado
):
    deber_partidos(session, usuario, partidos)

    perfil = client.get(MI_PERFIL, headers=con_token(usuario)).json()

    assert perfil['deuda'] == partidos
    assert perfil['habilitado'] is habilitado


def test_mi_perfil_pone_al_dia_mis_partidos_terminados(
    client, session, usuario, otro_usuario
):
    terminado_sin_consultar(session, usuario, [otro_usuario])

    perfil = client.get(MI_PERFIL, headers=con_token(otro_usuario)).json()

    assert perfil['partidos_jugados'] == 1
    assert perfil['deuda'] == 1


def test_editar_mi_perfil_tambien_muestra_la_deuda(client, session, usuario):
    partidos = 2
    deber_partidos(session, usuario, partidos)

    respuesta = client.patch(
        MI_PERFIL, json={'posicion': 'Arquera'}, headers=con_token(usuario)
    )

    assert respuesta.json()['posicion'] == 'Arquera'
    assert respuesta.json()['deuda'] == partidos
    assert respuesta.json()['habilitado'] is True


def test_un_complejo_sin_votos_no_tiene_puntuacion(client):
    complejo = client.get('/complejos/1').json()

    assert complejo['puntuacion_promedio'] is None
    assert complejo['cantidad_puntuaciones'] == 0


def test_editar_un_complejo_no_cambia_su_puntuacion(client_admin, session):
    estrellas = 4
    session.get(Complejo, 1).registrar_puntuacion(estrellas)
    session.commit()
    datos = client_admin.get('/complejos/1').json()
    # La puntuación que mande el cliente se ignora: sale de las votaciones.
    cambios = {'nombre': 'Otro nombre', 'puntuacion_promedio': 1}

    respuesta = client_admin.put('/complejos/1', json=datos | cambios)

    assert respuesta.status_code == HTTPStatus.OK
    assert respuesta.json()['nombre'] == 'Otro nombre'
    assert respuesta.json()['puntuacion_promedio'] == estrellas
    assert respuesta.json()['cantidad_puntuaciones'] == 1

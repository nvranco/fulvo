from datetime import timedelta
from http import HTTPStatus

import pytest

from fulvo.models import ahora_argentina
from tests.datos import con_token
from tests.factories import guardar_partido, guardar_usuario_comun

NOTIFICACIONES = '/notificaciones'


@pytest.fixture
def partido(session, usuario):
    """Partido abierto de `usuario` (el organizador), con 2 cupos."""
    return guardar_partido(session, usuario, cupos_faltantes=2)


def postular(client, partido, jugador) -> dict:
    return client.post(
        f'/partidos/{partido.id}/postulaciones', headers=con_token(jugador)
    ).json()


def aceptar(client, partido, postulacion, organizador) -> None:
    client.patch(
        f'/partidos/{partido.id}/postulaciones/{postulacion["id"]}',
        json={'estado': 'aceptada'},
        headers=con_token(organizador),
    )


def leer(client, usuario, **params) -> list[dict]:
    respuesta = client.get(
        NOTIFICACIONES, params=params, headers=con_token(usuario)
    )
    assert respuesta.status_code == HTTPStatus.OK
    return respuesta.json()['notificaciones']


def marcar(client, notificacion_id, usuario, leida=True):
    return client.patch(
        f'{NOTIFICACIONES}/{notificacion_id}',
        json={'leida': leida},
        headers=con_token(usuario),
    )


def test_el_organizador_recibe_el_aviso_de_una_postulacion(
    client, session, usuario, partido
):
    jugador = guardar_usuario_comun(session, usuario.rol_id, nombre='Beto')
    postulacion = postular(client, partido, jugador)

    avisos = leer(client, usuario)

    assert len(avisos) == 1
    aviso = avisos[0]
    assert aviso['tipo'] == 'postulacion_recibida'
    assert aviso['mensaje'].startswith('Beto se postuló a tu partido del ')
    assert aviso['referencia_tipo'] == 'postulacion'
    assert aviso['referencia_id'] == postulacion['id']
    assert aviso['leida'] is False


def test_el_jugador_aceptado_recibe_el_aviso_sin_ningun_whatsapp(
    client, usuario, otro_usuario, partido
):
    aceptar(client, partido, postular(client, partido, otro_usuario), usuario)

    avisos = leer(client, otro_usuario)

    assert [a['tipo'] for a in avisos] == ['postulacion_aceptada']
    assert usuario.whatsapp not in avisos[0]['mensaje']


def test_cada_uno_ve_solo_sus_notificaciones(
    client, usuario, otro_usuario, partido
):
    postular(client, partido, otro_usuario)

    assert leer(client, otro_usuario) == []
    assert len(leer(client, usuario)) == 1


def test_las_notificaciones_van_de_la_mas_nueva_a_la_mas_vieja(
    client, session, usuario, partido
):
    primero, segundo = (
        guardar_usuario_comun(session, usuario.rol_id, nombre=nombre)
        for nombre in ('Primero', 'Segundo')
    )
    postular(client, partido, primero)
    postular(client, partido, segundo)

    avisos = leer(client, usuario)

    assert [a['mensaje'].split()[0] for a in avisos] == ['Segundo', 'Primero']


def test_un_partido_usado_en_varios_pedidos_no_duplica_los_avisos(
    client, session, usuario, otro_usuario, partido
):
    # Cada pedido prepara el partido; si los observadores se sumaran de
    # nuevo, cada evento llegaría repetido.
    tercero = guardar_usuario_comun(session, usuario.rol_id)
    postulacion = postular(client, partido, otro_usuario)
    postular(client, partido, tercero)
    client.patch(
        f'/postulaciones/{postulacion["id"]}',
        json={'estado': 'retirada'},
        headers=con_token(otro_usuario),
    )

    tipos = [a['tipo'] for a in leer(client, usuario)]

    assert tipos == [
        'postulacion_retirada',
        'postulacion_recibida',
        'postulacion_recibida',
    ]


def test_filtrar_por_leidas_y_no_leidas(
    client, session, usuario, otro_usuario, partido
):
    postular(client, partido, otro_usuario)
    postular(client, partido, guardar_usuario_comun(session, usuario.rol_id))
    vieja, nueva = sorted(a['id'] for a in leer(client, usuario))
    marcar(client, vieja, usuario)

    assert [a['id'] for a in leer(client, usuario, leida='false')] == [nueva]
    assert [a['id'] for a in leer(client, usuario, leida='true')] == [vieja]


def test_las_notificaciones_se_paginan(client, session, usuario, partido):
    for _ in range(3):
        postular(
            client, partido, guardar_usuario_comun(session, usuario.rol_id)
        )

    pagina = leer(client, usuario, offset=1, limit=1)

    todas = leer(client, usuario)
    assert [a['id'] for a in pagina] == [todas[1]['id']]


def test_marcar_una_notificacion_como_leida(
    client, usuario, otro_usuario, partido
):
    postular(client, partido, otro_usuario)
    aviso = leer(client, usuario)[0]

    respuesta = marcar(client, aviso['id'], usuario)
    otra_vez = marcar(client, aviso['id'], usuario)

    assert respuesta.status_code == HTTPStatus.OK
    assert respuesta.json()['leida'] is True
    assert otra_vez.json()['leida'] is True
    assert leer(client, usuario)[0]['leida'] is True


def test_no_se_puede_marcar_la_notificacion_de_otro(
    client, usuario, otro_usuario, partido
):
    postular(client, partido, otro_usuario)
    aviso = leer(client, usuario)[0]

    respuesta = marcar(client, aviso['id'], otro_usuario)

    assert respuesta.status_code == HTTPStatus.FORBIDDEN
    assert respuesta.json()['detail'] == (
        'Solo el destinatario puede marcar la notificación'
    )
    assert leer(client, usuario)[0]['leida'] is False


def test_marcar_una_notificacion_inexistente_es_no_encontrado(client, usuario):
    respuesta = marcar(client, 9999, usuario)

    assert respuesta.status_code == HTTPStatus.NOT_FOUND
    assert respuesta.json()['detail'] == 'Notificación no encontrada'


def test_solo_se_puede_marcar_como_leida(
    client, usuario, otro_usuario, partido
):
    postular(client, partido, otro_usuario)
    aviso = leer(client, usuario)[0]

    respuesta = marcar(client, aviso['id'], usuario, leida=False)

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.parametrize(
    ('metodo', 'ruta', 'cuerpo'),
    [
        ('GET', NOTIFICACIONES, None),
        ('PATCH', f'{NOTIFICACIONES}/1', {'leida': True}),
    ],
)
def test_sin_token_devuelve_no_autenticado(client, metodo, ruta, cuerpo):
    respuesta = client.request(metodo, ruta, json=cuerpo)

    assert respuesta.status_code == HTTPStatus.UNAUTHORIZED


def test_consultar_un_partido_terminado_avisa_las_votaciones_pendientes(
    client, session, usuario
):
    terminado = guardar_partido(
        session, usuario, inicio=ahora_argentina() - timedelta(hours=3)
    )

    client.get(f'/partidos/{terminado.id}', headers=con_token(usuario))

    avisos = leer(client, usuario)
    assert [a['tipo'] for a in avisos] == ['votaciones_pendientes']
    assert avisos[0]['referencia_tipo'] == 'partido'
    assert avisos[0]['referencia_id'] == terminado.id
    assert avisos[0]['mensaje'].startswith('Terminó el partido del ')


def test_mis_postulaciones_ponen_al_dia_sus_partidos(
    client, session, usuario, otro_usuario, partido
):
    postular(client, partido, otro_usuario)
    partido.inicio = ahora_argentina() - timedelta(hours=3)
    session.commit()

    respuesta = client.get('/postulaciones', headers=con_token(otro_usuario))

    assert respuesta.json()['postulaciones'][0]['partido']['estado'] == (
        'jugado'
    )

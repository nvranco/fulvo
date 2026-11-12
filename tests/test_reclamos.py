from http import HTTPStatus

import pytest

from tests.datos import CONTRASENA, con_token
from tests.factories import guardar_partido, guardar_partido_jugado

RECLAMOS = '/reclamos'
MOTIVO = 'Fui al partido y jugué todo'
RESOLUCION = 'El organizador confirmó que fue'
SOLO_ADMIN = 'Esta acción es solo para administradores'


def abrir(client, autor, tipo, objetivo_id, motivo=MOTIVO):
    return client.post(
        RECLAMOS,
        json={
            'tipo_objetivo': tipo,
            'objetivo_id': objetivo_id,
            'motivo': motivo,
        },
        headers=con_token(autor),
    )


def responder(client, reclamo_id, quien, estado='resuelto', **extra):
    """PATCH sobre el reclamo; `extra` suma campos, como `bloquear`."""
    return client.patch(
        f'{RECLAMOS}/{reclamo_id}',
        json={'estado': estado, 'resolucion': RESOLUCION} | extra,
        headers=con_token(quien),
    )


def listar(client, usuario, **params) -> list[dict]:
    respuesta = client.get(RECLAMOS, params=params, headers=con_token(usuario))
    assert respuesta.status_code == HTTPStatus.OK
    return respuesta.json()['reclamos']


def avisos(client, usuario) -> list[dict]:
    """Notificaciones del usuario, de la más nueva a la más vieja."""
    respuesta = client.get('/notificaciones', headers=con_token(usuario))
    return respuesta.json()['notificaciones']


def votaciones(client, usuario, **params) -> list[dict]:
    respuesta = client.get(
        '/votaciones', params=params, headers=con_token(usuario)
    )
    assert respuesta.status_code == HTTPStatus.OK
    return respuesta.json()['votaciones']


def receptor(votacion: dict) -> tuple[str, int]:
    """A quién va el voto: ('usuario', id) o ('complejo', id)."""
    if votacion['receptor_usuario'] is not None:
        return ('usuario', votacion['receptor_usuario']['id'])
    return ('complejo', votacion['receptor_complejo']['id'])


def perfil(client, usuario) -> dict:
    return client.get('/usuarios/yo', headers=con_token(usuario)).json()


def iniciar_sesion(client, usuario):
    return client.post(
        '/auth/token',
        data={'username': usuario.email, 'password': CONTRASENA},
    )


@pytest.fixture
def jugado(session, usuario, otro_usuario):
    """Partido jugado de `usuario` (el organizador), con `otro_usuario`."""
    return guardar_partido_jugado(session, usuario, [otro_usuario])


@pytest.fixture
def no_show(client, jugado, usuario):
    """La postulación de `otro_usuario`, marcada como no-show por la API."""
    postulacion = jugado.postulaciones[0]
    respuesta = client.patch(
        f'/partidos/{jugado.id}/postulaciones/{postulacion.id}',
        json={'no_show': True},
        headers=con_token(usuario),
    )
    assert respuesta.status_code == HTTPStatus.OK
    # En producción cada pedido tiene su sesión y suma sus observadores; acá
    # la sesión es una sola, y el partido seguiría con los de este pedido.
    # Se los saca para que el pedido que resuelve el reclamo los tenga que
    # sumar, como en producción.
    jugado.observadores.clear()
    return postulacion


@pytest.fixture
def voto_recibido(client, jugado, usuario, otro_usuario) -> dict:
    """Votación de 1 estrella de `usuario` a `otro_usuario`, ya emitida."""
    votacion = next(
        v
        for v in votaciones(client, usuario, estado='pendiente')
        if receptor(v) == ('usuario', otro_usuario.id)
    )
    respuesta = client.patch(
        f'/votaciones/{votacion["id"]}',
        json={'estrellas': 1},
        headers=con_token(usuario),
    )
    assert respuesta.status_code == HTTPStatus.OK
    return respuesta.json()


@pytest.fixture
def denuncia(client, usuario, otro_usuario) -> dict:
    """Denuncia abierta de `usuario` contra `otro_usuario`."""
    return abrir(client, usuario, 'usuario', otro_usuario.id).json()


def test_abrir_un_reclamo_por_un_no_show_propio(
    client, jugado, otro_usuario, no_show
):
    respuesta = abrir(client, otro_usuario, 'no_show', no_show.id)

    assert respuesta.status_code == HTTPStatus.CREATED
    reclamo = respuesta.json()
    assert reclamo['tipo_objetivo'] == 'no_show'
    assert reclamo['objetivo_id'] == no_show.id
    assert reclamo['partido_id'] == jugado.id
    assert reclamo['motivo'] == MOTIVO
    assert reclamo['estado'] == 'abierto'
    assert reclamo['autor']['id'] == otro_usuario.id
    assert reclamo['resolucion'] is None
    assert reclamo['resuelto_at'] is None
    assert reclamo['resuelto_por'] is None


def test_abrir_un_reclamo_por_una_votacion_recibida(
    client, jugado, otro_usuario, voto_recibido
):
    respuesta = abrir(client, otro_usuario, 'votacion', voto_recibido['id'])

    assert respuesta.status_code == HTTPStatus.CREATED
    assert respuesta.json()['partido_id'] == jugado.id


@pytest.mark.parametrize('tipo', ['usuario', 'complejo'])
def test_las_denuncias_no_tienen_partido(client, usuario, otro_usuario, tipo):
    objetivo_id = otro_usuario.id if tipo == 'usuario' else 1

    respuesta = abrir(client, usuario, tipo, objetivo_id)

    assert respuesta.status_code == HTTPStatus.CREATED
    assert respuesta.json()['partido_id'] is None


@pytest.mark.parametrize(
    ('tipo', 'detalle'),
    [
        ('no_show', 'Postulación no encontrada'),
        ('votacion', 'Votación no encontrada'),
        ('usuario', 'Usuario no encontrado'),
        ('complejo', 'Complejo no encontrado'),
    ],
)
def test_un_objetivo_que_no_existe_devuelve_404(
    client, usuario, tipo, detalle
):
    respuesta = abrir(client, usuario, tipo, 999)

    assert respuesta.status_code == HTTPStatus.NOT_FOUND
    assert respuesta.json()['detail'] == detalle


def test_no_se_reclama_el_no_show_de_otro(client, usuario, no_show):
    respuesta = abrir(client, usuario, 'no_show', no_show.id)

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == 'Solo podés reclamar un no-show tuyo'


def test_no_se_reclama_un_no_show_que_no_esta_marcado(
    client, jugado, otro_usuario
):
    postulacion = jugado.postulaciones[0]

    respuesta = abrir(client, otro_usuario, 'no_show', postulacion.id)

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == (
        'Esa postulación no tiene un no-show marcado'
    )


def test_no_se_reclama_una_votacion_que_no_recibio(
    client, usuario, voto_recibido
):
    respuesta = abrir(client, usuario, 'votacion', voto_recibido['id'])

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == (
        'Solo podés reclamar una votación que recibiste'
    )


def test_no_se_reclama_una_votacion_pendiente(
    client, jugado, usuario, otro_usuario
):
    pendiente = next(
        v
        for v in votaciones(client, usuario, estado='pendiente')
        if receptor(v) == ('usuario', otro_usuario.id)
    )

    respuesta = abrir(client, otro_usuario, 'votacion', pendiente['id'])

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == (
        'Solo se puede reclamar una votación emitida'
    )


def test_nadie_se_denuncia_a_si_mismo(client, usuario):
    respuesta = abrir(client, usuario, 'usuario', usuario.id)

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == 'No podés denunciarte a vos mismo'


def test_no_se_abren_dos_reclamos_iguales(client, usuario, otro_usuario):
    abrir(client, usuario, 'usuario', otro_usuario.id)

    respuesta = abrir(client, usuario, 'usuario', otro_usuario.id, 'Otra vez')

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == (
        'Ya tenés un reclamo abierto sobre eso'
    )


def test_despues_de_un_rechazo_se_puede_volver_a_reclamar(
    client, usuario, otro_usuario, admin, denuncia
):
    responder(client, denuncia['id'], admin, 'rechazado')

    respuesta = abrir(client, usuario, 'usuario', otro_usuario.id)

    assert respuesta.status_code == HTTPStatus.CREATED


@pytest.mark.parametrize(
    'cuerpo',
    [
        {'tipo_objetivo': 'partido', 'objetivo_id': 1, 'motivo': MOTIVO},
        {'tipo_objetivo': 'complejo', 'objetivo_id': 1, 'motivo': '   '},
        {'tipo_objetivo': 'complejo', 'motivo': MOTIVO},
    ],
)
def test_un_reclamo_mal_armado_devuelve_422(client, usuario, cuerpo):
    respuesta = client.post(RECLAMOS, json=cuerpo, headers=con_token(usuario))

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.parametrize(
    ('metodo', 'ruta'), [('POST', RECLAMOS), ('GET', RECLAMOS)]
)
def test_los_reclamos_piden_token(client, metodo, ruta):
    cuerpo = {'tipo_objetivo': 'complejo', 'objetivo_id': 1, 'motivo': MOTIVO}

    respuesta = client.request(metodo, ruta, json=cuerpo)

    assert respuesta.status_code == HTTPStatus.UNAUTHORIZED


def test_cada_usuario_ve_solo_sus_reclamos(client, usuario, otro_usuario):
    abrir(client, usuario, 'complejo', 1)
    abrir(client, otro_usuario, 'complejo', 2)

    mios = listar(client, usuario)

    assert [r['autor']['id'] for r in mios] == [usuario.id]


def test_el_admin_ve_los_reclamos_de_todos(
    client, usuario, otro_usuario, admin
):
    primero = abrir(client, usuario, 'complejo', 1).json()
    segundo = abrir(client, otro_usuario, 'complejo', 2).json()

    todos = listar(client, admin)

    assert [r['id'] for r in todos] == [segundo['id'], primero['id']]


def test_el_admin_filtra_los_reclamos_por_estado(
    client, usuario, otro_usuario, admin
):
    rechazado = abrir(client, usuario, 'complejo', 1).json()
    abierto = abrir(client, otro_usuario, 'complejo', 2).json()
    responder(client, rechazado['id'], admin, 'rechazado')

    abiertos = listar(client, admin, estado='abierto')
    rechazados = listar(client, admin, estado='rechazado')

    assert [r['id'] for r in abiertos] == [abierto['id']]
    assert [r['id'] for r in rechazados] == [rechazado['id']]


def test_los_reclamos_se_paginan_con_offset_y_limit(client, usuario):
    ids = [
        abrir(client, usuario, 'complejo', complejo_id).json()['id']
        for complejo_id in (1, 2, 3)
    ]

    pagina = listar(client, usuario, offset=1, limit=1)

    assert [r['id'] for r in pagina] == [ids[1]]


def test_solo_el_admin_responde_reclamos(client, otro_usuario, denuncia):
    respuesta = responder(client, denuncia['id'], otro_usuario)

    assert respuesta.status_code == HTTPStatus.FORBIDDEN
    assert respuesta.json()['detail'] == SOLO_ADMIN


def test_responder_un_reclamo_pide_token(client, denuncia):
    respuesta = client.patch(
        f'{RECLAMOS}/{denuncia["id"]}',
        json={'estado': 'rechazado', 'resolucion': RESOLUCION},
    )

    assert respuesta.status_code == HTTPStatus.UNAUTHORIZED


def test_responder_un_reclamo_que_no_existe_devuelve_404(client, admin):
    respuesta = responder(client, 999, admin)

    assert respuesta.status_code == HTTPStatus.NOT_FOUND
    assert respuesta.json()['detail'] == 'Reclamo no encontrado'


def test_rechazar_guarda_la_respuesta_y_avisa_al_autor(
    client, usuario, admin, denuncia
):
    respuesta = responder(client, denuncia['id'], admin, 'rechazado')

    assert respuesta.status_code == HTTPStatus.OK
    reclamo = respuesta.json()
    assert reclamo['estado'] == 'rechazado'
    assert reclamo['resolucion'] == RESOLUCION
    assert reclamo['resuelto_por']['id'] == admin.id
    assert reclamo['resuelto_at'] is not None
    aviso = avisos(client, usuario)[0]
    assert aviso['tipo'] == 'reclamo_resuelto'
    assert aviso['mensaje'] == (
        f'Tu reclamo sobre el usuario fue rechazado. Respuesta del admin: '
        f'{RESOLUCION}'
    )
    assert aviso['referencia_tipo'] == 'reclamo'
    assert aviso['referencia_id'] == denuncia['id']


def test_resolver_una_denuncia_sin_bloquear(
    client, usuario, otro_usuario, admin, denuncia
):
    respuesta = responder(client, denuncia['id'], admin)

    assert respuesta.status_code == HTTPStatus.OK
    assert respuesta.json()['estado'] == 'resuelto'
    assert iniciar_sesion(client, otro_usuario).status_code == HTTPStatus.OK
    assert 'fue aceptado' in avisos(client, usuario)[0]['mensaje']


def test_resolver_una_denuncia_puede_bloquear_al_denunciado(
    client, session, otro_usuario, admin, denuncia
):
    partido = guardar_partido(session, otro_usuario)

    respuesta = responder(client, denuncia['id'], admin, bloquear=True)

    assert respuesta.status_code == HTTPStatus.OK
    assert iniciar_sesion(client, otro_usuario).status_code == (
        HTTPStatus.UNAUTHORIZED
    )
    sanciones = client.get(
        f'/usuarios/{otro_usuario.id}/sanciones', headers=con_token(admin)
    ).json()['sanciones']
    assert [
        (s['reclamo_id'], s['motivo'], s['activa']) for s in sanciones
    ] == [(denuncia['id'], RESOLUCION, True)]
    visto = client.get(f'/partidos/{partido.id}', headers=con_token(admin))
    assert visto.json()['estado'] == 'cancelado'


def test_bloquear_al_rechazar_devuelve_422(client, admin, denuncia):
    respuesta = responder(
        client, denuncia['id'], admin, 'rechazado', bloquear=True
    )

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_solo_se_bloquea_en_una_denuncia_a_un_usuario(client, usuario, admin):
    reclamo = abrir(client, usuario, 'complejo', 1).json()

    respuesta = responder(client, reclamo['id'], admin, bloquear=True)

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == (
        'Solo se puede bloquear al resolver una denuncia a un usuario'
    )
    assert listar(client, admin)[0]['estado'] == 'abierto'


def test_si_el_denunciado_ya_esta_bloqueado_el_reclamo_sigue_abierto(
    client, usuario, otro_usuario, admin, denuncia
):
    client.post(
        f'/usuarios/{otro_usuario.id}/sanciones',
        json={'motivo': 'Un bloqueo anterior'},
        headers=con_token(admin),
    )

    respuesta = responder(client, denuncia['id'], admin, bloquear=True)

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == 'El usuario ya está bloqueado'
    assert listar(client, usuario)[0]['estado'] == 'abierto'
    assert avisos(client, usuario) == []


def test_un_reclamo_cerrado_no_se_vuelve_a_responder(client, admin, denuncia):
    responder(client, denuncia['id'], admin, 'rechazado')

    respuesta = responder(client, denuncia['id'], admin)

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == (
        'El reclamo ya fue resuelto o rechazado'
    )


def test_resolver_un_no_show_le_devuelve_todo_al_jugador(
    client, usuario, otro_usuario, admin, no_show
):
    reclamo = abrir(client, otro_usuario, 'no_show', no_show.id).json()

    respuesta = responder(client, reclamo['id'], admin)

    assert respuesta.status_code == HTTPStatus.OK
    mias = client.get('/postulaciones', headers=con_token(otro_usuario))
    assert mias.json()['postulaciones'][0]['no_show'] is False
    suyo = perfil(client, otro_usuario)
    assert suyo['partidos_jugados'] == 1
    assert suyo['puntuacion_promedio'] is None
    # Se reponen las votaciones: las suyas y la del organizador hacia él.
    assert {
        receptor(v)
        for v in votaciones(client, otro_usuario, estado='pendiente')
    } == {('usuario', usuario.id), ('complejo', no_show.partido.complejo_id)}
    assert ('usuario', otro_usuario.id) in {
        receptor(v) for v in votaciones(client, usuario, estado='pendiente')
    }


def test_resolver_un_no_show_avisa_a_los_que_vuelven_a_deber(
    client, usuario, otro_usuario, admin, no_show
):
    reclamo = abrir(client, otro_usuario, 'no_show', no_show.id).json()

    responder(client, reclamo['id'], admin)

    assert [a['tipo'] for a in avisos(client, usuario)] == [
        'votaciones_repuestas'
    ]
    assert [a['tipo'] for a in avisos(client, otro_usuario)] == [
        'reclamo_resuelto',
        'votaciones_repuestas',
    ]


def test_rechazar_un_reclamo_por_no_show_deja_la_marca(
    client, otro_usuario, admin, no_show
):
    reclamo = abrir(client, otro_usuario, 'no_show', no_show.id).json()

    responder(client, reclamo['id'], admin, 'rechazado')

    mias = client.get('/postulaciones', headers=con_token(otro_usuario))
    assert mias.json()['postulaciones'][0]['no_show'] is True
    assert perfil(client, otro_usuario)['partidos_jugados'] == 0


def test_resolver_una_votacion_la_anula_y_recalcula_el_promedio(
    client, otro_usuario, admin, voto_recibido
):
    reclamo = abrir(client, otro_usuario, 'votacion', voto_recibido['id'])

    responder(client, reclamo.json()['id'], admin)

    recibidas = votaciones(client, otro_usuario, recibidas=True)
    assert [(v['id'], v['estado']) for v in recibidas] == [
        (voto_recibido['id'], 'anulada')
    ]
    assert perfil(client, otro_usuario)['puntuacion_promedio'] is None


def test_rechazar_un_reclamo_por_votacion_no_la_toca(
    client, otro_usuario, admin, voto_recibido
):
    reclamo = abrir(client, otro_usuario, 'votacion', voto_recibido['id'])

    responder(client, reclamo.json()['id'], admin, 'rechazado')

    recibidas = votaciones(client, otro_usuario, recibidas=True)
    assert [v['estado'] for v in recibidas] == ['emitida']
    assert perfil(client, otro_usuario)['puntuacion_promedio'] == 1


def test_resolver_una_denuncia_a_un_complejo_no_aplica_medidas(
    client, usuario, admin
):
    reclamo = abrir(client, usuario, 'complejo', 1).json()

    respuesta = responder(client, reclamo['id'], admin)

    assert respuesta.status_code == HTTPStatus.OK
    assert respuesta.json()['estado'] == 'resuelto'
    assert client.get('/complejos/1').status_code == HTTPStatus.OK


def test_las_votaciones_recibidas_no_dicen_quien_voto(
    client, otro_usuario, voto_recibido
):
    recibidas = votaciones(client, otro_usuario, recibidas=True)

    assert len(recibidas) == 1
    voto = recibidas[0]
    assert voto['id'] == voto_recibido['id']
    assert voto['estrellas'] == 1
    assert voto['receptor_usuario']['id'] == otro_usuario.id
    assert 'emisor' not in voto


def test_las_votaciones_recibidas_no_muestran_las_pendientes(
    client, jugado, otro_usuario
):
    assert votaciones(client, otro_usuario, recibidas=True) == []

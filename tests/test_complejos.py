from http import HTTPStatus

from fulvo.carga_inicial import leer_filas
from fulvo.routes.complejos import distancia_km

# Valores que salen de fulvo/datos/complejos.csv y de los valores por defecto
TOTAL_COMPLEJOS = 51
TOTAL_ZONAS = 8
MEDIA_CIRCUNFERENCIA_KM = 20015
TAMANIO_PAGINA = 20
COMPLEJOS_EN_SAAVEDRA = 6
ID_DEL_NUEVO = TOTAL_COMPLEJOS + 1
ID_SAAVEDRA = 6
ID_BELGRANO = 5

COMPLEJO_NUEVO = {
    'zona': 'Belgrano',
    'localidad': 'Belgrano',
    'nombre': 'Cancha de Prueba',
    'direccion': 'Calle Falsa 123',
    'tipo': 'Campo de fútbol',
    'latitud': -34.56,
    'longitud': -58.45,
}


def test_listar_complejos_devuelve_la_primera_pagina(client):
    # Actuar
    respuesta = client.get('/complejos')

    # Afirmar
    assert respuesta.status_code == HTTPStatus.OK
    assert len(respuesta.json()['complejos']) == TAMANIO_PAGINA


def test_listar_complejos_con_limit_y_offset_pagina_el_resultado(client):
    # Actuar
    respuesta = client.get(
        '/complejos', params={'offset': TOTAL_COMPLEJOS - 1, 'limit': 100}
    )

    # Afirmar: queda solo el último complejo
    assert respuesta.status_code == HTTPStatus.OK
    assert len(respuesta.json()['complejos']) == 1


def test_listar_complejos_filtra_por_zona_sin_importar_mayusculas(client):
    # Actuar
    respuesta = client.get('/complejos', params={'zona': 'saavedra'})

    # Afirmar
    complejos = respuesta.json()['complejos']
    assert respuesta.status_code == HTTPStatus.OK
    assert len(complejos) == COMPLEJOS_EN_SAAVEDRA
    assert {c['zona'] for c in complejos} == {'Saavedra'}


def test_listar_complejos_de_una_zona_inexistente_devuelve_lista_vacia(client):
    # Actuar
    respuesta = client.get('/complejos', params={'zona': 'Zona Inventada'})

    # Afirmar
    assert respuesta.status_code == HTTPStatus.OK
    assert respuesta.json() == {'complejos': []}


def test_listar_complejos_con_limit_cero_devuelve_error_de_validacion(client):
    # Actuar
    respuesta = client.get('/complejos', params={'limit': 0})

    # Afirmar
    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_leer_complejo_existente_devuelve_sus_datos(client):
    # Actuar
    respuesta = client.get('/complejos/1')

    # Afirmar
    assert respuesta.status_code == HTTPStatus.OK
    assert respuesta.json()['id'] == 1
    assert respuesta.json()['nombre'] == 'Banco Fútbol'


def test_leer_complejo_inexistente_devuelve_no_encontrado(client):
    # Actuar
    respuesta = client.get('/complejos/9999')

    # Afirmar
    assert respuesta.status_code == HTTPStatus.NOT_FOUND
    assert respuesta.json() == {'detail': 'Complejo no encontrado'}


def test_crear_complejo_devuelve_creado_y_queda_consultable(client_admin):
    # Actuar
    respuesta = client_admin.post('/complejos', json=COMPLEJO_NUEVO)

    # Afirmar
    assert respuesta.status_code == HTTPStatus.CREATED
    nuevo_id = respuesta.json()['id']
    assert nuevo_id == ID_DEL_NUEVO
    consulta = client_admin.get(f'/complejos/{nuevo_id}')
    assert consulta.json()['nombre'] == 'Cancha de Prueba'


def test_crear_complejo_repetido_devuelve_conflicto(client_admin):
    # Organizar
    client_admin.post('/complejos', json=COMPLEJO_NUEVO)

    # Actuar
    respuesta = client_admin.post('/complejos', json=COMPLEJO_NUEVO)

    # Afirmar
    assert respuesta.status_code == HTTPStatus.CONFLICT


def test_crear_complejo_con_latitud_invalida_devuelve_error_de_validacion(
    client_admin,
):
    # Organizar
    datos = {**COMPLEJO_NUEVO, 'latitud': 200}

    # Actuar
    respuesta = client_admin.post('/complejos', json=datos)

    # Afirmar
    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_crear_complejo_con_zona_en_otras_mayusculas_usa_la_zona_existente(
    client_admin,
):
    # Organizar
    datos = {**COMPLEJO_NUEVO, 'zona': 'belgrano'}

    # Actuar
    respuesta = client_admin.post('/complejos', json=datos)

    # Afirmar: toma el nombre correcto y la provincia de la zona
    assert respuesta.status_code == HTTPStatus.CREATED
    assert respuesta.json()['zona'] == 'Belgrano'
    assert respuesta.json()['provincia'] == 'CABA'


def test_crear_complejo_descarta_la_provincia_enviada_por_el_cliente(
    client_admin,
):
    # Organizar
    datos = {**COMPLEJO_NUEVO, 'provincia': 'Buenos Aires'}

    # Actuar
    respuesta = client_admin.post('/complejos', json=datos)

    # Afirmar: manda la zona (Belgrano es de CABA)
    assert respuesta.json()['provincia'] == 'CABA'


def test_crear_complejo_con_nombre_vacio_devuelve_error_de_validacion(
    client_admin,
):
    # Organizar
    datos = {**COMPLEJO_NUEVO, 'nombre': '   '}

    # Actuar
    respuesta = client_admin.post('/complejos', json=datos)

    # Afirmar
    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_crear_complejo_despues_de_borrar_el_ultimo_no_reutiliza_su_id(
    client_admin,
):
    # Organizar
    client_admin.delete(f'/complejos/{TOTAL_COMPLEJOS}')

    # Actuar
    respuesta = client_admin.post('/complejos', json=COMPLEJO_NUEVO)

    # Afirmar
    assert respuesta.json()['id'] == ID_DEL_NUEVO
    assert (
        client_admin.get(f'/complejos/{TOTAL_COMPLEJOS}').status_code
        == HTTPStatus.NOT_FOUND
    )


def test_borrar_complejo_existente_lo_elimina(client_admin):
    # Actuar
    respuesta = client_admin.delete('/complejos/1')

    # Afirmar
    assert respuesta.status_code == HTTPStatus.OK
    assert respuesta.json() == {'mensaje': 'Complejo eliminado'}
    assert client_admin.get('/complejos/1').status_code == HTTPStatus.NOT_FOUND


def test_borrar_complejo_no_corre_los_ids_de_los_demas(client_admin):
    # Actuar
    client_admin.delete('/complejos/1')

    # Afirmar: el complejo 2 sigue siendo el 2 aunque ahora esté primero
    consulta = client_admin.get('/complejos/2')
    assert consulta.status_code == HTTPStatus.OK
    assert consulta.json()['nombre'] == 'PLT FÚTBOL'


def test_borrar_complejo_inexistente_devuelve_no_encontrado(client_admin):
    # Actuar
    respuesta = client_admin.delete('/complejos/9999')

    # Afirmar
    assert respuesta.status_code == HTTPStatus.NOT_FOUND
    assert respuesta.json() == {'detail': 'Complejo no encontrado'}


def test_listar_cercanos_ordena_del_mas_cercano_al_mas_lejano(client):
    # Organizar: coordenadas de Banco Fútbol (id 1), vecino de PLT FÚTBOL
    parametros = {
        'latitud': -34.5365512,
        'longitud': -58.471825,
        'radio_km': 1,
    }

    # Actuar
    respuesta = client.get('/complejos/cercanos', params=parametros)

    # Afirmar
    cercanos = respuesta.json()
    assert respuesta.status_code == HTTPStatus.OK
    nombres = [c['nombre'] for c in cercanos]
    assert nombres[:2] == ['Banco Fútbol', 'PLT FÚTBOL']
    assert cercanos[0]['distancia_km'] == 0
    assert cercanos[0]['distancia_km'] <= cercanos[1]['distancia_km']


def test_distancia_entre_puntos_opuestos_no_falla_y_es_media_circunferencia():
    # Organizar: El Portón de Nuñez y su antípoda. Con estas coordenadas la
    # fórmula da 1.0000000000000002, el borde donde asin() podría fallar.
    latitud, longitud = -34.5479089, -58.4637438

    # Actuar
    distancia = distancia_km(-latitud, longitud + 180, latitud, longitud)

    # Afirmar: media circunferencia terrestre, unos 20015 km
    assert round(distancia) == MEDIA_CIRCUNFERENCIA_KM


def test_leer_filas_con_bom_de_excel_conserva_el_nombre_de_la_primera_clave(
    tmp_path,
):
    # Organizar: Excel guarda el CSV UTF-8 con una marca al principio
    archivo = tmp_path / 'complejos.csv'
    archivo.write_text('﻿zona,provincia\nBelgrano,CABA\n', encoding='utf-8')

    # Actuar
    filas = leer_filas(archivo)

    # Afirmar
    assert filas == [{'zona': 'Belgrano', 'provincia': 'CABA'}]


def test_listar_cercanos_sin_complejos_en_el_radio_devuelve_lista_vacia(
    client,
):
    # Actuar: el punto 0,0 queda en el océano
    respuesta = client.get(
        '/complejos/cercanos',
        params={'latitud': 0, 'longitud': 0, 'radio_km': 5},
    )

    # Afirmar
    assert respuesta.status_code == HTTPStatus.OK
    assert respuesta.json() == []


def test_listar_zonas_devuelve_las_ocho_zonas_con_id_nombre_y_provincia(
    client,
):
    # Actuar
    respuesta = client.get('/zonas')

    # Afirmar: el id sigue el orden en que aparecen las zonas en el CSV
    assert respuesta.status_code == HTTPStatus.OK
    zonas = respuesta.json()['zonas']
    assert len(zonas) == TOTAL_ZONAS
    assert zonas[0] == {
        'id': 1,
        'nombre': 'Vicente López',
        'provincia': 'Buenos Aires',
    }
    assert zonas[3] == {'id': 4, 'nombre': 'Núñez', 'provincia': 'CABA'}


def test_crear_zona_devuelve_creado_y_aparece_en_el_listado(client_admin):
    # Actuar
    respuesta = client_admin.post(
        '/zonas', json={'nombre': 'Colegiales', 'provincia': 'CABA'}
    )

    # Afirmar
    assert respuesta.status_code == HTTPStatus.CREATED
    assert respuesta.json() == {
        'id': TOTAL_ZONAS + 1,
        'nombre': 'Colegiales',
        'provincia': 'CABA',
    }
    zonas = client_admin.get('/zonas').json()['zonas']
    assert len(zonas) == TOTAL_ZONAS + 1


def test_crear_zona_repetida_devuelve_conflicto(client_admin):
    # Actuar: minúsculas y espacios sobrantes también cuentan como repetida
    respuesta = client_admin.post(
        '/zonas', json={'nombre': ' belgrano ', 'provincia': 'CABA'}
    )

    # Afirmar
    assert respuesta.status_code == HTTPStatus.CONFLICT


def test_crear_zona_con_nombre_vacio_devuelve_error_de_validacion(
    client_admin,
):
    # Actuar
    respuesta = client_admin.post(
        '/zonas', json={'nombre': '', 'provincia': 'CABA'}
    )

    # Afirmar
    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_crear_complejo_en_una_zona_inexistente_devuelve_no_encontrado(
    client_admin,
):
    # Organizar
    datos = {**COMPLEJO_NUEVO, 'zona': 'Zona Inventada'}

    # Actuar
    respuesta = client_admin.post('/complejos', json=datos)

    # Afirmar
    assert respuesta.status_code == HTTPStatus.NOT_FOUND
    assert respuesta.json() == {'detail': 'La zona no existe'}


def test_crear_complejo_en_una_zona_recien_creada_funciona(client_admin):
    # Organizar
    client_admin.post(
        '/zonas', json={'nombre': 'Colegiales', 'provincia': 'CABA'}
    )
    datos = {**COMPLEJO_NUEVO, 'zona': 'Colegiales'}

    # Actuar
    respuesta = client_admin.post('/complejos', json=datos)

    # Afirmar
    assert respuesta.status_code == HTTPStatus.CREATED


def test_actualizar_complejo_reemplaza_sus_datos_y_conserva_el_id(
    client_admin,
):
    # Actuar
    respuesta = client_admin.put('/complejos/1', json=COMPLEJO_NUEVO)

    # Afirmar
    assert respuesta.status_code == HTTPStatus.OK
    assert respuesta.json()['id'] == 1
    consulta = client_admin.get('/complejos/1')
    assert consulta.json()['nombre'] == 'Cancha de Prueba'
    assert consulta.json()['direccion'] == 'Calle Falsa 123'


def test_actualizar_complejo_a_otra_zona_toma_su_nombre_y_provincia(
    client_admin,
):
    # Organizar: el complejo 1 está en Vicente López (Buenos Aires)
    datos = {**COMPLEJO_NUEVO, 'zona': 'belgrano'}

    # Actuar
    respuesta = client_admin.put('/complejos/1', json=datos)

    # Afirmar
    assert respuesta.json()['zona'] == 'Belgrano'
    assert respuesta.json()['provincia'] == 'CABA'


def test_actualizar_complejo_sin_cambiar_nombre_ni_direccion_funciona(
    client_admin,
):
    # Organizar: mismos datos del complejo 1, con otro teléfono
    actual = client_admin.get('/complejos/1').json()
    datos = {**actual, 'telefono_contacto': '011 4444-5555'}

    # Actuar
    respuesta = client_admin.put('/complejos/1', json=datos)

    # Afirmar: no es conflicto consigo mismo
    assert respuesta.status_code == HTTPStatus.OK
    assert respuesta.json()['telefono_contacto'] == '011 4444-5555'


def test_actualizar_complejo_con_nombre_y_direccion_de_otro_es_conflicto(
    client_admin,
):
    # Organizar: nombre y dirección del complejo 2
    datos = {
        **COMPLEJO_NUEVO,
        'nombre': 'PLT FÚTBOL',
        'direccion': 'Juan Zufriategui 1233',
    }

    # Actuar
    respuesta = client_admin.put('/complejos/1', json=datos)

    # Afirmar
    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json() == {
        'detail': 'Ya existe un complejo con ese nombre y dirección'
    }


def test_actualizar_complejo_inexistente_devuelve_no_encontrado(client_admin):
    # Actuar
    respuesta = client_admin.put('/complejos/9999', json=COMPLEJO_NUEVO)

    # Afirmar
    assert respuesta.status_code == HTTPStatus.NOT_FOUND
    assert respuesta.json() == {'detail': 'Complejo no encontrado'}


def test_actualizar_complejo_con_zona_inexistente_devuelve_no_encontrado(
    client_admin,
):
    # Organizar
    datos = {**COMPLEJO_NUEVO, 'zona': 'Zona Inventada'}

    # Actuar
    respuesta = client_admin.put('/complejos/1', json=datos)

    # Afirmar
    assert respuesta.status_code == HTTPStatus.NOT_FOUND
    assert respuesta.json() == {'detail': 'La zona no existe'}


def test_actualizar_complejo_con_datos_invalidos_devuelve_error(client_admin):
    # Organizar
    datos = {**COMPLEJO_NUEVO, 'longitud': -500}

    # Actuar
    respuesta = client_admin.put('/complejos/1', json=datos)

    # Afirmar
    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_actualizar_zona_cambia_el_nombre_que_ven_sus_complejos(client_admin):
    # Actuar
    respuesta = client_admin.put(
        f'/zonas/{ID_SAAVEDRA}',
        json={'nombre': 'Saavedra Norte', 'provincia': 'CABA'},
    )

    # Afirmar: los complejos de la zona la ven con su nombre nuevo
    assert respuesta.status_code == HTTPStatus.OK
    assert respuesta.json() == {
        'id': ID_SAAVEDRA,
        'nombre': 'Saavedra Norte',
        'provincia': 'CABA',
    }
    complejos = client_admin.get(
        '/complejos', params={'zona': 'Saavedra Norte'}
    ).json()['complejos']
    assert len(complejos) == COMPLEJOS_EN_SAAVEDRA


def test_actualizar_zona_cambiando_solo_sus_mayusculas_funciona(client_admin):
    # Actuar
    respuesta = client_admin.put(
        f'/zonas/{ID_BELGRANO}',
        json={'nombre': 'BELGRANO', 'provincia': 'CABA'},
    )

    # Afirmar: no es conflicto consigo misma
    assert respuesta.status_code == HTTPStatus.OK
    assert respuesta.json()['nombre'] == 'BELGRANO'


def test_actualizar_zona_con_el_nombre_de_otra_devuelve_conflicto(
    client_admin,
):
    # Actuar: la zona 1 es Vicente López
    respuesta = client_admin.put(
        '/zonas/1', json={'nombre': 'belgrano', 'provincia': 'CABA'}
    )

    # Afirmar
    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json() == {'detail': 'Ya existe una zona con ese nombre'}


def test_actualizar_zona_inexistente_devuelve_no_encontrado(client_admin):
    # Actuar
    respuesta = client_admin.put(
        '/zonas/9999', json={'nombre': 'Colegiales', 'provincia': 'CABA'}
    )

    # Afirmar
    assert respuesta.status_code == HTTPStatus.NOT_FOUND
    assert respuesta.json() == {'detail': 'Zona no encontrada'}

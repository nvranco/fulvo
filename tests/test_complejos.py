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


def test_crear_complejo_devuelve_creado_y_queda_consultable(client):
    # Actuar
    respuesta = client.post('/complejos', json=COMPLEJO_NUEVO)

    # Afirmar
    assert respuesta.status_code == HTTPStatus.CREATED
    nuevo_id = respuesta.json()['id']
    assert nuevo_id == ID_DEL_NUEVO
    consulta = client.get(f'/complejos/{nuevo_id}')
    assert consulta.json()['nombre'] == 'Cancha de Prueba'


def test_crear_complejo_repetido_devuelve_conflicto(client):
    # Organizar
    client.post('/complejos', json=COMPLEJO_NUEVO)

    # Actuar
    respuesta = client.post('/complejos', json=COMPLEJO_NUEVO)

    # Afirmar
    assert respuesta.status_code == HTTPStatus.CONFLICT


def test_crear_complejo_con_latitud_invalida_devuelve_error_de_validacion(
    client,
):
    # Organizar
    datos = {**COMPLEJO_NUEVO, 'latitud': 200}

    # Actuar
    respuesta = client.post('/complejos', json=datos)

    # Afirmar
    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_crear_complejo_con_zona_en_otras_mayusculas_usa_la_zona_existente(
    client,
):
    # Organizar
    datos = {**COMPLEJO_NUEVO, 'zona': 'belgrano'}

    # Actuar
    respuesta = client.post('/complejos', json=datos)

    # Afirmar: toma el nombre correcto y la provincia de la zona
    assert respuesta.status_code == HTTPStatus.CREATED
    assert respuesta.json()['zona'] == 'Belgrano'
    assert respuesta.json()['provincia'] == 'CABA'


def test_crear_complejo_descarta_la_provincia_enviada_por_el_cliente(client):
    # Organizar
    datos = {**COMPLEJO_NUEVO, 'provincia': 'Buenos Aires'}

    # Actuar
    respuesta = client.post('/complejos', json=datos)

    # Afirmar: manda la zona (Belgrano es de CABA)
    assert respuesta.json()['provincia'] == 'CABA'


def test_crear_complejo_con_nombre_vacio_devuelve_error_de_validacion(client):
    # Organizar
    datos = {**COMPLEJO_NUEVO, 'nombre': '   '}

    # Actuar
    respuesta = client.post('/complejos', json=datos)

    # Afirmar
    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_crear_complejo_despues_de_borrar_el_ultimo_no_reutiliza_su_id(
    client,
):
    # Organizar
    client.delete(f'/complejos/{TOTAL_COMPLEJOS}')

    # Actuar
    respuesta = client.post('/complejos', json=COMPLEJO_NUEVO)

    # Afirmar
    assert respuesta.json()['id'] == ID_DEL_NUEVO
    assert (
        client.get(f'/complejos/{TOTAL_COMPLEJOS}').status_code
        == HTTPStatus.NOT_FOUND
    )


def test_borrar_complejo_existente_lo_elimina(client):
    # Actuar
    respuesta = client.delete('/complejos/1')

    # Afirmar
    assert respuesta.status_code == HTTPStatus.OK
    assert respuesta.json() == {'mensaje': 'Complejo eliminado'}
    assert client.get('/complejos/1').status_code == HTTPStatus.NOT_FOUND


def test_borrar_complejo_no_corre_los_ids_de_los_demas(client):
    # Actuar
    client.delete('/complejos/1')

    # Afirmar: el complejo 2 sigue siendo el 2 aunque ahora esté primero
    consulta = client.get('/complejos/2')
    assert consulta.status_code == HTTPStatus.OK
    assert consulta.json()['nombre'] == 'PLT FÚTBOL'


def test_borrar_complejo_inexistente_devuelve_no_encontrado(client):
    # Actuar
    respuesta = client.delete('/complejos/9999')

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


def test_crear_zona_devuelve_creado_y_aparece_en_el_listado(client):
    # Actuar
    respuesta = client.post(
        '/zonas', json={'nombre': 'Colegiales', 'provincia': 'CABA'}
    )

    # Afirmar
    assert respuesta.status_code == HTTPStatus.CREATED
    assert respuesta.json() == {
        'id': TOTAL_ZONAS + 1,
        'nombre': 'Colegiales',
        'provincia': 'CABA',
    }
    zonas = client.get('/zonas').json()['zonas']
    assert len(zonas) == TOTAL_ZONAS + 1


def test_crear_zona_repetida_devuelve_conflicto(client):
    # Actuar: minúsculas y espacios sobrantes también cuentan como repetida
    respuesta = client.post(
        '/zonas', json={'nombre': ' belgrano ', 'provincia': 'CABA'}
    )

    # Afirmar
    assert respuesta.status_code == HTTPStatus.CONFLICT


def test_crear_zona_con_nombre_vacio_devuelve_error_de_validacion(client):
    # Actuar
    respuesta = client.post('/zonas', json={'nombre': '', 'provincia': 'CABA'})

    # Afirmar
    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_crear_complejo_en_una_zona_inexistente_devuelve_no_encontrado(
    client,
):
    # Organizar
    datos = {**COMPLEJO_NUEVO, 'zona': 'Zona Inventada'}

    # Actuar
    respuesta = client.post('/complejos', json=datos)

    # Afirmar
    assert respuesta.status_code == HTTPStatus.NOT_FOUND
    assert respuesta.json() == {'detail': 'La zona no existe'}


def test_crear_complejo_en_una_zona_recien_creada_funciona(client):
    # Organizar
    client.post('/zonas', json={'nombre': 'Colegiales', 'provincia': 'CABA'})
    datos = {**COMPLEJO_NUEVO, 'zona': 'Colegiales'}

    # Actuar
    respuesta = client.post('/complejos', json=datos)

    # Afirmar
    assert respuesta.status_code == HTTPStatus.CREATED

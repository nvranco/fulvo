from dataclasses import asdict
from datetime import datetime, timedelta

import pytest
from freezegun import freeze_time
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from fulvo.models import (
    DURACION_PARTIDO_MINUTOS,
    Complejo,
    EstadoPartido,
    Partido,
    TipoPartido,
    Zona,
    ahora_argentina,
)


def crear_zona(session) -> Zona:
    zona = Zona(nombre='Belgrano', provincia='CABA')
    session.add(zona)
    session.commit()
    return zona


def armar_complejo(zona: Zona, **cambios) -> Complejo:
    datos = {
        'zona_id': zona.id,
        'localidad': 'Belgrano',
        'nombre': 'Cancha Norte',
        'direccion': 'Av. Cabildo 1000',
        'tipo': 'Campo de fútbol',
        'latitud': -34.56,
        'longitud': -58.45,
    }
    return Complejo(**(datos | cambios))


def test_crear_zona_guarda_los_datos_y_asigna_id(session):
    session.add(Zona(nombre='Belgrano', provincia='CABA'))
    session.commit()

    zona = session.scalar(select(Zona).where(Zona.nombre == 'Belgrano'))

    assert asdict(zona) == {
        'id': 1,
        'nombre': 'Belgrano',
        'provincia': 'CABA',
    }


def test_crear_zona_con_nombre_repetido_falla(session):
    crear_zona(session)
    session.add(Zona(nombre='Belgrano', provincia='Buenos Aires'))

    with pytest.raises(IntegrityError):
        session.commit()


def test_crear_complejo_aplica_valores_por_defecto(session):
    zona = crear_zona(session)
    session.add(armar_complejo(zona))
    session.commit()

    complejo = session.scalar(select(Complejo))

    assert complejo.id == 1
    assert complejo.reserva_online is False
    assert complejo.telefono_contacto is None
    assert complejo.sitio_web is None
    assert complejo.calificacion_maps is None
    assert complejo.link_maps is None


def test_complejo_accede_a_su_zona_por_la_relacion(session):
    zona = crear_zona(session)
    session.add(armar_complejo(zona))
    session.commit()

    complejo = session.scalar(select(Complejo))

    assert complejo.zona.nombre == 'Belgrano'
    assert complejo.zona.provincia == 'CABA'


def test_crear_complejo_con_mismo_nombre_y_direccion_falla(session):
    zona = crear_zona(session)
    session.add(armar_complejo(zona))
    session.commit()
    session.add(armar_complejo(zona, localidad='Núñez'))

    with pytest.raises(IntegrityError):
        session.commit()


def test_mismo_nombre_de_complejo_en_otra_direccion_es_valido(session):
    zona = crear_zona(session)
    session.add(armar_complejo(zona))
    session.add(armar_complejo(zona, direccion='Av. Cabildo 2000'))

    session.commit()

    direcciones = session.scalars(select(Complejo.direccion)).all()
    assert direcciones == ['Av. Cabildo 1000', 'Av. Cabildo 2000']


def test_id_de_complejo_borrado_no_se_reutiliza(session):
    zona = crear_zona(session)
    primero = armar_complejo(zona)
    segundo = armar_complejo(zona, direccion='Av. Cabildo 2000')
    session.add_all([primero, segundo])
    session.commit()
    id_borrado = segundo.id
    session.delete(segundo)
    session.commit()

    tercero = armar_complejo(zona, direccion='Av. Cabildo 3000')
    session.add(tercero)
    session.commit()

    assert tercero.id == id_borrado + 1


INICIO = datetime(2026, 11, 20, 20, 0)


def partido_de_prueba(estado=EstadoPartido.abierto) -> Partido:
    """Partido sin guardar: para probar sus métodos no hace falta la base."""
    return Partido(
        organizador_id=1,
        complejo_id=1,
        inicio=INICIO,
        tipo=TipoPartido.F5,
        cupos_faltantes=2,
        estado=estado,
    )


def test_partido_nuevo_nace_abierto_y_dura_60_minutos(session, usuario):
    partido = Partido(
        organizador_id=usuario.id,
        complejo_id=1,
        inicio=INICIO,
        tipo=TipoPartido.F7,
        cupos_faltantes=3,
    )
    session.add(partido)
    session.commit()
    session.refresh(partido)

    # Los enums vuelven de la base como enums, no como texto.
    assert partido.estado is EstadoPartido.abierto
    assert partido.tipo is TipoPartido.F7
    assert partido.duracion_minutos == DURACION_PARTIDO_MINUTOS


def test_fin_del_partido_es_el_inicio_mas_la_duracion():
    assert partido_de_prueba().fin() == datetime(2026, 11, 20, 21, 0)


def test_actualizar_estado_antes_del_fin_no_cambia_nada():
    partido = partido_de_prueba()

    cambio = partido.actualizar_estado(INICIO + timedelta(minutes=59))

    assert cambio is False
    assert partido.estado is EstadoPartido.abierto


def test_actualizar_estado_justo_al_terminar_pasa_a_jugado():
    partido = partido_de_prueba()

    cambio = partido.actualizar_estado(partido.fin())

    assert cambio is True
    assert partido.estado is EstadoPartido.jugado


def test_actualizar_estado_de_un_completo_terminado_pasa_a_jugado():
    partido = partido_de_prueba(EstadoPartido.completo)

    partido.actualizar_estado(INICIO + timedelta(days=1))

    assert partido.estado is EstadoPartido.jugado


@pytest.mark.parametrize(
    'estado', [EstadoPartido.cancelado, EstadoPartido.jugado]
)
def test_actualizar_estado_de_un_cancelado_o_jugado_no_cambia(estado):
    partido = partido_de_prueba(estado)

    cambio = partido.actualizar_estado(INICIO + timedelta(days=1))

    assert cambio is False
    assert partido.estado is estado


def test_ahora_argentina_esta_tres_horas_antes_que_utc():
    with freeze_time('2026-11-20 15:00:00'):
        assert ahora_argentina() == datetime(2026, 11, 20, 12, 0)

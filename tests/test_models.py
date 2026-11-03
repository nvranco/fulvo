from dataclasses import asdict

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from fulvo.models import Complejo, Zona


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

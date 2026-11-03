from sqlalchemy import func, select

from fulvo.carga_inicial import cargar
from fulvo.models import Complejo, Zona

# Valores que salen de fulvo/datos/complejos.csv
TOTAL_ZONAS = 8
TOTAL_COMPLEJOS = 51
CALIFICACION_UNO = 4.5

ENCABEZADO = (
    'zona,provincia,localidad,nombre,direccion,telefono_contacto,tipo,'
    'reserva_online,sitio_web,calificacion_maps,latitud,longitud,link_maps\n'
)
FILA_UNO = (
    'Belgrano,CABA,Belgrano,Cancha Uno,Calle 1,,Campo,si,,4.5,-34.5,-58.4,\n'
)
FILA_DOS = (
    'Belgrano,CABA,Belgrano,Cancha Dos,Calle 2,,Campo,no,,,-34.6,-58.5,\n'
)


def escribir_csv(tmp_path, *filas):
    archivo = tmp_path / 'complejos.csv'
    archivo.write_text(ENCABEZADO + ''.join(filas), encoding='utf-8')
    return archivo


def test_cargar_el_csv_real_crea_todas_las_zonas_y_complejos(session):
    zonas, complejos = cargar(session)

    assert (zonas, complejos) == (TOTAL_ZONAS, TOTAL_COMPLEJOS)
    assert session.scalar(select(func.count(Zona.id))) == TOTAL_ZONAS
    assert session.scalar(select(func.count(Complejo.id))) == TOTAL_COMPLEJOS


def test_cargar_dos_veces_no_duplica_nada(session):
    cargar(session)

    zonas, complejos = cargar(session)

    assert (zonas, complejos) == (0, 0)
    assert session.scalar(select(func.count(Complejo.id))) == TOTAL_COMPLEJOS


def test_cargar_convierte_las_celdas_del_csv_en_sus_tipos(session, tmp_path):
    archivo = escribir_csv(tmp_path, FILA_UNO, FILA_DOS)

    cargar(session, archivo)

    uno, dos = session.scalars(select(Complejo).order_by(Complejo.id))
    assert uno.reserva_online is True
    assert uno.calificacion_maps == CALIFICACION_UNO
    assert uno.telefono_contacto is None
    assert dos.reserva_online is False
    assert dos.calificacion_maps is None
    assert uno.zona.nombre == dos.zona.nombre == 'Belgrano'


def test_cargar_reutiliza_una_zona_existente_sin_importar_mayusculas(
    session, tmp_path
):
    session.add(Zona(nombre='belgrano', provincia='CABA'))
    session.commit()
    archivo = escribir_csv(tmp_path, FILA_UNO)

    zonas, complejos = cargar(session, archivo)

    assert (zonas, complejos) == (0, 1)
    assert session.scalar(select(func.count(Zona.id))) == 1


def test_cargar_agrega_solo_los_complejos_que_faltan(session, tmp_path):
    cargar(session, escribir_csv(tmp_path, FILA_UNO))

    zonas, complejos = cargar(
        session, escribir_csv(tmp_path, FILA_UNO, FILA_DOS)
    )

    assert (zonas, complejos) == (0, 1)

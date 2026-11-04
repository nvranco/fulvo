from datetime import date
from http import HTTPStatus

from sqlalchemy import func, select

from fulvo.carga_inicial import cargar, cargar_admin, cargar_roles
from fulvo.database import get_session
from fulvo.models import ROL_ADMIN, ROLES_BASE, Complejo, Rol, Usuario, Zona
from fulvo.security import verificar_contrasena

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


def test_cargar_roles_crea_usuario_y_admin(session):
    creados = cargar_roles(session)

    nombres = set(session.scalars(select(Rol.nombre)))
    assert creados == len(ROLES_BASE)
    assert nombres == {'usuario', 'admin'}


def test_cargar_roles_dos_veces_no_duplica(session):
    cargar_roles(session)

    creados = cargar_roles(session)

    assert creados == 0
    assert session.scalar(select(func.count(Rol.id))) == len(ROLES_BASE)


def test_cargar_admin_crea_un_usuario_con_rol_admin(session):
    cargar_roles(session)

    creado = cargar_admin(session, 'Admin@Ejemplo.com', 'clave-del-admin')

    admin = session.scalars(select(Usuario)).one()
    assert creado is True
    assert admin.email == 'admin@ejemplo.com'
    assert admin.tiene_rol(ROL_ADMIN)
    assert verificar_contrasena('clave-del-admin', admin.contrasena_hash)


def test_cargar_admin_dos_veces_no_duplica(session):
    cargar_roles(session)
    cargar_admin(session, 'admin@ejemplo.com', 'clave-del-admin')

    creado = cargar_admin(session, 'admin@ejemplo.com', 'otra-clave')

    assert creado is False
    assert session.scalar(select(func.count(Usuario.id))) == 1


def test_cargar_admin_no_ascienda_a_un_usuario_existente(session):
    cargar_roles(session)
    comun = Usuario(
        email='ana@ejemplo.com',
        contrasena_hash='x',
        nombre='Ana',
        apellido='Pérez',
        whatsapp='1',
        fecha_nacimiento=date(1990, 1, 1),
        posicion='Arquera',
        rol_id=session.scalars(
            select(Rol.id).where(Rol.nombre == 'usuario')
        ).one(),
    )
    session.add(comun)
    session.commit()

    creado = cargar_admin(session, 'ana@ejemplo.com', 'clave-del-admin')

    assert creado is False
    assert not comun.tiene_rol(ROL_ADMIN)


def test_el_admin_cargado_puede_iniciar_sesion(client):
    # `client` ya cargó los roles; falta el admin.
    session = client.app.dependency_overrides[get_session]()
    cargar_admin(session, 'admin@ejemplo.com', 'clave-del-admin')

    respuesta = client.post(
        '/auth/token',
        data={'username': 'admin@ejemplo.com', 'password': 'clave-del-admin'},
    )

    assert respuesta.status_code == HTTPStatus.OK

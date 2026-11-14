import csv
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from fulvo.database import engine
from fulvo.models import ROL_ADMIN, ROLES_BASE, Complejo, Rol, Usuario, Zona
from fulvo.security import hashear_contrasena
from fulvo.settings import Settings

# El CSV vive dentro del paquete `fulvo/` y no en `docs/`: así viaja con el
# código al contenedor y al deploy sin depender de una carpeta de documentos.
RUTA_CSV = Path(__file__).resolve().parent / 'datos' / 'complejos.csv'


def leer_filas(ruta: Path = RUTA_CSV) -> list[dict[str, str]]:
    """Lee el CSV de complejos y devuelve una fila por complejo.

    Es el único lugar que sabe dónde está el archivo y cómo se abre.

    Se abre con `utf-8-sig` porque Excel guarda el CSV UTF-8 con una marca
    (BOM) al principio. Con `utf-8` a secas esa marca se pegaría al nombre
    de la primera columna y el arranque fallaría con un KeyError.
    """
    with ruta.open(encoding='utf-8-sig', newline='') as archivo:
        return list(csv.DictReader(archivo))


def cargar(session: Session, ruta: Path = RUTA_CSV) -> tuple[int, int]:
    """Carga las zonas y los complejos del CSV, solo en una base sin zonas.

    Devuelve cuántas zonas y cuántos complejos creó. Es la carga inicial:
    se hace una sola vez. Después las zonas y los complejos son del admin,
    que los edita y los borra por la API (RQ10). `entrypoint.sh` corre este
    script en cada arranque del contenedor, y antes agregaba lo que faltara:
    volvía un complejo borrado y se duplicaba uno renombrado. Por eso, si
    ya hay alguna zona, no hace nada (decisión del equipo del 2026-11-13).
    Se mira la tabla de zonas porque no tiene baja: si hay una, la carga ya
    se hizo. Correrla dos veces sigue sin duplicar nada.

    Las zonas se crean en el orden en que aparecen en el CSV, y los
    complejos en el orden de las filas. Sobre una base vacía los ids quedan
    1, 2, 3... siguiendo ese orden. Dentro del CSV, una zona se reconoce por
    su nombre sin importar mayúsculas y un complejo por su nombre y
    dirección, las mismas reglas que la API usa para rechazar duplicados.
    """
    if session.scalar(select(Zona.id).limit(1)) is not None:
        return 0, 0

    filas = leer_filas(ruta)

    # La base no tiene zonas, y por lo tanto tampoco complejos (todo
    # complejo es de una zona): `zonas` y `cargados` arrancan vacíos y solo
    # evitan repetir algo que aparezca dos veces en el CSV.
    zonas = {}
    for fila in filas:
        if fila['zona'].lower() not in zonas:
            zona = Zona(nombre=fila['zona'], provincia=fila['provincia'])
            session.add(zona)
            zonas[fila['zona'].lower()] = zona
    # flush envía los INSERT sin cerrar la transacción: las zonas nuevas
    # reciben su id, que los complejos necesitan como zona_id.
    session.flush()

    cargados = set()
    for fila in filas:
        clave = (fila['nombre'], fila['direccion'])
        if clave in cargados:
            continue
        session.add(
            Complejo(
                zona_id=zonas[fila['zona'].lower()].id,
                localidad=fila['localidad'],
                nombre=fila['nombre'],
                direccion=fila['direccion'],
                tipo=fila['tipo'],
                latitud=float(fila['latitud']),
                longitud=float(fila['longitud']),
                reserva_online=fila['reserva_online'] == 'si',
                # Las celdas vacías del CSV pasan a None.
                telefono_contacto=fila['telefono_contacto'] or None,
                sitio_web=fila['sitio_web'] or None,
                calificacion_maps=float(fila['calificacion_maps'])
                if fila['calificacion_maps']
                else None,
                link_maps=fila['link_maps'] or None,
            )
        )
        cargados.add(clave)

    # Un solo commit: si algo falla, no queda la carga a medias.
    session.commit()
    return len(zonas), len(cargados)


def cargar_roles(session: Session) -> int:
    """Inserta los roles base (usuario y admin) que todavía no están.

    Devuelve cuántos creó. Es idempotente, como `cargar`. Está separada de
    `cargar` para no cambiar lo que esa función devuelve. Los roles tienen
    que existir antes del primer registro: todo usuario nace con el rol
    `usuario`.
    """
    existentes = set(session.scalars(select(Rol.nombre)))
    nuevos = [n for n in ROLES_BASE if n not in existentes]
    session.add_all(Rol(nombre=nombre) for nombre in nuevos)
    session.commit()
    return len(nuevos)


def cargar_admin(session: Session, email: str, contrasena: str) -> bool:
    """Crea el primer usuario admin si no hay un usuario con ese email.

    Devuelve True si lo creó. Es idempotente: la segunda vez no crea nada.
    Si el email ya pertenece a un usuario (aunque no sea admin) no lo toca:
    ascender a alguien a admin de forma silenciosa sería un riesgo.

    Es la única forma de tener un admin: ningún endpoint asigna ese rol
    (requerimientos.md). Los roles tienen que existir antes (`cargar_roles`).

    El modelo exige nombre, apellido, WhatsApp, nacimiento y posición, que
    para el admin no tienen sentido: se completan con valores fijos.
    """
    email = email.lower()
    if session.scalar(select(Usuario).where(Usuario.email == email)):
        return False
    rol_id = session.scalars(
        select(Rol.id).where(Rol.nombre == ROL_ADMIN)
    ).one()
    session.add(
        Usuario(
            email=email,
            contrasena_hash=hashear_contrasena(contrasena),
            nombre='Admin',
            apellido='Fulvo',
            whatsapp='-',
            fecha_nacimiento=date(2000, 1, 1),
            posicion='Administrador',
            rol_id=rol_id,
        )
    )
    session.commit()
    return True


def main() -> None:
    """Carga roles, admin, zonas y complejos: `python -m fulvo.carga_inicial`.

    Las tablas tienen que existir: primero `alembic upgrade head`. El admin
    se crea solo si ADMIN_EMAIL y ADMIN_PASSWORD están definidas.
    """
    configuracion = Settings()
    with Session(engine) as session:
        roles = cargar_roles(session)
        zonas, complejos = cargar(session)
        if configuracion.ADMIN_EMAIL and configuracion.ADMIN_PASSWORD:
            creado = cargar_admin(
                session,
                configuracion.ADMIN_EMAIL,
                configuracion.ADMIN_PASSWORD,
            )
            admin = 'creado' if creado else 'ya existía'
        else:
            admin = 'no creado (faltan ADMIN_EMAIL y ADMIN_PASSWORD)'
    print(f'Roles creados: {roles}.')
    print(f'Zonas creadas: {zonas}. Complejos creados: {complejos}.')
    print(f'Admin: {admin}.')


if __name__ == '__main__':
    main()

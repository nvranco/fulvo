import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from fulvo.database import engine
from fulvo.models import Complejo, Zona

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
    """Inserta en la base las zonas y complejos del CSV que todavía no están.

    Devuelve cuántas zonas y cuántos complejos creó. Es idempotente: se
    puede correr las veces que haga falta, y la segunda vez no crea nada.
    Una zona ya existente se reconoce por su nombre (sin importar
    mayúsculas) y un complejo por su nombre y dirección, las mismas reglas
    que la API usa para rechazar duplicados.

    Las zonas se crean en el orden en que aparecen en el CSV, y los
    complejos en el orden de las filas. Sobre una base vacía los ids quedan
    1, 2, 3... siguiendo ese orden.
    """
    filas = leer_filas(ruta)

    zonas = {z.nombre.lower(): z for z in session.scalars(select(Zona))}
    zonas_creadas = 0
    for fila in filas:
        if fila['zona'].lower() not in zonas:
            zona = Zona(nombre=fila['zona'], provincia=fila['provincia'])
            session.add(zona)
            zonas[fila['zona'].lower()] = zona
            zonas_creadas += 1
    # flush envía los INSERT sin cerrar la transacción: las zonas nuevas
    # reciben su id, que los complejos necesitan como zona_id.
    session.flush()

    claves = select(Complejo.nombre, Complejo.direccion)
    existentes = set(session.execute(claves).all())
    complejos_creados = 0
    for fila in filas:
        clave = (fila['nombre'], fila['direccion'])
        if clave in existentes:
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
        existentes.add(clave)
        complejos_creados += 1

    # Un solo commit: si algo falla, no queda la carga a medias.
    session.commit()
    return zonas_creadas, complejos_creados


def main() -> None:
    """Carga el CSV en la base configurada: `python -m fulvo.carga_inicial`.

    Las tablas tienen que existir: primero `alembic upgrade head`.
    """
    with Session(engine) as session:
        zonas, complejos = cargar(session)
    print(f'Zonas creadas: {zonas}. Complejos creados: {complejos}.')


if __name__ == '__main__':
    main()

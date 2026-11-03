from http import HTTPStatus
from pathlib import Path

from fastapi import APIRouter, HTTPException

from fulvo.carga_inicial import RUTA_CSV, leer_filas
from fulvo.schemas import ListaZonas, ZonaEntrada, ZonaPublica
from fulvo.secuencia import Secuencia

router = APIRouter(prefix='/zonas', tags=['zonas'])


def cargar_zonas(ruta: Path = RUTA_CSV) -> list[ZonaPublica]:
    """Arma la lista inicial de zonas a partir del CSV, con ids desde 1.

    El CSV no tiene una fila por zona sino una por complejo, así que se
    toma cada zona una sola vez, con la provincia del primer complejo que
    la trae y en el orden en que aparece.
    """
    provincia_por_zona: dict[str, str] = {}
    for fila in leer_filas(ruta):
        provincia_por_zona.setdefault(fila['zona'], fila['provincia'])
    return [
        ZonaPublica(id=numero, nombre=nombre, provincia=provincia)
        for numero, (nombre, provincia) in enumerate(
            provincia_por_zona.items(), start=1
        )
    ]


# Igual que `complejos`: lista en memoria que se reemplazará por una tabla
# de SQLAlchemy. Un complejo apunta a su zona por el nombre; con la base de
# datos será una clave foránea al id.
zonas: list[ZonaPublica] = cargar_zonas()
ids_zonas = Secuencia(len(zonas))


def buscar_zona(nombre: str) -> ZonaPublica | None:
    """Busca una zona por nombre sin distinguir mayúsculas, o None.

    Lo usan crear_zona y la creación de complejos, para que "belgrano" y
    "Belgrano" se traten siempre como la misma zona.
    """
    for zona in zonas:
        if zona.nombre.lower() == nombre.lower():
            return zona
    return None


@router.get('', response_model=ListaZonas)
def listar_zonas():
    """Lista las zonas disponibles (RQ3)."""
    return {'zonas': zonas}


@router.post('', status_code=HTTPStatus.CREATED, response_model=ZonaPublica)
def crear_zona(datos: ZonaEntrada):
    """Crea una zona nueva. 409 si ya existe una con ese nombre."""
    if buscar_zona(datos.nombre):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Ya existe una zona con ese nombre',
        )
    nueva = ZonaPublica(id=ids_zonas.siguiente(), **datos.model_dump())
    zonas.append(nueva)
    return nueva

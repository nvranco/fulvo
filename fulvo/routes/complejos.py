from http import HTTPStatus
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from fulvo.carga_inicial import RUTA_CSV, leer_filas
from fulvo.routes.zonas import buscar_zona
from fulvo.schemas import (
    ComplejoCercano,
    ComplejoEntrada,
    ComplejoPublico,
    ListaComplejos,
    Mensaje,
)
from fulvo.secuencia import Secuencia

router = APIRouter(prefix='/complejos', tags=['complejos'])

RADIO_TIERRA_KM = 6371


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en km entre dos puntos (fórmula de haversine).

    Se calcula en Python para no depender de la base de datos: sirve igual
    con la lista en memoria de hoy y con SQLite o PostgreSQL más adelante.
    """
    dif_lat = radians(lat2 - lat1)
    dif_lon = radians(lon2 - lon1)
    a = (
        sin(dif_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dif_lon / 2) ** 2
    )
    # min(1, ...): protección por si el redondeo deja sqrt(a) apenas por
    # encima de 1, que está fuera del dominio de asin() (ValueError). En las
    # pruebas con antípodas de los complejos del CSV no llegó a ocurrir.
    return 2 * RADIO_TIERRA_KM * asin(min(1, sqrt(a)))


def cargar_csv(ruta: Path = RUTA_CSV) -> list[ComplejoPublico]:
    """Lee el CSV de complejos y arma la lista inicial, con ids desde 1.

    Las celdas vacías pasan a None. Pydantic convierte los textos de
    coordenadas y calificación a número, y valida los rangos.
    """
    return [
        ComplejoPublico(
            id=numero,
            zona=fila['zona'],
            provincia=fila['provincia'],
            localidad=fila['localidad'],
            nombre=fila['nombre'],
            direccion=fila['direccion'],
            telefono_contacto=fila['telefono_contacto'] or None,
            tipo=fila['tipo'],
            reserva_online=fila['reserva_online'] == 'si',
            sitio_web=fila['sitio_web'] or None,
            calificacion_maps=fila['calificacion_maps'] or None,
            latitud=fila['latitud'],
            longitud=fila['longitud'],
            link_maps=fila['link_maps'] or None,
        )
        for numero, fila in enumerate(leer_filas(ruta), start=1)
    ]


# "Base de datos" provisional en memoria, como en la lección 03. Se pierde
# al reiniciar y se reemplazará por SQLAlchemy cuando toque.
complejos: list[ComplejoPublico] = cargar_csv()
ids_complejos = Secuencia(len(complejos))


@router.get('', response_model=ListaComplejos)
def listar_complejos(
    zona: str | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """Lista complejos, con filtro opcional por zona y paginación."""
    resultado = complejos
    if zona:
        resultado = [c for c in complejos if c.zona.lower() == zona.lower()]
    return {'complejos': resultado[offset : offset + limit]}


# Va antes de '/{complejo_id}': si no, FastAPI tomaría "cercanos" como un id.
@router.get('/cercanos', response_model=list[ComplejoCercano])
def listar_cercanos(
    latitud: Annotated[float, Query(ge=-90, le=90)],
    longitud: Annotated[float, Query(ge=-180, le=180)],
    radio_km: Annotated[float, Query(gt=0, le=50)],
):
    """Complejos dentro del radio, del más cercano al más lejano (RQ3)."""
    cercanos = []
    for complejo in complejos:
        distancia = distancia_km(
            latitud, longitud, complejo.latitud, complejo.longitud
        )
        if distancia <= radio_km:
            cercanos.append(
                ComplejoCercano(
                    **complejo.model_dump(), distancia_km=round(distancia, 2)
                )
            )
    return sorted(cercanos, key=lambda c: c.distancia_km)


def buscar_complejo(complejo_id: int) -> ComplejoPublico:
    """Devuelve el complejo con ese id, o levanta 404 si no existe.

    Lo usan la lectura y el borrado, así el 404 y su mensaje viven en un
    solo lugar. Se busca por id y no por posición en la lista: al borrar,
    las posiciones se corren y dejan de coincidir con los ids.
    """
    for complejo in complejos:
        if complejo.id == complejo_id:
            return complejo
    raise HTTPException(
        status_code=HTTPStatus.NOT_FOUND, detail='Complejo no encontrado'
    )


@router.get('/{complejo_id}', response_model=ComplejoPublico)
def leer_complejo(complejo_id: int):
    """Devuelve un complejo por id, o 404 si no existe."""
    return buscar_complejo(complejo_id)


@router.delete('/{complejo_id}', response_model=Mensaje)
def borrar_complejo(complejo_id: int):
    """Elimina un complejo por id, o 404 si no existe."""
    complejos.remove(buscar_complejo(complejo_id))
    return {'mensaje': 'Complejo eliminado'}


@router.post(
    '', status_code=HTTPStatus.CREATED, response_model=ComplejoPublico
)
def crear_complejo(datos: ComplejoEntrada):
    """Carga un complejo nuevo.

    404 si la zona no existe (todo complejo pertenece a una zona) y 409 si
    el nombre ya existe en esa dirección.
    """
    zona = buscar_zona(datos.zona)
    if zona is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='La zona no existe'
        )
    if any(
        c.nombre == datos.nombre and c.direccion == datos.direccion
        for c in complejos
    ):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Ya existe un complejo con ese nombre y dirección',
        )
    # La zona y la provincia salen de la zona hallada: se guarda el nombre
    # con su ortografía correcta y la provincia no se puede contradecir.
    datos_complejo = datos.model_dump() | {'zona': zona.nombre}
    nuevo = ComplejoPublico(
        id=ids_complejos.siguiente(),
        provincia=zona.provincia,
        **datos_complejo,
    )
    complejos.append(nuevo)
    return nuevo

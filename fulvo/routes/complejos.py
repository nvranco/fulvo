from http import HTTPStatus
from math import asin, cos, radians, sin, sqrt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from fulvo.database import get_session
from fulvo.models import Complejo, Partido, Zona
from fulvo.routes.zonas import buscar_zona
from fulvo.schemas import (
    ComplejoCercano,
    ComplejoEntrada,
    ComplejoPublico,
    ListaComplejos,
    Mensaje,
)
from fulvo.security import exigir_admin

router = APIRouter(prefix='/complejos', tags=['complejos'])
Session = Annotated[Session, Depends(get_session)]

RADIO_TIERRA_KM = 6371


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en km entre dos puntos (fórmula de haversine).

    Se calcula en Python para no depender de la base de datos: funciona
    igual en SQLite y en PostgreSQL.
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


def complejo_publico(complejo: Complejo) -> ComplejoPublico:
    """Arma la respuesta de la API a partir del modelo.

    El modelo guarda `zona_id` y la API expone el nombre de la zona y su
    provincia, así que no se puede leer directo con `from_attributes`: acá
    se traduce. Los datos de la zona salen de `complejo.zona`, que
    SQLAlchemy carga solo la primera vez que se lee.
    """
    return ComplejoPublico(
        id=complejo.id,
        zona=complejo.zona.nombre,
        provincia=complejo.zona.provincia,
        localidad=complejo.localidad,
        nombre=complejo.nombre,
        direccion=complejo.direccion,
        telefono_contacto=complejo.telefono_contacto,
        tipo=complejo.tipo,
        reserva_online=complejo.reserva_online,
        sitio_web=complejo.sitio_web,
        calificacion_maps=complejo.calificacion_maps,
        latitud=complejo.latitud,
        longitud=complejo.longitud,
        link_maps=complejo.link_maps,
    )


@router.get('', response_model=ListaComplejos)
def listar_complejos(
    session: Session,
    zona: str | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """Lista complejos, con filtro opcional por zona y paginación."""
    consulta = select(Complejo).order_by(Complejo.id)
    if zona:
        zona_hallada = buscar_zona(session, zona)
        if zona_hallada is None:
            return {'complejos': []}
        consulta = consulta.where(Complejo.zona_id == zona_hallada.id)
    complejos = session.scalars(consulta.offset(offset).limit(limit))
    return {'complejos': [complejo_publico(c) for c in complejos]}


# Va antes de '/{complejo_id}': si no, FastAPI tomaría "cercanos" como un id.
@router.get('/cercanos', response_model=list[ComplejoCercano])
def listar_cercanos(
    session: Session,
    latitud: Annotated[float, Query(ge=-90, le=90)],
    longitud: Annotated[float, Query(ge=-180, le=180)],
    radio_km: Annotated[float, Query(gt=0, le=50)],
):
    """Complejos dentro del radio, del más cercano al más lejano (RQ3)."""
    cercanos = []
    for complejo in session.scalars(select(Complejo)):
        distancia = distancia_km(
            latitud, longitud, complejo.latitud, complejo.longitud
        )
        if distancia <= radio_km:
            cercanos.append(
                ComplejoCercano(
                    **complejo_publico(complejo).model_dump(),
                    distancia_km=round(distancia, 2),
                )
            )
    return sorted(cercanos, key=lambda c: c.distancia_km)


def buscar_complejo(session: Session, complejo_id: int) -> Complejo:
    """Devuelve el complejo con ese id, o levanta 404 si no existe.

    Lo usan la lectura y el borrado, así el 404 y su mensaje viven en un
    solo lugar.
    """
    complejo = session.get(Complejo, complejo_id)
    if complejo is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Complejo no encontrado'
        )
    return complejo


@router.get('/{complejo_id}', response_model=ComplejoPublico)
def leer_complejo(complejo_id: int, session: Session):
    """Devuelve un complejo por id, o 404 si no existe."""
    return complejo_publico(buscar_complejo(session, complejo_id))


@router.delete(
    '/{complejo_id}',
    response_model=Mensaje,
    dependencies=[Depends(exigir_admin)],
)
def borrar_complejo(complejo_id: int, session: Session):
    """Elimina un complejo por id (RQ10, solo admin).

    404 si no existe y 409 si tiene partidos, de cualquier estado: un
    partido jugado o cancelado también apunta a su complejo, y quedaría
    huérfano (decisión del equipo del 2026-11-07).
    """
    complejo = buscar_complejo(session, complejo_id)
    un_partido = session.scalar(
        select(Partido.id).where(Partido.complejo_id == complejo.id).limit(1)
    )
    if un_partido is not None:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Error al borrar el complejo: aún tiene partidos agendados',
        )
    session.delete(complejo)
    session.commit()
    return {'mensaje': 'Complejo eliminado'}


def buscar_zona_del_complejo(session: Session, nombre: str) -> Zona:
    """Devuelve la zona por nombre, o levanta 404 si no existe.

    Todo complejo pertenece a una zona. Lo usan el alta y la edición, así
    el 404 y su mensaje viven en un solo lugar.
    """
    zona = buscar_zona(session, nombre)
    if zona is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='La zona no existe'
        )
    return zona


def rechazar_repetido(
    session: Session, datos: ComplejoEntrada, complejo_id: int | None = None
) -> None:
    """Levanta 409 si otro complejo ya tiene ese nombre y esa dirección.

    `complejo_id` es el complejo que se está editando: no cuenta como
    repetido de sí mismo, así se puede editar sin cambiar nombre ni
    dirección.
    """
    consulta = select(Complejo).where(
        Complejo.nombre == datos.nombre,
        Complejo.direccion == datos.direccion,
    )
    if complejo_id is not None:
        consulta = consulta.where(Complejo.id != complejo_id)
    if session.scalar(consulta):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Ya existe un complejo con ese nombre y dirección',
        )


@router.post(
    '',
    status_code=HTTPStatus.CREATED,
    response_model=ComplejoPublico,
    dependencies=[Depends(exigir_admin)],
)
def crear_complejo(datos: ComplejoEntrada, session: Session):
    """Carga un complejo nuevo (RQ10, solo admin).

    404 si la zona no existe (todo complejo pertenece a una zona) y 409 si
    el nombre ya existe en esa dirección.
    """
    zona = buscar_zona_del_complejo(session, datos.zona)
    rechazar_repetido(session, datos)
    # Se guarda el id de la zona hallada: así la zona se escribe siempre con
    # su ortografía correcta y la provincia sale de ella, sin poder
    # contradecirse con lo que mande el cliente.
    complejo = Complejo(zona_id=zona.id, **datos.model_dump(exclude={'zona'}))
    session.add(complejo)
    session.commit()
    session.refresh(complejo)
    return complejo_publico(complejo)


@router.put(
    '/{complejo_id}',
    response_model=ComplejoPublico,
    dependencies=[Depends(exigir_admin)],
)
def actualizar_complejo(
    complejo_id: int, datos: ComplejoEntrada, session: Session
):
    """Reemplaza todos los datos de un complejo (RQ10).

    Es un PUT: recibe el complejo completo, igual que el alta, y aplica sus
    mismas reglas. 404 si el complejo o la zona no existen, y 409 si el
    nombre y la dirección ya son de otro complejo. El id no cambia.
    """
    complejo = buscar_complejo(session, complejo_id)
    zona = buscar_zona_del_complejo(session, datos.zona)
    rechazar_repetido(session, datos, complejo_id)
    complejo.zona_id = zona.id
    for campo, valor in datos.model_dump(exclude={'zona'}).items():
        setattr(complejo, campo, valor)
    session.commit()
    session.refresh(complejo)
    return complejo_publico(complejo)

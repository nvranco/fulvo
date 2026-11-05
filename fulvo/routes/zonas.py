from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from fulvo.database import get_session
from fulvo.models import Zona
from fulvo.schemas import ListaZonas, ZonaEntrada, ZonaPublica
from fulvo.security import exigir_admin

router = APIRouter(prefix='/zonas', tags=['zonas'])
Session = Annotated[Session, Depends(get_session)]


def buscar_zona(session: Session, nombre: str) -> Zona | None:
    """Busca una zona por nombre sin distinguir mayúsculas, o None.

    Lo usan crear_zona y la creación y el filtro de complejos, para que
    "belgrano" y "Belgrano" se traten siempre como la misma zona.

    La comparación se resuelve en Python y no con `lower()` de SQL: el
    `lower()` de SQLite solo entiende ASCII (no pasa "NÚÑEZ" a "núñez") y el
    de PostgreSQL sí, y la API se comportaría distinto según la base. Las
    zonas son pocas, así que recorrerlas es barato.
    """
    for zona in session.scalars(select(Zona)):
        if zona.nombre.lower() == nombre.lower():
            return zona
    return None


@router.get('', response_model=ListaZonas)
def listar_zonas(session: Session):
    """Lista las zonas disponibles (RQ3)."""
    return {'zonas': session.scalars(select(Zona).order_by(Zona.id)).all()}


@router.post(
    '',
    status_code=HTTPStatus.CREATED,
    response_model=ZonaPublica,
    dependencies=[Depends(exigir_admin)],
)
def crear_zona(datos: ZonaEntrada, session: Session):
    """Crea una zona nueva (RQ10, solo admin). 409 si el nombre existe."""
    if buscar_zona(session, datos.nombre):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Ya existe una zona con ese nombre',
        )
    zona = Zona(**datos.model_dump())
    session.add(zona)
    session.commit()
    session.refresh(zona)
    return zona


@router.put(
    '/{zona_id}',
    response_model=ZonaPublica,
    dependencies=[Depends(exigir_admin)],
)
def actualizar_zona(zona_id: int, datos: ZonaEntrada, session: Session):
    """Reemplaza el nombre y la provincia de una zona (RQ10, solo admin).

    404 si no existe y 409 si el nombre nuevo ya es de otra zona. Los
    complejos guardan el id de su zona, así que ven el cambio solos:
    también la provincia, que leen de la zona.
    """
    zona = session.get(Zona, zona_id)
    if zona is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Zona no encontrada'
        )
    otra = buscar_zona(session, datos.nombre)
    # La misma zona sí puede cambiar solo las mayúsculas de su nombre.
    if otra is not None and otra.id != zona.id:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Ya existe una zona con ese nombre',
        )
    zona.nombre = datos.nombre
    zona.provincia = datos.provincia
    session.commit()
    session.refresh(zona)
    return zona

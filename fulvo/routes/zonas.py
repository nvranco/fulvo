from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from fulvo.database import get_session
from fulvo.models import Zona
from fulvo.schemas import ListaZonas, ZonaEntrada, ZonaPublica

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


@router.post('', status_code=HTTPStatus.CREATED, response_model=ZonaPublica)
def crear_zona(datos: ZonaEntrada, session: Session):
    """Crea una zona nueva. 409 si ya existe una con ese nombre."""
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

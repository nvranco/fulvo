from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from fulvo.database import get_session
from fulvo.models import Postulacion
from fulvo.routes.partidos import (
    buscar_partido,
    mi_postulacion,
    preparar_partido,
)
from fulvo.schemas import (
    ListaMisPostulaciones,
    MiPostulacion,
    Paginacion,
    PostulacionRetiro,
)
from fulvo.security import UsuarioActual

# Las rutas del jugador. Las del organizador están en `partidos.py`, bajo
# `/partidos/{id}/postulaciones`, porque siempre parten de su partido.
router = APIRouter(prefix='/postulaciones', tags=['postulaciones'])
Session = Annotated[Session, Depends(get_session)]


@router.get('', response_model=ListaMisPostulaciones)
def listar_mis_postulaciones(
    jugador: UsuarioActual,
    session: Session,
    filtro: Annotated[Paginacion, Query()],
):
    """Postulaciones del usuario, de la más nueva a la más vieja (RQ5).

    Cada una trae su partido y, si está aceptada, el WhatsApp del
    organizador (RQ6). Antes prepara cada partido (observadores y pase a
    jugado), como cualquier consulta de un partido.
    """
    consulta = (
        select(Postulacion)
        .where(Postulacion.jugador_id == jugador.id)
        .order_by(Postulacion.id.desc())
        .offset(filtro.offset)
        .limit(filtro.limit)
    )
    postulaciones = session.scalars(consulta).all()
    for postulacion in postulaciones:
        preparar_partido(session, postulacion.partido)
    session.commit()
    return {'postulaciones': [mi_postulacion(p) for p in postulaciones]}


@router.patch('/{postulacion_id}', response_model=MiPostulacion)
def retirar_postulacion(
    postulacion_id: int,
    datos: PostulacionRetiro,
    jugador: UsuarioActual,
    session: Session,
):
    """El jugador retira su postulación o, si estaba aceptado, se baja (RQ7).

    `datos` solo valida que se pida "retirada". 404 si no existe, 403 si
    no es suya y 409 si ya no se puede retirar.
    """
    postulacion = session.get(Postulacion, postulacion_id)
    if postulacion is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Postulación no encontrada',
        )
    if postulacion.jugador_id != jugador.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Solo el jugador de la postulación puede retirarla',
        )
    partido = buscar_partido(session, postulacion.partido_id)
    partido.retirar(postulacion)
    session.commit()
    return mi_postulacion(postulacion)

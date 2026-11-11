from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from fulvo.database import get_session
from fulvo.models import Notificacion
from fulvo.schemas import (
    FiltroNotificaciones,
    ListaNotificaciones,
    NotificacionLectura,
    NotificacionPublica,
)
from fulvo.security import UsuarioActual

# Las notificaciones las crea `NotificadorPartido` cuando pasa algo en un
# partido. Acá cada usuario solo lee las suyas y las marca como leídas.
router = APIRouter(prefix='/notificaciones', tags=['notificaciones'])
Session = Annotated[Session, Depends(get_session)]


@router.get('', response_model=ListaNotificaciones)
def listar_mis_notificaciones(
    usuario: UsuarioActual,
    session: Session,
    filtro: Annotated[FiltroNotificaciones, Query()],
):
    """Notificaciones del usuario, de la más nueva a la más vieja (RQ9).

    Con `leida=false` se ven solo las que todavía no leyó.
    """
    consulta = select(Notificacion).where(
        Notificacion.usuario_id == usuario.id
    )
    if filtro.leida is not None:
        consulta = consulta.where(Notificacion.leida == filtro.leida)
    consulta = (
        consulta
        .order_by(Notificacion.id.desc())
        .offset(filtro.offset)
        .limit(filtro.limit)
    )
    return {'notificaciones': session.scalars(consulta).all()}


@router.patch('/{notificacion_id}', response_model=NotificacionPublica)
def marcar_notificacion_leida(
    notificacion_id: int,
    datos: NotificacionLectura,
    usuario: UsuarioActual,
    session: Session,
):
    """Marca una notificación como leída (RQ9).

    `datos` solo valida que se pida `{"leida": true}`. 404 si no existe y
    403 si es de otro usuario.
    """
    notificacion = session.get(Notificacion, notificacion_id)
    if notificacion is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Notificación no encontrada',
        )
    if notificacion.usuario_id != usuario.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Solo el destinatario puede marcar la notificación',
        )
    notificacion.marcar_leida()
    session.commit()
    return notificacion

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from fulvo.database import get_session
from fulvo.models import Sancion, Usuario, ahora_argentina
from fulvo.routes.partidos import sacar_de_partidos_por_jugar
from fulvo.schemas import (
    ListaSanciones,
    Paginacion,
    SancionCierre,
    SancionEntrada,
    SancionPublica,
    UsuarioPublico,
)
from fulvo.security import AdminActual, exigir_admin

# Bloquear es crear una sanción y desbloquear es cerrarla, así que las rutas
# van sobre las sanciones del usuario (decisión del equipo del 2026-11-12).
# Todo el recurso es solo para el admin (RQ10): la dependencia del router
# responde 401 sin token y 403 a un usuario común, antes de cada ruta.
router = APIRouter(
    prefix='/usuarios/{usuario_id}/sanciones',
    tags=['sanciones'],
    dependencies=[Depends(exigir_admin)],
)
Session = Annotated[Session, Depends(get_session)]


def sancion_publica(sancion: Sancion) -> SancionPublica:
    """Arma la sanción como la ve el admin.

    No alcanza con `from_attributes`: `activa` es un método del modelo y
    no una columna, así que los campos se pasan a mano.
    """
    return SancionPublica(
        id=sancion.id,
        usuario_id=sancion.usuario_id,
        motivo=sancion.motivo,
        desde=sancion.desde,
        hasta=sancion.hasta,
        activa=sancion.activa(),
        aplicada_por=UsuarioPublico.model_validate(sancion.aplicada_por),
    )


def buscar_usuario(session: Session, usuario_id: int) -> Usuario:
    """Devuelve el usuario con ese id, o levanta 404.

    Lo usan las tres rutas, así el 404 y su mensaje viven en un solo lugar.
    """
    usuario = session.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Usuario no encontrado'
        )
    return usuario


@router.post('', status_code=HTTPStatus.CREATED, response_model=SancionPublica)
def bloquear_usuario(
    usuario_id: int,
    datos: SancionEntrada,
    admin: AdminActual,
    session: Session,
):
    """Bloquea al usuario y registra la sanción (RQ10, solo admin).

    404 si el usuario no existe, y 409 si es admin o ya está bloqueado.
    Además cancela los partidos que organiza y lo saca de los partidos a
    los que se postuló, si todavía no empezaron: un bloqueado ya no puede
    entrar a coordinarlos. Todo se guarda en un solo commit.
    """
    usuario = buscar_usuario(session, usuario_id)
    sancion = usuario.bloquear(admin, datos.motivo, ahora_argentina())
    sacar_de_partidos_por_jugar(session, usuario)
    session.commit()
    return sancion_publica(sancion)


@router.get('', response_model=ListaSanciones)
def listar_sanciones(
    usuario_id: int,
    session: Session,
    paginacion: Annotated[Paginacion, Query()],
):
    """Historial de sanciones del usuario, de la más nueva a la más vieja.

    Muestra las activas y las cerradas (RQ10). 404 si el usuario no existe.
    """
    usuario = buscar_usuario(session, usuario_id)
    sanciones = session.scalars(
        select(Sancion)
        .where(Sancion.usuario_id == usuario.id)
        .order_by(Sancion.id.desc())
        .offset(paginacion.offset)
        .limit(paginacion.limit)
    ).all()
    return {'sanciones': [sancion_publica(s) for s in sanciones]}


@router.patch('/{sancion_id}', response_model=SancionPublica)
def desbloquear_usuario(
    usuario_id: int,
    sancion_id: int,
    datos: SancionCierre,
    session: Session,
):
    """Desbloquea al usuario cerrando su sanción (RQ10, solo admin).

    Es PATCH porque la sanción no se borra: queda cerrada, con su fecha de
    fin. `datos` solo valida que se pida `{"activa": false}`. 404 si el
    usuario o la sanción no existen, o si la sanción es de otro usuario, y
    409 si ya estaba cerrada. Los partidos cancelados y las postulaciones
    retiradas al bloquear no vuelven.
    """
    usuario = buscar_usuario(session, usuario_id)
    sancion = session.get(Sancion, sancion_id)
    if sancion is None or sancion.usuario_id != usuario.id:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Sanción no encontrada'
        )
    usuario.desbloquear(sancion, ahora_argentina())
    session.commit()
    return sancion_publica(sancion)

from datetime import date
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from fulvo.database import get_session
from fulvo.models import EDAD_MINIMA, ROL_USUARIO, Rol, Usuario
from fulvo.schemas import UsuarioEntrada, UsuarioPublico
from fulvo.security import hashear_contrasena

router = APIRouter(prefix='/usuarios', tags=['usuarios'])
Session = Annotated[Session, Depends(get_session)]


@router.post('', status_code=HTTPStatus.CREATED, response_model=UsuarioPublico)
def registrar_usuario(datos: UsuarioEntrada, session: Session):
    """Registra un usuario nuevo con el rol `usuario` (RQ1).

    422 si es menor de 16 años y 409 si el email ya está registrado.
    """
    # El email se guarda en minúsculas para que "Ana@x.com" y "ana@x.com"
    # sean la misma cuenta (y el login no dependa de cómo lo escriba).
    email = datos.email.lower()

    # Si faltan los roles base (no se corrió la carga inicial), esto falla
    # con un 500 a propósito: es un error de despliegue, no del cliente.
    rol_id = session.scalars(
        select(Rol.id).where(Rol.nombre == ROL_USUARIO)
    ).one()

    # Se arma el Usuario antes de guardarlo para reutilizar `edad()`: la
    # regla de la edad vive en un solo lugar (el modelo).
    usuario = Usuario(
        email=email,
        contrasena_hash=hashear_contrasena(datos.contrasena),
        nombre=datos.nombre,
        apellido=datos.apellido,
        whatsapp=datos.whatsapp,
        fecha_nacimiento=datos.fecha_nacimiento,
        posicion=datos.posicion,
        rol_id=rol_id,
    )
    if usuario.edad(date.today()) < EDAD_MINIMA:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail=f'Hay que tener al menos {EDAD_MINIMA} años para '
            'registrarse',
        )

    if session.scalar(select(Usuario).where(Usuario.email == email)):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Ya existe un usuario con ese email',
        )

    session.add(usuario)
    session.commit()
    session.refresh(usuario)
    return usuario

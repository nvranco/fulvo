from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from fulvo.database import get_session
from fulvo.models import Usuario
from fulvo.schemas import Token
from fulvo.security import crear_token_acceso, verificar_contrasena

router = APIRouter(prefix='/auth', tags=['auth'])
Session = Annotated[Session, Depends(get_session)]
FormularioLogin = Annotated[OAuth2PasswordRequestForm, Depends()]


@router.post('/token', response_model=Token)
def iniciar_sesion(formulario: FormularioLogin, session: Session):
    """Inicia sesión y devuelve un token JWT (RQ1).

    Usa el formulario estándar de OAuth2 para que el botón "Authorize" de
    /docs funcione. Ese formulario llama `username` al campo, pero acá
    lleva el email.

    Un solo mensaje y un solo código para todo fallo (email inexistente,
    contraseña incorrecta o usuario bloqueado): así no se revela qué
    emails están registrados ni quién está bloqueado.
    """
    usuario = session.scalar(
        select(Usuario).where(Usuario.email == formulario.username.lower())
    )
    if (
        usuario is None
        or usuario.bloqueado
        or not verificar_contrasena(
            formulario.password, usuario.contrasena_hash
        )
    ):
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail='Email o contraseña incorrectos',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    token = crear_token_acceso({'sub': usuario.email})
    return {'access_token': token, 'token_type': 'bearer'}

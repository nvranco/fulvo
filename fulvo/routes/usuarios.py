from datetime import date
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from fulvo.database import get_session
from fulvo.models import EDAD_MINIMA, ROL_USUARIO, Rol, Usuario
from fulvo.schemas import (
    UsuarioEdicion,
    UsuarioEntrada,
    UsuarioPerfil,
    UsuarioPublico,
    UsuarioRegistrado,
)
from fulvo.security import (
    UsuarioActual,
    hashear_contrasena,
    obtener_usuario_actual,
)

router = APIRouter(prefix='/usuarios', tags=['usuarios'])
Session = Annotated[Session, Depends(get_session)]


def rechazar_menor_de_edad(usuario: Usuario, session: Session) -> None:
    """Levanta 422 si el usuario no llega a la edad mínima (RQ1).

    Lo usan el registro y la edición del perfil: si no, cambiar la fecha de
    nacimiento alcanzaría para esquivar el límite. El rollback descarta lo
    que ya se haya cambiado en el objeto, para que no se guarde nada.
    """
    if usuario.edad(date.today()) < EDAD_MINIMA:
        session.rollback()
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail=f'Hay que tener al menos {EDAD_MINIMA} años para usar '
            'la app',
        )


@router.post(
    '', status_code=HTTPStatus.CREATED, response_model=UsuarioRegistrado
)
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
    rechazar_menor_de_edad(usuario, session)

    if session.scalar(select(Usuario).where(Usuario.email == email)):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Ya existe un usuario con ese email',
        )

    session.add(usuario)
    session.commit()
    session.refresh(usuario)
    return usuario


# `/yo` tiene que declararse antes que `/{usuario_id}`: FastAPI prueba las
# rutas en orden, y si no, "yo" se tomaría como un id y daría 422.
@router.get('/yo', response_model=UsuarioPerfil)
def leer_mi_perfil(usuario: UsuarioActual):
    """Devuelve el perfil propio, con los datos privados (RQ2).

    La ruta no recibe un id a propósito: el usuario sale del token, así que
    no hay forma de pedir los datos privados de otro.
    """
    return usuario


@router.patch('/yo', response_model=UsuarioPerfil)
def editar_mi_perfil(
    datos: UsuarioEdicion, usuario: UsuarioActual, session: Session
):
    """Cambia solo los campos enviados del perfil propio (RQ2).

    422 si la fecha de nacimiento nueva no llega a la edad mínima. Es
    PATCH y no PUT porque se edita un dato a la vez, sin reenviar el resto.
    """
    # `exclude_unset` deja solo lo que mandó el cliente. Sin él, los campos
    # que no vinieron se guardarían con su valor por defecto (`None`).
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(usuario, campo, valor)
    rechazar_menor_de_edad(usuario, session)
    session.commit()
    session.refresh(usuario)
    return usuario


# El token se exige aunque el perfil sea público: solo lo necesitan usuarios
# de la app, y así nadie de afuera recorre los ids para juntar nombres.
@router.get(
    '/{usuario_id}',
    response_model=UsuarioPublico,
    dependencies=[Depends(obtener_usuario_actual)],
)
def leer_perfil_publico(usuario_id: int, session: Session):
    """Devuelve el perfil público de un usuario, o 404 si no existe (RQ2)."""
    usuario = session.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Usuario no encontrado'
        )
    return usuario

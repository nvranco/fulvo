from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from fulvo.database import get_session
from fulvo.models import ROL_ADMIN, Usuario
from fulvo.settings import Settings

# Se lee una vez al importar el módulo, igual que el engine en database.py.
configuracion = Settings()
Session = Annotated[Session, Depends(get_session)]

# Le dice a FastAPI de dónde sale el token (encabezado `Authorization:
# Bearer ...`) y a Swagger a qué ruta ir a pedirlo: el botón "Authorize"
# de /docs usa `tokenUrl`.
esquema_oauth2 = OAuth2PasswordBearer(tokenUrl='auth/token')

# `recommended()` arma el hasher con argon2, el algoritmo que pide la
# cátedra. Argon2 es lento a propósito y usa mucha memoria: encarece los
# ataques de fuerza bruta si se filtra la base. Cada hash lleva su propia
# sal, así que dos usuarios con la misma contraseña tienen hashes distintos.
_hasher = PasswordHash.recommended()


def hashear_contrasena(contrasena: str) -> str:
    """Devuelve el hash argon2 de la contraseña, listo para guardar.

    Es lo único que se guarda (`Usuario.contrasena_hash`): la contraseña
    en claro nunca se guarda ni se loguea.
    """
    return _hasher.hash(contrasena)


def verificar_contrasena(contrasena: str, contrasena_hash: str) -> bool:
    """Dice si la contraseña corresponde al hash guardado.

    Devuelve un booleano y no levanta excepción: que la contraseña sea
    incorrecta es un resultado esperado, no un error. La ruta de login
    responderá siempre el mismo mensaje genérico (CLAUDE.md, sección 11).
    """
    return _hasher.verify(contrasena, contrasena_hash)


def crear_token_acceso(datos: dict, expira_en: timedelta | None = None) -> str:
    """Firma un JWT con `datos` y le agrega la fecha de vencimiento (`exp`).

    Por convención `datos` lleva `sub` con el identificador del usuario
    (el email). No se meten datos sensibles: el token se puede leer, solo
    está firmado, no cifrado. `expira_en` permite probar tokens vencidos
    sin esperar; por defecto se usa ACCESS_TOKEN_EXPIRE_MINUTES.

    Se copia `datos` para no modificar el diccionario del que llama. El
    vencimiento se calcula en UTC porque `exp` es un instante absoluto.
    """
    if expira_en is None:
        expira_en = timedelta(
            minutes=configuracion.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    a_firmar = datos.copy()
    a_firmar['exp'] = datetime.now(UTC) + expira_en
    return jwt.encode(
        a_firmar,
        configuracion.SECRET_KEY,
        algorithm=configuracion.ALGORITHM,
    )


def decodificar_token_acceso(token: str) -> dict:
    """Verifica la firma y el vencimiento del token y devuelve sus datos.

    Si el token está vencido, alterado o mal formado, pyjwt levanta una
    subclase de `jwt.InvalidTokenError`. No se captura acá: la dependencia
    de "usuario actual" la traducirá a un 401 en un solo lugar (CLAUDE.md,
    sección 7). Se pasa `algorithms` como lista fija para que un atacante
    no pueda elegir otro algoritmo desde el encabezado del token.
    """
    return jwt.decode(
        token,
        configuracion.SECRET_KEY,
        algorithms=[configuracion.ALGORITHM],
    )


def obtener_usuario_actual(
    session: Session,
    token: Annotated[str, Depends(esquema_oauth2)],
) -> Usuario:
    """Devuelve el usuario dueño del token, o corta con un error HTTP.

    Es el único lugar que traduce los errores del token a 401 (CLAUDE.md,
    sección 7). Todo fallo de autenticación da el mismo error, sin decir
    si el token estaba vencido, alterado o era de un usuario inexistente.

    Se vuelve a leer al usuario de la base en cada request, en vez de
    confiar en el token, para que un bloqueo valga al instante y no recién
    cuando el token venza.
    """
    no_autenticado = HTTPException(
        status_code=HTTPStatus.UNAUTHORIZED,
        detail='No se pudo validar las credenciales',
        headers={'WWW-Authenticate': 'Bearer'},
    )
    try:
        datos = decodificar_token_acceso(token)
    except jwt.InvalidTokenError:
        raise no_autenticado from None

    email = datos.get('sub')
    if not email:
        raise no_autenticado
    usuario = session.scalar(select(Usuario).where(Usuario.email == email))
    if usuario is None:
        raise no_autenticado
    if usuario.bloqueado:
        # 403 y no 401: la identidad es válida pero no tiene permiso.
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail='Usuario bloqueado'
        )
    return usuario


# Alias para las rutas protegidas: `usuario: UsuarioActual`.
UsuarioActual = Annotated[Usuario, Depends(obtener_usuario_actual)]


def exigir_admin(usuario: UsuarioActual) -> Usuario:
    """Deja pasar solo a un usuario con rol admin; si no, 403.

    Se apoya en `UsuarioActual`, así que sin token o con token inválido
    da 401 antes de llegar acá. La regla de quién es admin vive en
    `Usuario.tiene_rol`: este es el único lugar que la convierte en un 403.

    Las rutas la usan con `dependencies=[Depends(exigir_admin)]` en el
    decorador: no necesitan el usuario, solo el permiso.
    """
    if not usuario.tiene_rol(ROL_ADMIN):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Esta acción es solo para administradores',
        )
    return usuario

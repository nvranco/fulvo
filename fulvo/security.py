from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from fulvo.settings import Settings

# Se lee una vez al importar el módulo, igual que el engine en database.py.
configuracion = Settings()

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

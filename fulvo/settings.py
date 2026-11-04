from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la app, leída de variables de entorno o de `.env`.

    Orden de prioridad: variable de entorno, luego `.env`, luego el valor
    por defecto. Así cada entorno (local, contenedor, CI, Fly.io) define sus
    valores desde afuera y el código no cambia.
    """

    model_config = SettingsConfigDict(
        env_file='.env', env_file_encoding='utf-8'
    )

    # Con valor por defecto para que la app y los tests anden sin `.env`.
    # Ojo en producción: si falta DATABASE_URL no hay error, se crea un
    # SQLite dentro del contenedor y los datos se pierden al redesplegar.
    # Por eso compose.yaml y los secrets de Fly la definen siempre.
    DATABASE_URL: str = 'sqlite:///fulvo.db'

    # Clave con la que se firman los tokens JWT. Va sin valor por defecto a
    # propósito: una clave pública en el repo permitiría a cualquiera
    # falsificar tokens. Si falta, la app no arranca (error claro) en vez de
    # firmar con una clave débil. Los tests definen una falsa en
    # tests/__init__.py.
    SECRET_KEY: str

    # HS256: firma simétrica con una sola clave. Alcanza porque el mismo
    # servidor firma y verifica; no se necesita un par de claves (RS256).
    ALGORITHM: str = 'HS256'

    # Duración del token. Corta para limitar el daño si se filtra, ya que
    # el MVP no tiene tokens de renovación.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

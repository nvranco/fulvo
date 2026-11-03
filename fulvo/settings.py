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

    # Las claves de JWT (SECRET_KEY, etc.) se agregan con el login (RQ1) y
    # van sin valor por defecto: una clave de firma pública en el repo
    # permitiría falsificar tokens.

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Configuración de este servidor, leída de variables de entorno.

    Cada instancia (server-a, server-b, server-c) usa el mismo código con
    valores distintos de DOMAIN y DATABASE_URL.
    """

    domain: str = "localhost"
    database_url: str = "postgresql+asyncpg://social:social@localhost:5432/social"

settings = Settings()
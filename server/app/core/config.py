from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Configuración de este servidor, leída de variables de entorno.

    Cada instancia (server-a, server-b, server-c) usa el mismo código con
    valores distintos de DOMAIN y DATABASE_URL.
    """

    domain: str = "localhost"
    database_url: str = "postgresql+asyncpg://social:social@localhost:5432/social"
    secret_key: str = "dev-secret-cambiar-en-produccion"
    token_ttl_seconds: int = 7 * 24 * 3600

    @property
    def base_url(self) -> str:
        """URL con la que otros servidores alcanzan a éste dentro de la red de Docker."""
        return f"http://{self.domain}:8000"

settings = Settings()
import logging
from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.domain.entities import Actor
from app.domain.ports import Repos
from app.services import follows

log = logging.getLogger(__name__)

class UsernameTaken(Exception):
    pass

def local_actor_id(username: str) -> str:
    return f"{settings.base_url}/users/{username}"

async def get_local(repos: Repos, username: str) -> Actor | None:
    return await repos.actors.get(local_actor_id(username))

async def register(repos: Repos, username: str, password: str, display_name: str) -> Actor:
    if await get_local(repos, username):
        raise UsernameTaken(username)
    actor = Actor(
        id=local_actor_id(username),
        username=username,
        domain=settings.domain,
        is_local=True,
        display_name=display_name or username,
        password_hash=hash_password(password)
    )
    repos.actors.add(actor)
    await repos.commit()
    log.info("user_registered", extra={"actor_id": actor.id})
    return actor

async def update_profile(
        repos: Repos, actor: Actor, display_name: str |None = None, locked: bool | None = None
) -> Actor:
    """None = no cambiar. Pasar de privada a pública acepta las solicitudes pendientes."""
    if display_name is not None:
        actor.display_name = display_name
    if locked is not None:
        if actor.locked and not locked:
            await follows.acept_all_pending(repos, actor)
        actor.locked = locked
    await repos.commit()
    log.info("profile_updated", extra={"actor_id": actor.id, "locked": actor.locked})
    return actor

async def authenticate(repos: Repos, username: str, password: str) -> Actor | None:
    actor = await get_local(repos, username)
    if actor and verify_password(password, actor.password_hash):
        return actor
    return None
import logging
from app.core.security import hash_password, verify_password
from app.domain.entities import Actor, base_url
from app.domain.ports import Repos
from app.services import follows, activities

log = logging.getLogger(__name__)

class UsernameTaken(Exception):
    pass

def actor_id(domain: str, username: str) -> str:
    return f"{base_url(domain)}/users/{username}"

async def get_local(repos: Repos, username: str) -> Actor | None:
    return await repos.actors.get(actor_id(repos.domain, username))

def parse_handle(handle: str) -> tuple[str, str | None]:
    """`ana`, `ana@server-a` o `@ana@server-a` → (nombre, dominio o None)."""
    username, _, domain = handle.removeprefix("@").partition("@")
    return username, domain or None

async def find(repos: Repos, handle: str, fetch: bool = True) -> Actor | None:
    """El usuario de ese handle, local o remoto. Un remoto que aún no conocemos se pide a su servidor
    (si `fetch`) y queda guardado. Lanza ServerUnavailable si ese servidor no responde."""
    username, domain = parse_handle(handle)
    if domain is None or domain == repos.domain:
        return await get_local(repos, username)
    actor = await repos.actors.get(actor_id(domain, username))
    if actor is None and fetch:
        data = await repos.federation.fetch_actor(domain, username)
        if data is not None:
            actor = await activities.remote_actor(repos, data)
            await repos.commit()
    return actor

async def register(repos: Repos, username: str, password: str, display_name: str) -> Actor:
    if await get_local(repos, username):
        raise UsernameTaken(username)
    actor = Actor(
        id=actor_id(repos.domain, username),
        username=username,
        domain=repos.domain,
        is_local=True,
        display_name=display_name or username,
        password_hash=hash_password(password)
    )
    await repos.actors.add(actor)
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
from app.domain.entities import Actor
from app.domain.ports import Repos
from app.services import timeline

class CannotFollowSelf(Exception):
    pass

async def follow(repos: Repos, follower: Actor, followed: Actor) -> None:
    """Idempotente: seguir dos veces a la misma cuenta no hace nada la segunda."""
    if follower.id == followed.id:
        raise CannotFollowSelf()
    if not await repos.follows.exists(follower.id, followed.id):
        repos.follows.add(follower.id, followed.id)
        await timeline.backfill(repos, follower, followed)
        await repos.commit()

async def unfollow(repos: Repos, follower: Actor, followed: Actor) -> None:
    await repos.follows.remove(follower.id, followed.id)
    await timeline.remove_author(repos, follower, followed)
    await repos.commit()

async def followers(repos: Repos, actor: Actor) -> list[Actor]:
    return await repos.follows.followers(actor.id)

async def following(repos: Repos, actor: Actor) -> list[Actor]:
    return await repos.follows.following(actor.id)
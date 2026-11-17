"""Adaptador en memoria: implementa los puertos de persistencia con diccionarios y conjuntos.

Lo usan los tests unitarios de los services y el prototipo Ray (cada actor guarda aquí su estado).
No depende de SQLAlchemy. `commit()` sólo cuenta las confirmaciones: no hay transacciones.
"""

from app.domain.entities import Actor, Note

class MemoryActorRepo:
    def __init__(self):
        self.by_id: dict[str, Actor] = {}

    async def get(self, actor_id):
        return self.by_id.get(actor_id)

    def add(self, actor):
        self.by_id[actor.id] = actor

class MemoryNoteRepo:
    def __init__(self):
        self.by_id: dict[str, Note] = {}

    async def add(self, note):
        self.by_id[note.id] = note

    async def recent_by_author(self, author_id, limit):
        notes = [n for n in self.by_id.values() if n.author_id == author_id]
        return sorted(notes, key=lambda n: n.published, reverse=True)[:limit]

class MemoryFollowRepo:
    def __init__(self, actors: MemoryActorRepo):
        self.actors = actors
        self.pairs: set[tuple[str,str]] = set()

    async def exists(self, follower_id, followed_id):
        return (follower_id, followed_id) in self.pairs

    def add(self, follower_id, followed_id):
        self.pairs.add((follower_id,followed_id))

    async def remove(self, follower_id, followed_id):
        self.pairs.discard((follower_id, followed_id))

    async def followers(self, actor_id):
        return [self.actors.by_id[f] for f, t in self.pairs if t == actor_id]

    async def following(self, actor_id):
        return [self.actors.by_id[t] for f, t in self.pairs if f == actor_id]

    async def local_follower_ids(self, actor_id):
        return [f for f, t in self.pairs if t == actor_id and self.actors.by_id[f].is_local]

class MemoryTimelineRepo:
    def __init__(self, notes: MemoryNoteRepo):
        self.notes = notes
        self.entries: set[tuple[str, str]] = set()

    async def add(self, entries):
        self.entries |= {(e["owner_id"], e["note_id"]) for e in entries}

    async def remove_author(self, owner_id, author_id):
        self.entries = {
            (o, n) for o, n in self.entries
            if not (o == owner_id and self.notes.by_id[n].author_id == author_id)
        }

    async def home(self, owner_id, limit):
        notes = [self.notes.by_id[n] for o, n in self.entries if o == owner_id]
        return sorted(notes, key=lambda n: n.published, reverse=True)[:limit]

class MemoryRepos:
    def __init__(self):
        self.actors = MemoryActorRepo()
        self.notes = MemoryNoteRepo()
        self.follows = MemoryFollowRepo(self.actors)
        self.timeline = MemoryTimelineRepo(self.notes)
        self.commits = 0

    async def commit(self):
        self.commits += 1
        print("Commit aumentado")
"""Adaptador en memoria: implementa los puertos de persistencia con diccionarios y conjuntos.

Lo usan los tests unitarios de los services y el prototipo Ray (cada actor guarda aquí su estado).
No depende de SQLAlchemy. `commit()` sólo cuenta las confirmaciones: no hay transacciones.
"""

from app.domain.entities import Actor, Note, Repost, Tombstone

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
        self.tombstones: dict[str, Tombstone] = {}
        self.dependents = () # repositorios que referencian notas: hacen de "ON DELETE CASCADE"

    async def add(self, note):
        self.by_id[note.id] = note

    async def get(self, note_id):
        return self.by_id.get(note_id)
    
    async def delete(self, note):
        del self.by_id[note.id]
        self.tombstones[note.id] = Tombstone(id=note.id, author_id=note.author_id)
        for repo in self.dependents:
            repo.drop_note(note.id)

    async def get_tombstone(self, note_id):
        return self.tombstones.get(note_id)

    async def recent_by_author(self, author_id, limit, visibilities=None):
        notes = [
            n for n in self.by_id.values() 
            if n.author_id == author_id and (visibilities is None or n.visibility in visibilities)
        ]
        return _newest(notes, limit)

    async def latest(self, limit, visibilities, local_only):
        notes = [
            n for n in self.by_id.values()
            if n.visibility in visibilities and (n.author.is_local or not local_only)
        ]
        return _newest(notes, limit)

class MemoryFollowRepo:
    def __init__(self, actors: MemoryActorRepo):
        self.actors = actors
        self.pairs: set[tuple[str,str]] = set()

    async def exists(self, follower_id, followed_id):
        return (follower_id, followed_id) in self.pairs

    async def is_follower(self, follower_id, followed_id):
        return (follower_id, followed_id) in self.pairs # en memoria aún no hay estado pendiente

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

class MemoryRepostRepo:
    def __init__(self):
        self.by_key: dict[tuple[str, str], Repost] = {}

    async def exists(self, actor_id, note_id):
        return (actor_id, note_id) in self.by_key

    def add(self, repost):
        self.by_key[(repost.actor_id, repost.note_id)] = repost

    async def remove(self, actor_id, note_id):
        self.by_key.pop((actor_id, note_id), None)

    async def of_note(self, note_id):
        return [r for (_, n), r in self.by_key.items() if n == note_id]

    def drop_note(self, note_id):
        self.by_key = {k: r for k, r in self.by_key.items() if k[1] != note_id}

class MemoryTimelineRepo:
    def __init__(self, notes: MemoryNoteRepo, actors: MemoryActorRepo):
        self.notes = notes
        self.actors = actors
        self.entries: dict[tuple[str, str], tuple] = {} # (owner_id, note_id) -> (sort_date, reposted_by)

    async def add(self, entries):
        for e in entries:
            key = (e["owner_id"], e["note_id"])
            if key not in self.entries or self.entries[key][0] < e["sort_date"]:
                self.entries[key] = (e["sort_date"], e["reposted_by"])

    async def remove_author(self, owner_id, author_id):
        self.entries = {
            (o, n): (d, by)  for (o, n), (d, by) in self.entries.items()
            if not (o == owner_id and (by == author_id or (by is None and self.notes.by_id[n].author_id == author_id)))
        }

    async def remove_repost(self, actor_id, note_id):
        self.entries = {k: v for k, v in self.entries.items() if not (k[1] == note_id and v[1] == actor_id)}

    async def home(self, owner_id, limit):
        mine = sorted(
            ((d, n, by) for (o, n), (d, by) in self.entries.items() if o == owner_id), reverse=True 
        )[:limit]
        return [(self.notes.by_id[n], self.actors.by_id.get(by)) for _, n, by in mine]

    def drop_note(self, note_id):
        self.entries = {k: v for k, v in self.entries.items() if k[1] != note_id}

def _newest(notes, limit):
    return sorted(notes, key=lambda n: n.published, reverse=True)[:limit]
class MemoryRepos:
    def __init__(self):
        self.actors = MemoryActorRepo()
        self.notes = MemoryNoteRepo()
        self.reposts = MemoryRepostRepo()
        self.follows = MemoryFollowRepo(self.actors)
        self.timeline = MemoryTimelineRepo(self.notes, self.actors)
        self.notes.dependents = (self.reposts, self.timeline)
        self.commits = 0

    async def commit(self):
        self.commits += 1
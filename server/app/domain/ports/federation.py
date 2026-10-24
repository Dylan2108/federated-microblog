from typing import Protocol

class Federation(Protocol):
    """Comunicación con otros servidores, vista desde la lógica de negocio.

    `deliver` encarga entregar una actividad (un dict JSON con un `id` global) al servidor `domain`.
    No espera a que llegue: la entrega es asíncrona y eventual.
    """

    async def deliver(self, domain: str, activity: dict) -> None: ...
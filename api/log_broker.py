"""Broker de logs en memoria para retransmitir vía WebSocket."""
import asyncio
from collections import deque
from typing import Set


class LogBroker:
    """Mantiene un buffer circular de logs y suscriptores WebSocket."""

    def __init__(self, max_buffer: int = 500):
        self._buffer: deque = deque(maxlen=max_buffer)
        self._subscribers: Set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

    async def publish(self, line: str) -> None:
        """Agregar línea al buffer y enviarla a todos los suscriptores."""
        self._buffer.append(line)
        async with self._lock:
            for q in list(self._subscribers):
                try:
                    q.put_nowait(line)
                except asyncio.QueueFull:
                    pass

    async def subscribe(self) -> asyncio.Queue:
        """Suscriptor recibe primero el buffer histórico, luego stream live."""
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        # Enviar buffer inicial
        for line in list(self._buffer):
            try:
                q.put_nowait(line)
            except asyncio.QueueFull:
                break
        async with self._lock:
            self._subscribers.add(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        async with self._lock:
            self._subscribers.discard(q)


broker = LogBroker()

import asyncio
from typing import Dict, List, AsyncGenerator

class RunBus:
    def __init__(self):
        self._queues: Dict[str, "asyncio.Queue[str]"] = {}
    def queue(self, run_id: str) -> "asyncio.Queue[str]":
        if run_id not in self._queues:
            self._queues[run_id] = asyncio.Queue()
        return self._queues[run_id]
    async def emit(self, run_id: str, payload: dict):
        await self.queue(run_id).put(f"data: {payload}\n\n")
    async def stream(self, run_id: str) -> AsyncGenerator[bytes, None]:
        q = self.queue(run_id)
        try:
            while True:
                item = await q.get()
                yield item.encode("utf-8")
        except asyncio.CancelledError:
            return

# Gate control for approval workflow
RUN_GATES = {}       # run_id -> asyncio.Event
RUN_NOVNC = {}       # run_id -> noVNC URL

def gate_for(run_id: str) -> asyncio.Event:
    if run_id not in RUN_GATES:
        RUN_GATES[run_id] = asyncio.Event()
    return RUN_GATES[run_id]

RUN_BUS = RunBus()

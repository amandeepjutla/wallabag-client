# Kera (GPT-6 Astra). Created 2026-11-13.
"""Serialize this reader's blocking requests beyond coroutine cancellation."""
import asyncio
from functools import partial
from typing import Callable, TypeVar

_Result = TypeVar("_Result")


class ReaderRequests:
    """Keep OAuth refresh/config writes inside one request at a time.

    Cancelling an asyncio waiter does not stop its requests-library thread.
    Waiting requests stay in the event loop until they are admitted. Once a
    request starts, its shielded executor future keeps the lock until the actual
    operation ends. Cancelling a waiting request prevents its dispatch entirely.
    This is process-local; separate CLI processes retain their existing behavior.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    async def run(self, operation: Callable[..., _Result], *args, **kwargs) -> _Result:
        await self._lock.acquire()
        try:
            pending = asyncio.get_running_loop().run_in_executor(None, partial(operation, *args, **kwargs))
        except BaseException:
            self._lock.release()
            raise

        def finished(result):
            self._lock.release()
            # A cancelled caller no longer retrieves a failed HTTP operation's
            # exception. Consume it here while preserving normal await behavior.
            if not result.cancelled():
                result.exception()

        pending.add_done_callback(finished)
        return await asyncio.shield(pending)

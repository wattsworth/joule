
from typing import Callable
import asyncio


class Subscription:

    def __init__(self, queue: asyncio.Queue, unsubscribe: Callable[[], None]):
        self.queue = queue
        self.unsubscribe = unsubscribe


"""
Not an actual test. Just a script to test how the async_map function works.
"""
import asyncio
from constelite.utils import async_map

async def coro(val: int):
    if val > 2:
        raise Exception("An error occurred")


async def test_async_map():
    await async_map(coro, [1, 2, 3, 4, 5])

if __name__ == "__main__":
    asyncio.run(test_async_map())
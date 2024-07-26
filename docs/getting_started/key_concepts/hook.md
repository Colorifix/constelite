# Hook

## Intro

Hook is an abstraction of a webhook. It is a callback function that runs on a server and can trigger client when a certain event occurs. This is opposite of a protocol, which is called by the client.

## Implementation

Hooks can only be implemented as classes (opposed to protocols that can be either functions or classes).

```python
import asyncio
from constelite.hook import Hook

class TimerHook(Hook):
    interval_sec: int

    async def run(self) -> str:
        while True:
            await asyncio.sleep(self.interval_sec)
            yield "ping"
```

Above is a simple hook that emits "ping" at a regular intervals.

!!! note
    We are using `yield` instead of `return` to allow one hook to emit multiple signals. You must use `yield` even if you only return once.

### Hook config

Note that the `TimerHook` above does not control what happens with the values that it yields. This is instead controlled by the API. Each API can define a derivative of a `HookConfig` class, specifying information required for the hook logic.

For example,

```python
from constelite.api import ConsteliteAPI
from constelite.hook import
import aiohttp

class HTTPHookConfig:
    endpoint: str


class HTTPAPI(ConsteliteAPI):
    async def trigger_hook(self, ret: Any, hook_config: dict) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.post(hook_config.endpoint, data=ret) as response:
                pass


api = HTTPAPI(...)

task = api.start_hook(slug='timer_hook', hook_config=HTTPHookConfig(endpoint="server.colorifix.com/ping"))
```
All logic for handling the hook call is defined in `trigger_hook` method. In this example, we are sending HTTP POST requests each time the hook yields a value.


!!! warning
    Hooks are currently only implemented for CamundaAPI
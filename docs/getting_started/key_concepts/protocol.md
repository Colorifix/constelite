[](){#protocol}
# Protocol

## Intro

Protocol is just a fancy word for a serverless function. It's just a Python function that has access to constelite API and hence has access to all other protocols and stores.

## Anatomy of a protocol

Protocols can be defined either as functions or classes.

## Function protocols

When your protocol is simple you can define it using a `@protocol` wrapper.

```py
from constelite.protocol import protocol
from constelite.api import ConsteliteAPI
from constelite.models import Ref

from constelite_demo import Cat

@protocol
async def herd_a_cat(api: ConsteliteAPI, r_cat: Ref[Cat]) -> bool:
    await api.get_state(r_cat)
    ...

    return False
```

Function protocol must always have `api` as it's first argument, which will be an instance of [ConsteliteAPI][constelite.api.ConsteliteAPI]. All other arguments must have type hints and will be validated before the protocol is called. Return type must also be set. If your function does not return anything set the return type hint to `None`.

## Class protocols

When the logic of a protocol is complex, you might want to wrap it into a class.

```py
from constelite.protocol import Protocol
from constelite.models import Ref

from constelite_demo import Cat

class HerdACat(Protocol):
    r_cat: Ref[Cat]

    def run(self, api: ConsteliteAPI) -> bool
        ...

        return False
```

All protocol arguments are defined as class fields. The logic itself goes into `run()` method that must take `api` as an argument. 


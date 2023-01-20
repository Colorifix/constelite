# Welcome to Constelite

## Definitions

### StateModel

Model is just a class that is derived from `constelite.Model`, which is your ordinary `pydantic.BaseModel`.

### Store

### StoreRecord

### Ref

### Protocol

A function wrapped in `@protocol` that convers one or more models into another model.

Can alos be implemented as a `Protocol` class with a `run()` method.


## How to

### Define a new state model

Constelite uses `pydantic`. All models in constelite should be defined from `constelite.StateModel` base class.


```python
from constelite.models import StateModel


class Message(StateModel):
    message: str
    likes: Optional[Dynamic[int]]
```

### Add a protocol

Protocols can be defined as function wrapped in a `@protocol` or a class derived from `Protocol`.

**Functional protocols**

* Must use type hints.
* Must use references (not state models) as input arguments and state models as returns.
* Must have an `api` argument that will be linked to the instance of the API.

```python
from typing import List, Any

from constelite.models import Ref
from constelite.protocol import protocol

from model import Message


@protocol(name='Combine messages')
def combine_messages(messages: List[Ref[Message]], api: Any) -> Message:
    return Message(
        message=''.join([api.get_state(message).message for message in messages]),
    )
```

**Class protocols**

* Must have a `run()` method defined.
* The `run()` method must use type hints.
* The `run()` must use references (not state models) as input arguments and state models as returns.
* The `api` instance can be accessed through `self.api`

```python

from typing import List
from constelite.models import Ref
from constelite.protocol import Protocol

from model import Message


class SumTotalLikes(Protocol):
    _name = "Sum total likes"

    messages: List[Ref[Message]]

    def run(self) -> int:
        total = 0
        for r_message in self.messages:
            message = self.api.get_state(r_message)
            points = message.likes.points
            if len(points) > 0:
                total += points[-1].value
        return total
``` 

### Start an API server

* Create an instance of the API.
* Discover protocols using `api.discover_protocols()`
* Launch using `api.run()` method
* See `example/api`


### Call remote functions

Easy, just create an instance of `StarliteClient` and use it to do the reemote calls. Make sure you have a server running first.

```python
from constelite.api import StarliteClient


if __name__ == '__main__':
    client = StarliteClient(url='http://127.0.0.1:8083')
```
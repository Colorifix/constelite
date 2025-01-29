# Getting started

## Install constelite from PyPI

```console
$ pip install constelite
```
or

```console
$ poetry add constelite
```

## Setup the folder structure

This is more of an advice to get started rather than a hard rule.

```
.
├── README.md
├── constelite_demo
│   ├── __init__.py
│   ├── api.py
│   ├── models
│   └── protocols
├── poetry.lock
└── pyproject.toml
```

`protocols` is a folder where we are going to store all protocols.

`models` is a folder for storing models.

`api.py` is a main file that will start contelite API

## Write a simple protocol

Let's create a new protocol in `/protocols/hello_world.py`.

```python
from constelite.protocol import protocol
from constelite.api import ConsteliteAPI
from constelite.loggers import Logger

@protocol(name="HelloWorldProtocol")
async def hello_world(api: ConsteliteAPI, logger: Logger, name: str) -> None:
    await logger.log(f"Hello, {name}!")
```

[Protocols](key_concepts/protocol.md) in constelite can be either functional (as the one above) or class-based.

Protocols are just fancy Python functions. As a rule, they must take `api` and `logger` arguments.

`api` is a reference to the constelite API that is serving the protocol. `logger` is a reference to the logger, which defaults to a wrapper of loguru logger but can be customised and selected by the user who calls the protocol.

In addition, protocols can take any other arguments, which must be type-hinted.

## Start an API

Let's create a simple api in `api.py`

```python
from constelite.api.starlite import StarliteAPI

import constelite_demo.protocols
import constelite_demo.models

from constelite.models.model import discover_models

api = StarliteAPI(name="Alpha") # create an instance of API

api.discover_protocols(constelite_demo.protocols) # Load protocols from the '/protocols' folder
discover_models(constelite_demo.models) # Load models from the '/models' folder

api.generate_app() # generate Litestar app

api.run('localhost', 8001) # Start API
```

Now we have a litestar server running that serves our protocol. You can navigate to [http://localhost:8001/schema]{:target="_blank"} to the OpenAPI documentation.

## Create a simple model

Let's create a first model in the `/models/cat.py` file.

```python
from constelite.models import StateModel

class Cat(StateModel):
    name: str | None = None
```

All modles in constelite must inherit from the [StateModel](key_concepts/state_model.md) class. Apart from that they behave just like `justpy.BaseModel`.


## What's next?

Check out [User Guide](user_guide) for more examples to get you started.

Check out [Key concepts](key_concepts/) to learn more about constelite way of thinking.

[http://localhost:8001/schema]: http://localhost:8001/schema
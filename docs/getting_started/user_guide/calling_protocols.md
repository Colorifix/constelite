Constelite hosts a collection of protocols that can be called using various APIs.

In this guide, we will use "HelloWorldProtocol" protocol from the [Getting started](../index.md) as an example.

```python
from constelite.protocol import protocol
from constelite.api import ConsteliteAPI
from constelite.loggers import Logger

@protocol(name="HelloWorldProtocol")
async def hello_world(api: ConsteliteAPI, logger: Logger, name: str) -> None:
    await logger.log(f"Hello, {name}!")
```

From the OpenAPI docs, we can see that the protocol expect the following request format:

```json
{
  "args": {
     "name": "Steve"
  },
  "logger": null
}
```

All protocols expect a request that contains two fields:

* **args**: for arguments to pass to the protocol function.
* **logger**: optional field to instruct constelite which logger to use.

## Calling protocols using an HTTP request

Let's send a request to `https://localhost:8000/protocols/hello_world`

```console
$ curl -X POST http://localhost:8001/protocols/hello_world -d '{"args": {"name": "Steve"}}'
```


## Calling protocols using Starlite client

Making raw requests to constelite is tedious. Constelite provide a Starlite client which makes it a bit simpler using Python. Let's create another file `client.py`.

```py
from constelite.api.starlite.client import StarliteClient

if __name__ == '__main__':
    client = StarliteClient(url="http://localhost:8001")

    client.protocols.hello_world(
        name="Steve"
    )
```

This code is equivalent to sending a `curl` request.
## Calling constelite protocols

Constelite hosts a collection of protocols that can be called using various APIs.

In this guide, we will use "HelloWorldProtocol" protocol from the [Getting started](../index.md) as an example.

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

### Calling protocols using an HTTP request

Let's send a request to `https://localhost:8000/protocols/hello_world`

```console
$ curl -X POST http://localhost:8001/protocols/h
ello_world -d '{"args": {"name": "Steve"}}'
```


### Calling protocols using Starlite client

Making raw requests to constelite is tedious. Constelite provide a Starlite client which makes it a bit simpler using Python. The code below is equivalent to sending the request above:

```py
from constelite.api.starlite.client import StarliteClient

if __name__ == '__main__':
    client = StarliteClient(url="http://localhost:8001")

    client.protocols.hello_world(
        name="Steve"
    )
```
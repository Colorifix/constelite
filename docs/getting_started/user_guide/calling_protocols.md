## Calling constelite protocols

Constelite hosts a collection of protocols that can be called using various APIs.

You can see all available protocols in the [Constelite API documentation](http://constelite.colorifix.com/schema/swagger).

In this guide, we will use "GeneratePhase3Workflow" protocol as an example.

From the documentation, we can see that the protocol expect the following request format:

```json
{
  "args": {
    "r_request": null,
    "store": {
      "uid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "name": null
    },
    "r_dye_at_scale": null,
    "r_fermentation_service": null
  },
  "logger": null
}
```

All protocols expect a request that contains two fields:

* **args**: for arguments to pass to the protocol function.
* **logger**: optional field to instruct constelite which logger to use.

This particular protocol requires a reference to a Phase III request (`r_request`) and a store where the changes should be written to (`store`).

It is common for protocols to specify the store because, by design, constelite is agnostic to the data source / sink.

You can find uids of all available stores at the constelite [home page](https://constelite.colorifix.com)


### Calling protocols using an HTTP request

Send a request to `https://constelite.colorifix.com/protocols/requests/generate_phase3_workflow`

With a body:

```json
{
  "args": {
    "r_request": {
        "model_name": "Ref",
        "state_model_name": "PhaseIIIWorkflowInstance",
        "record": {
            "uid": "2bab57ebb2c34dc9867de9b0401825f1",
            "store": {
                "uid": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
            }
        },
    },
    "store": {
      "uid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "name": null
    },
  }
}
```

And the following headers:

```
Content-Type: application/json
Authorization: Bearer {{constelite_token}}
```

### Calling protocols using Starlite client

Making raw requests to constelite is tedious. Constelite provide a Starlite client which makes it a bit simpler using Python. The code below is equivalent to sending the request above:

```py
import os

from constelite.api import StarliteClient
from constelite.models import StoreModel, ref
from colorifix_alpha.models import (
    PhaseIIIWorkflowInstance
)


if __name__ == '__main__':
    client = StarliteClient(url="http://constelite.colorifix.com")

    notion_store = StoreModel(
        uid="3fa85f64-5717-4562-b3fc-2c963f66afa6"
    )

    r_request = ref(
        PhaseIIIWorkflowInstance,
        uid="2bab57ebb2c34dc9867de9b0401825f1",
        store=notion_store
    )

    client.protocols.requests.generate_phase3_workflow(
        r_request=r_request,
        store=notion_store
    )
```

!!! note
    When using Python client you can supply your authentication token as a `token` argument when initialising the client or by setting `CONSTELITE_TOKEN` environmental variable.
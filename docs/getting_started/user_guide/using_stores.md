In the [Getting started](../index.md), we introduced a simple model in the `/models/cat.py` file. Let's see how we can use this model for storing information about cats in a store.

```python
from constelite.models import StateModel

class Cat(StateModel):
    name: str | None = None
```

## Creating a store

First, we need to create a new store and register it with out api.

In constelite, API can can have access to as many stores as we want, and they can be accessing either local or remote data providers.

In this example, we will use `MemoryStore` a simple in-memory store.


```python
from constelite.store import MemoryStore


memory_store = MemoryStore(
    uid="5ef14649-fd40-40a0-a693-de36c855a181",
    name="Memory store"
)
```

As minimum, a store must have a unique uid. Optionally it can have a name and any extra arguments that are required for the particular store implementation.

To register the store with API, just pass it to the API constructor:

```python
api = StarliteAPI(name="Alpha", stores=[memory_store])
```

The complete `api.py` now looks like:

```python
from constelite.api.starlite import StarliteAPI

import constelite_demo.protocols
import constelite_demo.models

from constelite.models.model import discover_models

from constelite.store import MemoryStore

memory_store = MemoryStore(
    uid="5ef14649-fd40-40a0-a693-de36c855a181",
    name="Memory store"
)

api = StarliteAPI(name="Alpha", stores=[memory_store]) # create an instance of API

api.discover_protocols(constelite_demo.protocols) # Load protocols from the '/protocols' folder
discover_models(constelite_demo.models) # Load models from the '/models' folder

api.generate_app() # generate Litestar app

api.run('localhost', 8001) # Start API
```

## Read and write from the store

Let's now explore how we can read and write models to the store. If you haven't already, create a `client.py` file. Inside we will create a Starlite client and a reference to a `Cat`

```python
from constelite.api.starlite.client import StarliteClient
from constelite.models import ref, StoreModel

from constelite_demo.models.cat import Cat

if __name__ == '__main__':
    client = StarliteClient(url="http://localhost:8001")

    r_cat = ref(
        Cat(name="Snowball")
    )
    print(r_cat)
```

```console
record=None
guid=None
state=Cat(model_name='Cat', name='Snowball')
state_model_name='Cat'
model_name='Ref'
```

What we created is not a model of a `Cat` but a reference to the model. We can see that the reference contains `state`, which holds the model of the `Cat`. And at the moment it has no `record`. This is expected, because we have not saved the ref yet.

!!! note
    See [Key concepts: Ref](../key_concepts/ref.md) for more in-depth explanation of references.

Let's go ahead an save it to the memory store:

```python
r_cat = client.store.put(
    ref=r_cat,
    store=StoreModel(uid="5ef14649-fd40-40a0-a693-de36c855a181")
)
print(r_cat)
```

```console
record=StoreRecordModel(
    store=StoreModel(
        uid=UUID('5ef14649-fd40-40a0-a693-de36c855a181'),
        name='Memory store'
    ),
    uid='be4fab6b-98cd-4ed4-b34e-8ae7cf1c93f2',
    url=None
)
guid=None
state=None
state_model_name='Cat'
model_name='Ref'
```

What we are doing here, is asking API to create a new record in the Memory store. What we see now is that `r_cat` now has a record in the Memory store and it has acquired a unique uid. Note that `put` does not return the state associated with the record. This is intentional to save traffic on sending references back and forth.

But no worries, we can always retrieve the state back by calling `get`:

```python
r_cat = client.store.get(ref=r_cat)
print(r_cat)
```

```console
record=StoreRecordModel(
    store=StoreModel(
        uid=UUID('5ef14649-fd40-40a0-a693-de36c855a181'),
        name='Memory store'
    ),
    uid='be4fab6b-98cd-4ed4-b34e-8ae7cf1c93f2',
    url=None
)
guid=None
state=Cat(model_name='Cat', name='Snowball')
state_model_name='Cat'
model_name='Ref'
```

Now we got a reference that contains both the record and a snapshot of the state.

## Modify records in store

Now let's assume we wanted to rename our cat. That's where the `patch` method comes in:

```python
r_cat.name = "Snowball II"

r_cat = client.store.patch(ref=r_cat)

r_cat = client.store.get(ref=r_cat)
print(r_cat)
```

```console
record=StoreRecordModel(
    store=StoreModel(
        uid=UUID('5ef14649-fd40-40a0-a693-de36c855a181'), 
        name='Memory store'
    ),
    uid='be4fab6b-98cd-4ed4-b34e-8ae7cf1c93f2',
    url=None
)
guid=None
state=Cat(model_name='Cat', name='Snowball II')
state_model_name='Cat'
model_name='Ref'
```

Now we have successfully updated (or patched) our record in the Memory store.

A couple of things to note:

* We can access attributes of the state inside reference as if they were attributes of the reference itself.

* Patch, similar to put, does not return the state

## Delete records from store

We can finally delete the record from the store using `delete`

```python
client.store.delete(ref=r_cat)
```

Now we have deleted the record of the Snowball II from the store and if we tried to get it, we would end up with a KeyError, because the store would fail to locate the record with the given uid.

## Final note

It is important to understand the difference between `put` and `patch`, especially regarding relations. You can read more on this topic in [Key concepts: Store](../key_concepts/store.md) and [Key concepts: Relationships](../key_concepts/relations.md)

If you want to develop a new store check out [For developers: Adding new store](../../for_developers/new_store.md)

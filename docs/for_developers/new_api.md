# Adding new API

API is constelite is responsible for:

* Providing user access to call protocols
* Providing user access to stores

For example, StarliteAPI creates a web server that accepts HTTP requests and translates them either into protocol calls or access to the core store methods: get, patch, post, delete and query.

If you want to support other ways to call protocols or access stores, you need a new API.

To create a new API, you should create a new class derived from the `ConsteliteAPI` and implement a `run` method


```python
from constelite.api import ConsteliteAPI

class MyAPI(ConsteliteAPI):
    def run(self, *args, **kwargs) -> None:
        ...
```

Not much, eh?

Don't worry, ConsteliteAPI is packed with methods that will help you to design your new API.


### Getting protocols

ConsteliteAPI has a method for discovering protocols (`discover_protocols`). Usually it will be called before the API is started and will populate API's protocols with instances of `ProtocolModel`.

```python
class MyAPI(ConsteliteAPI):
    def run(self, *args, **kwargs) -> None:
        ...

    def print_protocols(self) -> None:
        for protocol_model in self.protocols:
            print(protocol_model)


api = MyAPI()

api.print_protocols()
```

An example of what you will get:

```console
path='hello_world' name='HelloWorldProtocol' fn=<function protocol.wrap_fn.<locals>.wrapper at 0x10045d1c0> fn_model=<class 'pydantic.v1.main.hello_world'> ret_model=None slug='hello_world'
```

Looks like we are dealing with a protocol called "HelloWorldProtocol" with function that encapsulates the protocol logic given in `fn`. In addition, we are getting `fn_model` a BaseModel that we can use for validating function arguments and `ret_model` tells us that this protocol returns `None`

### Calling protocols

Say your API received a message from the user asking to call `hello_world` protocol with arguments `kwargs = {"name": "Lisa"}`. All you need to do, as an API developer is call `run_protocol` method. For example:


```python
class MyAPI(ConsteliteAPI):
    async def on_call_protocol_message_received(self, protocol_slug: str, kwargs: dict):
        logger = await self.get_logger()
        try:
            ret = await self.run_protocol(slug=protocol_slug, logger=logger, **kwargs)
        except ValueError:
            await self.send_message_to_user(f"Protocol {protocol_slug} is not found")
        except Exception as e:
            await self.send_message_to_user(f"Protocol {protocol_slug} failed with error: {e}")

    async send_message_to_user(self, message: str):
        ...
```

### Handling store calls

If your API support operations with a store, here is how you could handle them:

```python
class MyAPI(ConsteliteAPI):
    async def handle_put_request(self, ref: Ref, store_model: Optional[StoreModel]):
        if store is not None:
            store_uid = store.uid
        elif ref.record is not None:
            store_uid = ref.record.store.uid
        else:
            raise ValueError("Can't figure out where to save the reference")
        
        store = self.get_store(uid=store_uid)
        store.put(ref=ref)
```

Here we are using `get_store` method of the `ConsteliteAPI` to retrieve a store object that is registered under the given UID.
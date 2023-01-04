import inspect

from pydantic import BaseModel, UUID4, root_validator, validator

from typing import Callable, Literal, Optional

from starlite import Controller, Starlite, OpenAPIConfig, MiddlewareProtocol, State
from starlite import post, delete

from openapi_schema_pydantic import Tag

from constelite.config import load_config
from constelite.models import StateModel, Ref, StoreModel, resolve_model
from constelite.api_base import ConsteliteAPI
from constelite.store import BaseStore

import uvicorn

from loguru import logger

ControllerType = Literal['protocol', 'getter', 'setter']


class StoreController(Controller):
    path = '/store'

    class PostRequest(BaseModel):
        ref: Ref
        store: Optional[StoreModel]

        @root_validator
        def root(cls, values):
            store = values.get("store", None)
            ref = values["ref"]

            if store is None and ref.record is None:
                raise ValueError(
                    "Unknown store."
                    "Either send a reference with a record or supply a store"
                )
            if store is None:
                values['store'] = ref.record.store
            return values

    class RefRequest(BaseModel):
        ref: Ref

        @validator('ref')
        def validate_ref_store(cls, value):
            if value.record is None:
                raise ValueError("Reference has an empy record")
            return value

    @post('/put')
    def put(self, data: PostRequest, state: State) -> Ref:
        # breakpoint()
        ref = data.ref

        ref.state = resolve_model(values=ref.state)

        store = next(
            (
                store for store in state['stores']
                if store.uid == data.store.uid),
            None
        )

        if store is None:
            raise ValueError("Store not found")
        return store.put(ref)

    @post('/get')
    def get(self, data: RefRequest, state: State) -> StateModel:
        ref = data.ref

        record = data.ref.record

        if record is None:
            raise ValueError("Reference does not contain a store record")

        store = next(
            (
                store for store in state['stores']
                if store.uid == record.store.uid),
            None
        )

        if store is None:
            raise ValueError("Store not found")
        return store.get(ref)

    @post('/patch')
    def patch(self, data: RefRequest, state: State) -> Ref:
        ref = data.ref
        record = data.ref.record
        if record is None:
            raise ValueError("Reference does not contain a store record")

        ref.state = resolve_model(values=ref.state)

        store = next(
            (
                store for store in state['stores']
                if store.uid == store.uid),
            None
        )

        if store is None:
            raise ValueError("Store not found")
        return store.patch(ref)
    # @patch
    # def patch(self, data: RefRequest) -> Ref:
    #     ref = data.ref
    #     ref.state = resolve_model(values=ref.state)

    # @post(path='/load', tags=['store'], description='Load model from store')
    # def load(self, data: LoadRequest) -> Optional[FlexibleModel]:
    #     store = get_store()

    #     if store.ref_exists(data.ref):
    #         return store.load(data.ref)
    #     else:
    #         return None

    # @post(path='/save', tags=['store'], description='Store model')
    # def save(self, data: StoreRequest) -> Ref:
    #     store = get_store()
    #     return store.store(data)


class StarliteAPI(ConsteliteAPI):
    # _method_tags = {
    #     'protocol': Tag(
    #         name='Protocols'
    #     ),
    #     'setter': Tag(
    #         name='Setters'
    #     ),
    #     'getter': Tag(
    #         name='Getters'
    #     )
    # }
    def create_store_middleware(api):
        class StoreMiddleware(MiddlewareProtocol):
            def __init__(self, app) -> None:
                self.app = app

            async def __call__(self, scope, receive, send):
                app = scope['app']
                app.state.setdefault("stores", [])
                app.state['stores'] = api.stores
                await self.app(scope, receive, send)
        return StoreMiddleware

    def run(self):
        self.app = Starlite(
            route_handlers=[
                # self.generate_controller('protocol'),
                # self.generate_controller('getter'),
                # self.generate_controller('setter'),
                StoreController
            ],
            exception_handlers={
            },
            openapi_config=OpenAPIConfig(title=self.name, version=self.version),
            middleware=[self.create_store_middleware()]
        )
        uvicorn.run(self.app, port=self.port, host=self.host)

    # def generate_endpoint(
    #         self,
    #         method: APIModel,
    #         controller_type: ControllerType
    #      ) -> Callable:
    #     """Generates a post endpoint from a ProtocolAPI model.
    #     """

    #     async def method_wrapper(
    #         self,
    #         data: method.fn_model,
    #     ) -> method.ret_model:
    #         if inspect.iscoroutinefunction(method.fn):
    #             ret = await method.fn(**data.__dict__)
    #         else:
    #             ret = method.fn(**data.__dict__)
    #         return ret

    #     method_wrapper.__name__ = method.fn.__name__

    #     return post(
    #         path=f'/{method.fn.__name__}',
    #         tags=[controller_type],
    #         description=method.name
    #     )(method_wrapper)

    # def generate_controller(
    #         self,
    #         controller_type: ControllerType,
    #      ) -> Controller:
    #     attrs = {
    #         'path': f'/{controller_type}'
    #     }

    #     for method in getattr(self, f'get_{controller_type}_methods')():
    #         logger.info(f"Adding path for {method.name}")
    #         attrs[method.path] = self.generate_endpoint(method, controller_type)
    #     return type('ProtocolController', (Controller,), attrs)

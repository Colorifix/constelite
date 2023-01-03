import inspect

from pydantic import BaseModel

from typing import Callable, Literal, Optional

from starlite import Controller, post, Starlite, OpenAPIConfig
from openapi_schema_pydantic import Tag

from constelite import (
    ConsteliteAPI,
    APIModel,
    get_store,
    Ref,
    FlexibleModel,
    Model,
    resolve_model
)

import uvicorn

from loguru import logger

ControllerType = Literal['protocol', 'getter', 'setter']


def get_store(uid: UUID4):
    config = load_config()

    return next(
        (store for store in config.stores if store.uid==uid),
        None
    )


class StoreController(Controller):
    path = '/store'

    class RefRequest(BaseModel):
        ref: Ref

    @post(path='/write')
    def write(self, data: RefRequest) -> Ref:
        ref = data.ref
        ref.state = resolve_model(values=ref.state)

        store = get_store(ref.record.store.uid)

        return store.put(ref)

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
    _method_tags = {
        'protocol': Tag(
            name='Protocols'
        ),
        'setter': Tag(
            name='Setters'
        ),
        'getter': Tag(
            name='Getters'
        )
    }

    def run(self):
        self.app = Starlite(
            route_handlers=[
                self.generate_controller('protocol'),
                self.generate_controller('getter'),
                self.generate_controller('setter'),
                StoreController
            ],
            exception_handlers={
            },
            openapi_config=OpenAPIConfig(title=self.name, version=self.version),
            middleware=[]
        )
        uvicorn.run(self.app, port=self.port, host=self.host)

    def generate_endpoint(
            self,
            method: APIModel,
            controller_type: ControllerType
         ) -> Callable:
        """Generates a post endpoint from a ProtocolAPI model.
        """

        async def method_wrapper(
            self,
            data: method.fn_model,
        ) -> method.ret_model:
            if inspect.iscoroutinefunction(method.fn):
                ret = await method.fn(**data.__dict__)
            else:
                ret = method.fn(**data.__dict__)
            return ret

        method_wrapper.__name__ = method.fn.__name__

        return post(
            path=f'/{method.fn.__name__}',
            tags=[controller_type],
            description=method.name
        )(method_wrapper)

    def generate_controller(
            self,
            controller_type: ControllerType,
         ) -> Controller:
        attrs = {
            'path': f'/{controller_type}'
        }

        for method in getattr(self, f'get_{controller_type}_methods')():
            logger.info(f"Adding path for {method.name}")
            attrs[method.path] = self.generate_endpoint(method, controller_type)
        return type('ProtocolController', (Controller,), attrs)

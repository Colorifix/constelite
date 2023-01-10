import inspect

from pydantic import BaseModel, root_validator, validator

from typing import Literal, Optional

from starlite import Controller, Starlite, OpenAPIConfig, MiddlewareProtocol, State
from starlite import post

from openapi_schema_pydantic import Tag

from constelite.models import StateModel, Ref, StoreModel, resolve_model
from constelite.store import BaseStore
from constelite.api.api import ConsteliteAPI

import uvicorn

from loguru import logger

from constelite.api.starlite.controllers import StoreController

ControllerType = Literal['protocol', 'getter', 'setter']


class StarliteAPI(ConsteliteAPI):
    app: Optional[Starlite]
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

    def __init__(self, **data):
        super().__init__(**data)
        self.app = Starlite(
            route_handlers=[
                # self.generate_controller('protocol'),
                # self.generate_controller('getter'),
                # self.generate_controller('setter'),
                StoreController
            ],
            exception_handlers={
            },
            openapi_config=OpenAPIConfig(
                title=self.name, version=self.version),
            middleware=[self.create_store_middleware()]
        )

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

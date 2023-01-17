from typing import Literal, Optional

from starlite import Provide, Starlite, OpenAPIConfig, MiddlewareProtocol

from openapi_schema_pydantic import Tag

from constelite.api.api import ConsteliteAPI

import uvicorn

from loguru import logger

from constelite.api.starlite.controllers import (
        StoreController, protocol_controller
)

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

    def provide_api(self):
        return self

    def run(self):
        self.app = Starlite(
            route_handlers=[
                protocol_controller(self),
                StoreController
            ],
            exception_handlers={
            },
            openapi_config=OpenAPIConfig(
                title=self.name,
                version=self.version
            ),
            middleware=[],
            dependencies={"api": Provide(self.provide_api)}
        )
        uvicorn.run(self.app, port=self.port, host=self.host)

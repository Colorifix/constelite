from typing import Literal, Optional

from starlite import Provide, Starlite, OpenAPIConfig

from constelite.api.api import ConsteliteAPI

import uvicorn

from constelite.api.starlite.controllers import (
        StoreController, protocol_controller
)

ControllerType = Literal['protocol', 'getter', 'setter']


class StarliteAPI(ConsteliteAPI):
    app: Optional[Starlite]

    def provide_api(self):
        """Provides instance of self to route handlers
        """
        return self

    def generate_app(self) -> Starlite:
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
            dependencies={"api": Provide(self.provide_api)}
        )

        return self.app

    def run(self) -> None:
        uvicorn.run(self.app, port=self.port, host=self.host)

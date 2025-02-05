from __future__ import annotations
import os

import json

from typing import Literal

from litestar import Response, MediaType
from litestar.exceptions import  ValidationException
from litestar.static_files import create_static_files_router
from litestar.config.cors import CORSConfig
from litestar import Litestar, Router, get
from litestar.di import Provide
from litestar.response import Template
from litestar.template import TemplateConfig
from litestar.openapi import OpenAPIConfig
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.openapi.spec import Components, SecurityScheme

from constelite.api.api import ConsteliteAPI
import uvicorn

ControllerType = Literal['protocol', 'getter', 'setter']


class StarliteAPI(ConsteliteAPI):
    def __init__(
        self,
        **kwargs
    ):
        super().__init__(**kwargs)

    async def provide_api(self) -> StarliteAPI:
        """Provides instance of self to route handlers
        """
        return self


    def generate_app(self) -> Litestar:
        from constelite.api.starlite.controllers import (
            StoreController,
            threaded_protocol_router,
            task_protocol_router
        )
        route_handlers = [
            threaded_protocol_router(self),
            task_protocol_router(self),
            StoreController
        ]

        main_router = Router(
            path="/",
            route_handlers=route_handlers
        )

        def handle_validation_exception(_, exc: ValidationException) -> Response:
            return Response(
                media_type=MediaType.JSON,
                content={
                    "extra": {"error_message": f"Validation exception {json.dumps(exc.extra)}"},
                    "detail": exc.detail,
                },
                status_code=400,
            )

        self.app = Litestar(
            route_handlers=[main_router],
            exception_handlers={
                ValidationException: handle_validation_exception
            },
            openapi_config=OpenAPIConfig(
                title=self.name,
                version=self.version,
                use_handler_docstrings=True
            ),
            dependencies={
                "api": Provide(self.provide_api)
            }
        )

        return self.app

    def run(self, host: str, port: int) -> None:
        uvicorn.run(self.app, port=port, host=host)

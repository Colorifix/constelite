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
from constelite.api.starlite.middlewares import JWTAuthenticationMiddleware
import uvicorn

from colorifix_alpha.util import get_config


ControllerType = Literal['protocol', 'getter', 'setter']


@get(path="/ping", summary="Ping")
async def ping() -> bool:
    return True


class StarliteAPI(ConsteliteAPI):
    def __init__(
        self,
        index_template=None,
        template_dir=None,
        static_dir=None,
        docs_dir=None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.index_template = index_template
        self.template_dir = template_dir
        self.static_dir = static_dir
        self.docs_dir = docs_dir

    async def provide_api(self) -> StarliteAPI:
        """Provides instance of self to route handlers
        """
        return self

    @property
    def context(self):
        return {
            "name": self.name,
            "version": self.version,
            "stores": self.stores,
            "temp_store": self.temp_store,
            "dependencies": self._dependencies
        }

    def generate_index_route(self, index_template):
        async def index() -> Template:
            return Template(
                template_name=index_template,
                context=self.context
            )
        return get(path="/", include_in_schema=False)(index)

    def generate_app(self) -> Litestar:
        from constelite.api.starlite.controllers import (
            StoreController,
            threaded_protocol_router,
            task_protocol_router
        )
        route_handlers = [
            threaded_protocol_router(self),
            task_protocol_router(self),
            StoreController,
            ping
        ]
        open_route_handlers = []

        if (
            self.static_dir is not None
            and os.path.exists(self.static_dir)
        ):
            open_route_handlers.append(
                create_static_files_router(
                    directories=[self.static_dir],
                    path="/static"
                )
            )

        if (
            self.docs_dir is not None
            and os.path.exists(self.docs_dir)
        ):
            open_route_handlers.append(
                create_static_files_router(
                    directories=[self.docs_dir],
                    path="/docs",
                    html_mode=True
                )
            )

        template_config = None

        if (
            self.index_template is not None
            and self.template_dir is not None
            and os.path.exists(self.template_dir)
        ):
            open_route_handlers.append(
                self.generate_index_route(self.index_template)
            )

            template_config = TemplateConfig(
                directory=self.template_dir,
                engine=JinjaTemplateEngine
            )

        main_router = Router(
            path="/",
            route_handlers=route_handlers,
            middleware=[JWTAuthenticationMiddleware],
            security=[{"BearerToken": []}],
        )

        open_router = Router(
            path="/",
            route_handlers=open_route_handlers,
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
            route_handlers=[main_router, open_router],
            exception_handlers={
                ValidationException: handle_validation_exception
            },
            # openapi_config=None,
            openapi_config=OpenAPIConfig(
                title=self.name,
                version=self.version,
                use_handler_docstrings=True,
                security=[{"BearerToken": []}],
                components=Components(
                    security_schemes={
                        "BearerToken": SecurityScheme(
                            type="http",
                            scheme="bearer",
                        )
                    },
                ),
            ),
            dependencies={
                "api": Provide(self.provide_api)
            },
            template_config=template_config,
            cors_config=CORSConfig(
                allow_origins=get_config("security", "allowed_origins"),
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        )

        return self.app

    def run(self, host: str, port: int) -> None:
        uvicorn.run(self.app, port=port, host=host)

import os

from pathlib import Path

from typing import Literal, Optional

from pydantic import Field

from starlite import (
    Provide,
    Starlite,
    OpenAPIConfig,
    Template,
    TemplateConfig,
    StaticFilesConfig,
    get
)

from starlite.contrib.jinja import JinjaTemplateEngine

from constelite.api.api import ConsteliteAPI

import uvicorn

from constelite.api.starlite.controllers import (
        StoreController, protocol_controller
)

ControllerType = Literal['protocol', 'getter', 'setter']


class StarliteAPI(ConsteliteAPI):
    app: Optional[Starlite] = Field(exclude=True)
    index_template: Optional[str]
    static_dir: Optional[str]
    template_dir: Optional[str]

    def __init__(
        self,
        index_template=None,
        template_dir=None,
        static_dir=None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.index_template = index_template
        self.template_dir = template_dir
        self.static_dir = static_dir

    def provide_api(self):
        """Provides instance of self to route handlers
        """
        return self

    @property
    def context(self):
        return {
            "name": self.name,
            "version": self.version,
            "host": self.host,
            "port": self.port,
            "stores": self.stores,
            "temp_store": self.temp_store,
            "dependencies": self._dependencies
        }

    def generate_index_route(self, index_template):
        def index() -> Template:
            return Template(
                name=index_template,
                context=self.context
            )
        return get(path="/", include_in_schema=False)(index)

    def generate_app(self) -> Starlite:
        route_handlers = [
            protocol_controller(self),
            StoreController
        ]

        template_config = None
        static_files_config = None

        if (
            self.index_template is not None
            and self.template_dir is not None
            and os.path.exists(self.template_dir)
        ):
            route_handlers.append(
                self.generate_index_route(self.index_template)
            )

            template_config = TemplateConfig(
                directory=Path(self.template_dir),
                engine=JinjaTemplateEngine
            )

            if (
                self.static_dir is not None
                and os.path.exists(self.static_dir)
            ):
                static_files_config = StaticFilesConfig(
                    path="/static", directories=[self.static_dir]
                )
        self.app = Starlite(
            route_handlers=route_handlers,
            exception_handlers={
            },
            openapi_config=OpenAPIConfig(
                title=self.name,
                version=self.version,
                use_handler_docstrings=True
            ),
            dependencies={"api": Provide(self.provide_api)},
            template_config=template_config,
            static_files_config=static_files_config
        )

        return self.app

    def run(self) -> None:
        uvicorn.run(self.app, port=self.port, host=self.host)

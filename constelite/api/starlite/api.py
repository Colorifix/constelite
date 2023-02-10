from pathlib import Path

from typing import Literal, Optional

from pydantic import Field

from starlite import (
    Provide,
    Starlite,
    OpenAPIConfig,
    Template,
    TemplateConfig,
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
    template_dir: Optional[str]

    def __init__(self, index_template=None, template_dir=None, **kwargs):
        super().__init__(**kwargs)
        self.index_template = index_template
        self.template_dir = template_dir

    def provide_api(self):
        """Provides instance of self to route handlers
        """
        return self

    def generate_index_route(self, index_template):
        def index() -> Template:
            return Template(name=index_template)
        return get(path="/")(index)

    def generate_app(self) -> Starlite:
        route_handlers = [
            protocol_controller(self),
            StoreController
        ]

        template_config = None

        if self.index_template is not None and self.template_dir is not None:
            route_handlers.append(
                self.generate_index_route(self.index_template)
            )

            breakpoint()

            template_config = TemplateConfig(
                directory=Path(self.template_dir),
                engine=JinjaTemplateEngine
            )

        self.app = Starlite(
            route_handlers=route_handlers,
            exception_handlers={
            },
            # openapi_config=OpenAPIConfig(
            #     title=self.name,
            #     version=self.version
            # ),
            openapi_config=None,
            dependencies={"api": Provide(self.provide_api)},
            template_config=template_config
        )

        return self.app

    def run(self) -> None:
        uvicorn.run(self.app, port=self.port, host=self.host)

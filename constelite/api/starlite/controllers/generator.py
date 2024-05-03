import json
from typing import Any, Callable, List, Type, Coroutine

from pydantic.v1 import BaseModel


from litestar import Router, post
from litestar.handlers import BaseRouteHandler

from constelite.protocol import ProtocolModel
from constelite.models import resolve_model

from .models import ProtocolRequest

def generate_route(
        data_cls: Type[BaseModel],
        ret_cls: Type[BaseModel],
        fn: Coroutine
    ) -> Callable:
    """Generates a starlite route function.

    Arguments:
        data_cls: A typehint for the endpoint data argument.
        ret_cls: A return typehint.
        fn: A coroutine that executes the endpoint logic.

    Returns:
        A litestar route function with the given typehint.
    """
    async def endpoint(data: ProtocolRequest[data_cls], api: Any) -> ret_cls:
        args = resolve_model(
            values=json.loads(data.args.json()),
            model_type = data.args.__class__
        )

        kwargs = {
            field_name: getattr(args, field_name, None)
            for field_name in args.__fields__.keys()
        }

        logger = await api.get_logger(data.logger)
        
        return await fn(api, logger, **kwargs)

    # functools.wraps removes __annotations__ from endpoint
    endpoint.__name__ = fn.__name__
    endpoint.__doc__ = fn.__doc__
    endpoint.__module__ = fn.__module__

    return endpoint


def generate_protocol_router(
        api: "StarliteAPI",
        path: str,
        fn_wrapper: Callable[[ProtocolModel], Callable],
        tags: List[str] = [],
        extra_route_handlers: List[BaseRouteHandler] = []
) -> Router:
    """
    Generates a litestar router that serves all api protocols as endpoints.

    Arguments:
        api: Instance of the StarliteAPI class.
        path: Path to the root endpoint for protocols.
        fn_wrapper: A function that converts a protocol model to a litestar route function.
        tags: Tags to add for each protocol endpoint.
        extra_route_handlers: Extra route handlers to add to the router.
    
    Returns:
        A litestar router that serves all api protocols as endpoints.
    """
    handlers = []

    for protocol_model in api.protocols:

        protocol_tags = []
        path_parts = protocol_model.path.split('/')
        if len(path_parts) > 1:
            protocol_tags.extend(path_parts[:-1])

        endpoint = fn_wrapper(protocol_model)

        handlers.append(
            post(
                path=protocol_model.path,
                summary=protocol_model.name,
                tags=protocol_tags
            )(endpoint)
        )

    return Router(
        path=path,
        tags=tags,
        route_handlers=handlers + extra_route_handlers
    )

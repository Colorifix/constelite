from typing import Any, Callable, List, TYPE_CHECKING
import traceback
import json
from loguru import logger

from litestar import Router, post
from litestar.handlers import HTTPRouteHandler
from litestar.exceptions import HTTPException

from constelite.protocol import ProtocolModel
from constelite.models import resolve_model

from constelite.api.starlite.controllers.models import ProtocolRequest

if TYPE_CHECKING:
    from constelite.api.starlite.api import StarliteAPI

def generate_route(
        # data_cls: Type[BaseModel],
        # ret_cls: Type[BaseModel] | None,
        protocol_model: ProtocolModel,
        fn: Callable
    ) -> Callable:
    """Generates a starlite route function.

    Arguments:
        data_cls: A typehint for the endpoint data argument.
        ret_cls: A return typehint.
        fn: A coroutine that executes the endpoint logic.

    Returns:
        A litestar route function with the given typehint.
    """
    async def endpoint(data: ProtocolRequest[protocol_model.fn_model], api: Any) -> protocol_model.ret_model:
        args: protocol_model.fn_model = resolve_model(
            values=json.loads(data.args.json()),
            model_type = protocol_model.fn_model
        )

        kwargs = {
            field_name: getattr(args, field_name, None)
            for field_name in args.__fields__.keys()
        }

        logger = await api.get_logger(data.logger)
        try:
            return await fn(api, logger, **kwargs)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail="Internal Server Error",
                extra={
                    "error_message": f"Runtime error while running {protocol_model.name}: {repr(e)}",
                    "traceback": traceback.format_exc()
                }
            )

    # functools.wraps removes __annotations__ from endpoint
    endpoint.__name__ = fn.__name__
    endpoint.__doc__ = fn.__doc__
    endpoint.__module__ = fn.__module__

    return endpoint


def generate_protocol_router(
        api: 'StarliteAPI',
        path: str,
        fn_wrapper: Callable[[ProtocolModel], Callable],
        tags: List[str] = [],
        extra_route_handlers: List[HTTPRouteHandler] = []
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

        protocol_tags: list[str] = []
        if protocol_model.path:
            path_parts = protocol_model.path.split('/')
            if len(path_parts) > 1:
                protocol_tags.extend(path_parts[:-1])

        endpoint_fn = fn_wrapper(protocol_model)
        
        endpoint = generate_route(
            protocol_model=protocol_model,
            fn=endpoint_fn
        )

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

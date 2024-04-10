from typing import Any, Callable
import inspect
from litestar import Controller, post

from constelite.models import StateModel, Ref, resolve_model
from constelite.api import ProtocolModel


def generate_method(
        protocol_model: ProtocolModel
        ) -> Callable[[StateModel, "StarliteAPI"], Any]:
    ret_model = protocol_model.ret_model
    fn = protocol_model.fn
    fn_model = protocol_model.fn_model

    def wrapper(self, data: Any, api: Any) -> ret_model:
        kwargs = {}
        if "logger" in inspect.signature(fn).parameters or \
                "logger" in fn_model.__annotations__:
            kwargs["logger"] = api.get_logger(data.pop("logger", None))

        for key, value in data.items():
            if isinstance(value, dict) and 'model_name' in value:
                kwargs[key] = resolve_model(value)
            else:
                kwargs[key] = value

        kwargs['api'] = api
        ret = fn(**kwargs)

        if isinstance(ret, StateModel):
            temp_store = getattr(api, 'temp_store', None)

            ref = Ref[ret_model](state=ret)

            if temp_store is not None:
                return temp_store.put(
                    ref=ref
                )
            else:
                return ref

        return ret

    wrapper.__name__ = fn.__name__
    wrapper.__module__ = fn.__module__
    wrapper.__doc__ = fn.__doc__
    return wrapper


def protocol_controller(api: "StarliteAPI") -> Controller:
    """Generates a controller to handle protocol endpoints
    """
    attrs = {
        "path": "/protocols",
        "tags": ["Protocols"]
    }

    for protocol_model in api.protocols:

        tags = []
        path_parts = protocol_model.path.split('/')
        if len(path_parts) > 1:
            tags.extend(path_parts[:-1])

        attrs[protocol_model.slug] = post(
            path=protocol_model.path,
            summary=protocol_model.name,
            tags=tags,
            sync_to_thread=True
        )(generate_method(protocol_model))

    return type("ProtocolController", (Controller,), attrs)

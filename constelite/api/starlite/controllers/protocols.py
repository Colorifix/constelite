from typing import Any, Callable
from starlite import Controller, post

from constelite.models import StateModel, Ref
from constelite.api import ProtocolModel


def generate_method(
        protocol_model: ProtocolModel
        ) -> Callable[[StateModel, "StarliteAPI"], Any]:
    fn_model = protocol_model.fn_model
    ret_model = protocol_model.ret_model
    fn = protocol_model.fn

    def wrapper(self, data: fn_model, api: Any) -> ret_model:
        kwargs = {
            field_name: getattr(data, field_name, None)
            for field_name in data.__fields__.keys()
        }
        kwargs['api'] = api
        ret = fn(**kwargs)

        if isinstance(ret, StateModel):
            temp_store = getattr(api, 'temp_store', None)

            if temp_store is not None:
                return temp_store.put(
                    ref=Ref[ret_model](state=ret)
                )

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

        attrs[protocol_model.slug] = post(path=protocol_model.path, name='foo')(
            generate_method(protocol_model)
        )

    return type("ProtocolController", (Controller,), attrs)

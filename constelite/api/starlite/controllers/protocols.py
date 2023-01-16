from typing import Any
from starlite import Controller, post

from constelite.models import Ref


def generate_method(protocol_model):
    fn_model = protocol_model.fn_model
    ret_model = protocol_model.ret_model
    fn = protocol_model.fn

    def wrapper(self, data: fn_model, api: Any) -> ret_model:
        args = {
            field_name: getattr(data, field_name, None)
            for field_name in data.__fields__.keys()
        }
        args['api'] = api
        ret = fn(**args)

        temp_store = getattr(api, 'temp_store', None)

        if temp_store is not None:
            return temp_store.put(
                ref=Ref[ret_model](state=ret)
            )
        else:
            return ret

    wrapper.__name__ = fn.__name__
    wrapper.__module__ = fn.__module__
    wrapper.__doc__ = fn.__doc__

    return wrapper


def protocol_controller(api) -> Controller:
    attrs = {
        "path": "/protocols"
    }

    for protocol_model in api.protocols:

        attrs[protocol_model.slug] = post(path=protocol_model.path)(
            # generate_method(protocol_model.fn, protocol_model.fn_model)
            generate_method(protocol_model)
        )

    return type("ProtocolController", (Controller,), attrs)

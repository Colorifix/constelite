from functools import wraps
import inspect

from constelite.models import StateModel, Ref
from constelite.protocol import ProtocolModel
from constelite.api.starlite.controllers.generator import (
    generate_protocol_router,
    generate_route
)

def direct_call_wrapper(protocol_model: ProtocolModel):
    @wraps(protocol_model.fn)
    async def wrapper(api, logger, **kwargs):
        ret = await protocol_model.fn(api, logger, **kwargs)

        if isinstance(ret, StateModel):
            temp_store = getattr(api, 'temp_store', None)

            ref = Ref[protocol_model.ret_model](state=ret)

            if temp_store is not None:
                return temp_store.put(
                    ref=ref
                )
            else:
                return ref

        return ret

    return generate_route(
        data_cls=protocol_model.fn_model,
        ret_cls=protocol_model.ret_model,
        fn=wrapper
    )


def threaded_protocol_router(api):
    return generate_protocol_router(
        api=api,
        path='/protocols',
        fn_wrapper=direct_call_wrapper,
        tags=["Protocols"]
    )

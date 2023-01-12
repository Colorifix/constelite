from starlite import Controller, post
from pydantic import BaseModel


async def intercept(request):
    print(await request.json())


class Test(BaseModel):
    messages: list[str]


def generate_method(fn, model):
    def wrapper(self, data: model) -> fn.__annotations__.get('return', None):
        return fn(data.dict())
    return wrapper


def protocol_controller(api) -> Controller:
    attrs = {
        "path": "/protocols",
        "before_request": intercept
    }

    def test(self, data: Test) -> str:
        return "ok"

    for protocol_model in api.protocols:

        attrs[protocol_model.slug] = post(path=protocol_model.path)(
            # generate_method(protocol_model.fn, protocol_model.fn_model)
            protocol_model.fn
        )

    return type("ProtocolController", (Controller,), attrs)

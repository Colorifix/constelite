from starlite import Controller, post


async def intercept(request):
    print(await request.json())


def protocol_controller(api) -> Controller:
    attrs = {
        "path": "/protocols",
        "before_request": intercept
    }

    for protocol_model in api.protocols:
        breakpoint()
        attrs[protocol_model.slug] = post(path=protocol_model.path)(
            protocol_model.fn
        )

    return type("ProtocolController", (Controller,), attrs)

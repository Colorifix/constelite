from pydantic import validate_arguments


def method(a: str, b: int) -> bool:
    return True

vm = validate_arguments(method)

breakpoint()
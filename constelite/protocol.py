from pydantic import validate_arguments


class protocol:
    """Decorator for protocols
    """
    __protocols = {}

    @classmethod
    def protocols(cls):
        return cls.__protocols

    def __init__(self, name):
        self.name = name

    def __call__(self, fn):
        vfn = validate_arguments(fn)
        self.__protocols[self.name] = vfn
        return vfn

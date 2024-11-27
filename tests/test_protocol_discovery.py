from types import ModuleType, FunctionType
import inspect
import pkgutil
import importlib
import colorifix_alpha

from pydantic.v1.generics import GenericModel

from constelite.protocol import Protocol, ProtocolModel

from colorifix_alpha.protocols.converters.converter import ConverterProtocol
class MyConverter(ConverterProtocol[int]):
    pass

CreateCulture = type("CreateCulture", (ConverterProtocol[int],), {})

def get_protocols_from_module(module_name: str) -> list[ProtocolModel]:
    module = importlib.import_module(module_name)

    cls_protocols = inspect.getmembers(
        module,
        lambda member: (
            inspect.isclass(member)
            and issubclass(member, Protocol)
            and member != Protocol
            and '[' not in member.__name__
            and GenericModel not in member.__bases__
        )
    )

    fn_protocols = inspect.getmembers(
        module,
        lambda member: (
            isinstance(member, FunctionType)
            and hasattr(member, 'get_model')
        )
    )

    return [cls.get_model() for _, cls in cls_protocols] + [fn.get_model() for _, fn in fn_protocols]

def walk(root_package: ModuleType):
    protocol_models = []
    for _, module_name, is_pkg in pkgutil.walk_packages(root_package.__path__, root_package.__name__ + "."):
        if not is_pkg:
            try:
                new_models = get_protocols_from_module(module_name)
                protocol_models.extend(new_models)
            except ImportError:
                print("Failed to import module:", module_name)
    return protocol_models

if __name__ == "__main__":
    models = walk(colorifix_alpha)
    for model in models:
        print(model.fn_model.__name__)
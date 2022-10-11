from typing import List, Optional
from constelite import getter, protocol, setter
from constelite import GetterAPIModel, SetterAPIModel, ProtocolAPIModel


class ConsteliteAPI:
    """Base class for API implementations
    """
    def __init__(
            self,
            name,
            version: Optional[str] = None,
            port: Optional[int] = None
    ):
        self.name = name
        self.version = version
        self.port = port

    def get_protocol_methods(self) -> List[ProtocolAPIModel]:
        return protocol.protocols

    def get_getter_methods(self) -> List[GetterAPIModel]:
        return getter.getters

    def get_setter_methods(self) -> List[SetterAPIModel]:
        return setter.setters

    def run(self):
        pass

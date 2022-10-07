from typing import Dict
from constelite import getter, protocol, setter
from constelite import GetterAPIModel, SetterAPIModel, ProtocolAPIModel


class ConsteliteAPI:
    def get_protocol_methods(self) -> Dict[str, ProtocolAPIModel]:
        return protocol.protocols

    def get_getter_methods(self) -> Dict[str, GetterAPIModel]:
        return getter.getters

    def get_setter_methods(self) -> Dict[str, SetterAPIModel]:
        return setter.setters

    def run(self):
        pass

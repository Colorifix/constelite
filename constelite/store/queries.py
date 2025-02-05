from pydantic.v1 import BaseModel
from constelite.models import (
    Ref,
)
from typing import Dict, Any


class Query(BaseModel):
    pass

class RefQuery(Query):
    ref: Ref


class BackrefQuery(RefQuery):
    class_name: str
    backref_field_name: str


class PropertyQuery(Query):
    property_values: Dict[str, Any]

    def __init__(self, **data):
        property_values = data.pop('property_values', None)
        if property_values is None:
            super().__init__(property_values=data)
        else:
            super().__init__(property_values=property_values)


class GetAllQuery(Query):
    pass

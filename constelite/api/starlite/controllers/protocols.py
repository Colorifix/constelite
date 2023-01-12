from typing import List, Dict
from inspect import Parameter
from starlite import Controller, post

from constelite.models import StateModel, Ref


def generate_post_method(fn):
    fields = {}
    for field_name, field in fn.__annotations__['data'].__fields__.items():
        if issubclass(field.type_, StateModel):
            if field.type_ != field.outer_type_:
                if field.outer_type_.__origin__ == list:
                    new_field_type = List[Ref[field.type_]]
                    fields[field_name] = (
                        (
                            new_field_type,
                            ...
                        )
                        if field.default == Parameter.empty
                        else (
                            new_field_type,
                            field.default
                        )
                    )
                if field.outer_type_.__origin__ == dict:


def generate_protocol_controller(api, path: str) -> Controller:
    methods = {}

    for protocol_model in api.protocols:
        methods[protocol_model.slug] = post()

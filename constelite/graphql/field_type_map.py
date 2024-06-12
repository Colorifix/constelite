import graphene
from graphene.types.generic import GenericScalar
from enum import Enum
from typing import get_origin, get_args, Literal, TypeVar
from uuid import UUID
from datetime import datetime
from pydantic.v1 import BaseModel


class ConversionError(Exception):
    pass


def convert_to_graphql_type(type_):
    """
    Recursive function to convert to a Graphene GraphQL type.

    When used to create a schema, we need to use instances of the types,
    e.g. graphene.String().

    If no conversion is defined, return None and the field will be excluded
    from the schema.

    Args:
        type_:

    Returns:
        Graphene type instance, or None

    """
    if get_origin(type_) is Literal:
        # If all objects in the literal are the same type, then use that type
        # for the conversion
        types = set([type(l) for l in get_args(type_)])
        if len(types) > 1:
            # More than one type in literal
            # Don't know how to covert this so return None
            raise ConversionError("More than one type in literal")
        else:
            # Consistent type in the literal. Convert this to Graphene type
            # below
            type_ = list(types)[0]
    elif get_origin(type_) is list:
        converted_type = None
        for a in get_args(type_):
            g = convert_to_graphql_type(a)
            if converted_type is None:
                converted_type = g
            elif type(g) != type(converted_type):
                raise ConversionError("More than one type in list")
        return graphene.List(type(converted_type))
    elif get_origin(type_) is not None:
        # a type with an origin.
        # Look through all the args and convert to Graphene types.
        # If all args are of the same type, return that type.
        # If not, we don't know how to deal with it and return None
        converted_type = None
        for a in get_args(type_):
            if a != type(None):
                g = convert_to_graphql_type(a)
                if converted_type is None:
                    converted_type = g
                elif type(g) != type(converted_type):
                    raise ConversionError(
                        f"More than one type in args: {type_}"
                    )
        return converted_type

    if isinstance(type_, TypeVar) or issubclass(type_, BaseModel):
        return GenericScalar()
    elif issubclass(type_, Enum):
        return graphene.Enum.from_enum(type_)()
    elif issubclass(type_, str):
        return graphene.String()
    elif issubclass(type_, int):
        return graphene.Int()
    elif issubclass(type_, float):
        return graphene.Float()
    elif issubclass(type_, bool):
        return graphene.Boolean()
    elif issubclass(type_, UUID):
        return graphene.ID()
    elif issubclass(type_, datetime):
        return graphene.DateTime()

    raise ConversionError(f"No GraphQL Type defined for {type_}")



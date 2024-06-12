import unittest
from typing import Optional, ForwardRef, List
from datetime import datetime
from uuid import UUID
import os

from constelite.graphql.schema import GraphQLSchemaManager
from constelite.graphql.utils import GraphQLModelQuery
import graphql_query
from constelite.models import (
    StateModel, Association, Composition, Aggregation, backref, Dynamic
)
from pydantic.v1 import ConstrainedInt
from enum import Enum


class Enum1(Enum):
    a = 1


class BarGraphQL(StateModel):
    name: str


class BazGraphQL(StateModel):
    name: str
    foo: backref(model="FooGraphQL", from_field="baz")


class FooGraphQL(StateModel):
    int_field: Optional[int]
    str_field: Optional[str]
    bool_field: Optional[bool]
    float_field: Optional[float]
    model_field: Optional[BarGraphQL]
    list_field: Optional[List[int]]
    datetime_field: Optional[datetime]
    uuid_field: Optional[UUID]
    constrained_int_field: Optional[ConstrainedInt]
    enum_type: Optional[Enum1]

    dynamic_int: Optional[Dynamic[int]]

    self_association: Optional[Association[ForwardRef("FooGraphQL")]]
    association: Optional[Association[BarGraphQL]]
    composition: Optional[Composition[BarGraphQL]]
    aggregation: Optional[Aggregation[BarGraphQL]]
    baz: Optional[Association[BazGraphQL]]


def test_schema_creation():
    schema = GraphQLSchemaManager().create_graphql_schema(root_cls=FooGraphQL)

    dir_path = os.path.dirname(os.path.realpath(__file__))

    # For generating new expected test results
    # (if absolutely confident they are correct)
    # with open(
    #         os.path.join(dir_path, 'expected_graphql_schema_new.txt'), 'w'
    # ) as f:
    #     print(schema, file=f)

    with open(os.path.join(dir_path, 'expected_graphql_schema.txt'), 'r') as f:
        expected_schema = "".join(f.readlines())

    # the printed version will have a new line at the end
    schema_string = str(schema) + "\n"
    assert schema_string == expected_schema


def test_query_string_creation():
    expected_query_string = """
        query {
          dnasamples(
            barcode: "2118717660"
          ) {
              guid
              model_name
              state_model_name
              record {
                  uid
                  store {
                      uid
                  }
              }
              state {
                  barcode
                  location {
                    guid
                    model_name
                    state_model_name
                    record {
                        uid
                        store {
                            uid
                        }
                    }
                    state {
                      name
                      model_name
                    }
                  }
                  model_name
              }
          }
        }
    """

    q = GraphQLModelQuery(
        state_fields=[
            'barcode',
            graphql_query.Field(name="location", fields=['name'])
        ],
        arguments={'barcode': '"2118717660"'},
        state_model_name='DNASample'
    )

    # Standardise all whitespace for the comparisons
    assert ' '.join(q.query_string.split()) == \
           ' '.join(expected_query_string.split())

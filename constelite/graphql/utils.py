import graphql_query
from pydantic.v1 import BaseModel, root_validator
from constelite.models import StoreModel, StateModel, get_auto_resolve_model
from typing import Optional, Union, ClassVar


def convert_model_to_query_name(cls: Union[StateModel, str]):
    if not isinstance(cls, str):
        cls = cls.__name__
    return cls.lower() + 's'


class GraphQLQuery(BaseModel):
    query_string: str


class GraphQLModelQuery(GraphQLQuery):
    record_fields: ClassVar = graphql_query.Field(
        name="record",
        fields=[
            'uid',
            graphql_query.Field(
                name="store",
                fields=['uid']
            )
        ]
    )
    required_ref_fields: ClassVar[tuple] = (
        "guid", "model_name", "state_model_name")
    required_state_fields: ClassVar[tuple] = (
        "model_name",
    )
    state_model_name: Optional[str]
    state_fields: Optional[list[Union[str, graphql_query.Field]]] = None
    arguments: Optional[dict[str, str]] = None

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def _get_ref_fields(cls):
        field_list = list(GraphQLModelQuery.required_ref_fields)
        field_list.append(cls.record_fields)
        return field_list

    @classmethod
    def _add_model_fields(cls,
                          state_fields: Optional[
                                     list[str, graphql_query.Field]
                                 ]):
        """
        Recursively adds any fields we need to define the full Ref model
        including the record and state

        Args:
            state_fields:

        Returns:

        """
        # Get the Ref fields to start off
        fields = cls._get_ref_fields()

        # Then add any state fields
        if state_fields:
            for f in state_fields:
                if isinstance(f, graphql_query.Field):
                    f.fields = cls._add_model_fields(
                        f.fields
                    )
            for f in GraphQLModelQuery.required_state_fields:
                if f not in state_fields:
                    state_fields.append(f)
            fields.append(
                graphql_query.Field(name='state', fields=state_fields)
            )
        return fields

    @root_validator(pre=True)
    def check_query_string(cls, values):
        if values.get('query_string') is not None and (
                values.get('fields') is not None or
                values.get('arguments') is not None):
            raise ValueError(
                "Cannot define both the query string "
                "and fields or arguments"
            )
        elif values.get('query_string') is None:
            # Create a query string from the fields and arguments

            fields = cls._add_model_fields(values.pop('state_fields', []))

            args = values.pop('arguments', [])
            if args:
                args = [graphql_query.Argument(name=k, value=v) for k, v in
                        args.items()]

            query = graphql_query.Query(
                name=convert_model_to_query_name(values['state_model_name']),
                arguments=args,
                fields=fields
            )
            operation = graphql_query.Operation(
                type="query",
                queries=[query]
            )
            values['query_string'] = operation.render()

        return values

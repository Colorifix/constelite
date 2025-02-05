import graphene
from constelite.utils import all_subclasses, resolve_forward_ref
from constelite.store.queries import PropertyQuery
from constelite.models import Relationship, StateModel, ref
import pydantic.v1 as pydantic
from typing import Optional, Any, Dict, Type, ForwardRef
from aiodataloader import DataLoader
import asyncio
from constelite.graphql.field_type_map import (
    convert_to_graphql_type,
    ConversionError
)
from constelite.graphql.utils import convert_model_to_query_name


def get_dataloader(store, cls):
    """
    Creates a dataloader for a particular store and model class.
    The dataloader function takes a list of UIDs and runs store.get for each
    Args:
        store:
        cls:

    Returns:

    """
    async def loading_function(uids):
        refs = [
            ref(uid=uid, store=store, model=cls) for uid in uids
        ]
        return await store.bulk_get(refs)

    return DataLoader(loading_function)


class StoreModelGQL(graphene.ObjectType):
    uid = graphene.String()
    name = graphene.String()


class RecordGQL(graphene.ObjectType):
    """
    Equivalent of the Constelite Ref Record.
    """
    uid = graphene.String()
    store = graphene.Field(StoreModelGQL)


class GrapheneModelAttributes:
    """
    Converts a Constelite model class into a Graphene model.
    Also collects the arguments for resolver related to this model.
    """

    def __init__(self, schema_maker, constelite_model):
        self.schema_maker = schema_maker
        self.constelite_model: Type[pydantic.BaseModel] = constelite_model
        self.graphene_model: Optional[Type[graphene.ObjectType]] = None
        self.ref_attributes: Optional[Dict[str, Any]] = {}
        self.state_attributes: Optional[Dict[str, Any]] = {}
        self.resolver_arguments: Optional[Dict[str, Any]] = {}
        self.related_class_resolvers: Optional[Dict[str, Any]] = {}

    @property
    def cls_name(self):
        return self.constelite_model.__name__

    def get_resolver(self):
        """
        Get a function for the top-level query. Returns a list of items and
        can filter by any of the fields.
        Args:
            cls:

        Returns:

        """
        async def resolver(parent, info, **kwargs):
            context = info.context
            store = context.get('store')
            dataloader = context.get('dataloaders').get(
                self.cls_name
            )

            # If searching by UID or GUID, we can use the data loaders
            if 'uid' in kwargs:
                uids = [kwargs['uid']]
            elif 'uids' in kwargs:
                uids = kwargs['uids']
            elif 'guid' in kwargs:
                uids = [
                    await store._guid_map.get_uid(guid=kwargs['guid'],
                                                  store=store)
                ]
            elif 'guids' in kwargs:
                tasks = []
                async with asyncio.TaskGroup() as tg:
                    for guid in kwargs['guids']:
                        tasks.append(
                            tg.create_task(
                                store._guid_map.get_uid(guid=guid, store=store)
                            )
                        )
                uids = [task.result() for task in tasks]
            else:
                # It not given UIDs or GUIDs, we run a store query
                refs = await store.query(
                    query=PropertyQuery(**kwargs),
                    include_states=True,
                    model_name=self.cls_name
                )
                # prime the dataloader with the results
                for r in refs:
                    dataloader.prime(r.uid, r)
                uids = [r.uid for r in refs]

            return await dataloader.load_many(uids)

        return resolver

    def get_state_resolver(self):
        async def resolve_state(parent, info):

            state = parent.state
            if state is None:
                context = info.context
                dataloader = context.get('dataloaders').get(
                    self.cls_name
                )
                loaded_ref = await dataloader.load(parent.uid)
                state = loaded_ref.state

            return state

        return resolve_state

    @staticmethod
    def get_graphene_model_name(cls, state=False):
        name = cls.__name__ + 'GQL'
        if state:
            name += 'state'
        return name

    def graphene_placeholder(self, graphene_model_name):
        """
        Returns a model that we made earlier. Called when the schema is created
        after we have made all the Graphene models.
        Args:
            graphene_model_name:

        Returns:

        """
        graphene_model = next(
            (m.graphene_model for m in
             self.schema_maker.graphene_models.values()
             if m.graphene_model.__name__ == graphene_model_name), None)
        if graphene_model is None:
            raise ValueError(f"Could not find model for {graphene_model_name}")
        return graphene_model

    def convert_relationship(self, field_name, field_type):
        """
        Converts a Constelite relationships to a graphene.List of the related
        Graphene model.
        Args:
            field_name:
            field_type:

        Returns:

        """
        related_model = field_type.model()
        if isinstance(related_model, ForwardRef):
            related_model = resolve_forward_ref(related_model, StateModel)
        # Need to convert to the graphene version
        # To prevent circular references,
        # we just use the name and resolve the placeholders later.
        graphene_model_name = self.get_graphene_model_name(related_model)
        if related_model in self.schema_maker._in_progress:
            # Use a placeholder function
            def related():
                return self.graphene_placeholder(graphene_model_name)
        else:
            related = self.schema_maker.get_graphene_model(
                related_model).graphene_model

        self.state_attributes[field_name] = graphene.List(related)
        # The resolver argument is the related model UID, i.e. a string
        self.resolver_arguments[field_name] = graphene.String()

    def convert_type(self, field_name, field):
        """
        Convert field types into the equivalent GraphQL type
        """

        field_type = field.type_

        if isinstance(field_type, type) and \
                issubclass(field_type, Relationship):
            self.convert_relationship(
                field_name,
                field_type
            )
        else:
            try:
                graphql_type = convert_to_graphql_type(field.annotation)
                self.state_attributes[field_name] = graphql_type
                self.resolver_arguments[field_name] = graphql_type
            except ConversionError as e:
                # If the field type isn't converted to a GraphQL type,
                # exclude and warn
                print(f"GraphQL type conversion error: {e}")

    def convert_field_types(self, cls):
        """
        Convert types that aren't defined in GraphQL to the best equivalent.
        Also collects the resolver arguments.
        Any related models will be created too
        (if they haven't been created already)
        Args:
            cls:

        Returns:

        """
        # Add the attributes of the Ref model.
        self.ref_attributes = dict(
            model_name=graphene.String(),
            guid=graphene.String(),
            record=graphene.Field(RecordGQL),
            state_model_name=graphene.String(),
            resolve_state=self.get_state_resolver()
        )
        self.state_attributes = dict()
        self.resolver_arguments = dict(
            guid=graphene.String(),
            uid=graphene.String(),
            uids=graphene.List(graphene.String),
            guids=graphene.List(graphene.String)
        )
        # Then add all attributes of this StateModel
        for field_name, field in cls.__fields__.items():
            self.convert_type(field_name, field)

    def create_graphene_model(self):
        """
        Make a version of a StateModel that includes the Ref details.
        Can convert back from this after querying.
        Args:

        Returns:

        """
        self.convert_field_types(self.constelite_model)

        state_model = type(
            self.get_graphene_model_name(self.constelite_model, state=True),
            (graphene.ObjectType,),
            self.state_attributes
        )

        self.ref_attributes['state'] = graphene.Field(state_model)

        ref_model = type(
            self.get_graphene_model_name(self.constelite_model),
            (graphene.ObjectType,),
            self.ref_attributes | self.related_class_resolvers
        )
        self.graphene_model = ref_model

    def get_top_level_query_attributes(self):
        """
        Fetches the query field and the resolver argument to add to the
        main Query model
        Returns:

        """
        query_name = convert_model_to_query_name(self.constelite_model)
        return {
            query_name: graphene.List(
                self.graphene_model,
                **self.resolver_arguments
            ),
            f"resolve_{query_name}": self.get_resolver()
        }


class GraphQLSchemaManager:

    def __init__(self):
        self.graphene_models = {}
        self._in_progress = set()
        self.schema = None

    def get_graphene_model(self, cls: StateModel) -> GrapheneModelAttributes:
        """
        Gets (and also creates if needed) the Graphene equivalent of the input
        class.

        Args:
            cls: StateModel

        Returns:

        """
        if cls not in self.graphene_models:
            # Need to track the models in progress so we can catch circular
            # relationships
            self._in_progress.add(cls)

            graphene_model = GrapheneModelAttributes(
                schema_maker=self,
                constelite_model=cls,
            )
            graphene_model.create_graphene_model()

            self.graphene_models[cls] = graphene_model
            self._in_progress.remove(cls)

        return self.graphene_models[cls]

    def _update_query_attributes(self, cls: StateModel) -> Dict[str, Any]:
        graphene_model = self.get_graphene_model(cls)
        return graphene_model.get_top_level_query_attributes()

    def create_graphql_schema(self, root_cls=StateModel) -> graphene.Schema:
        """
        Creates a GraphQL schema containing all subclasses of the given
        root_cls.

        Args:
            root_cls:

        Returns:

        """
        # First collect all fields and resolvers that we need to add to the
        # main query class. This will also create all the Graphene models
        # that are equivalent to the StateModels.
        query_attributes = dict()
        query_attributes.update(self._update_query_attributes(root_cls))
        for cls in all_subclasses(root_cls):
            query_attributes.update(self._update_query_attributes(cls))

        # Create the Query class containing all the query fields and resolver
        # functions.
        Query = type(
            "Query",
            (graphene.ObjectType,),
            query_attributes
        )

        # And then create the schema
        schema = graphene.Schema(query=Query, auto_camelcase=False)

        return schema

    def get_schema(self):
        if self.schema is None:
            self.schema = self.create_graphql_schema()
        return self.schema

    def get_dataloaders(self, store):
        """
        Get a set of dataloaders for a store.
        Should be called at the start of a GraphQL query execution, so we
        start with a fresh set of dataloaders.
        Creates one dataloader per StateModel subclass.
        Args:
            store:

        Returns:

        """
        dataloaders = {}
        for cls in self.graphene_models.keys():
            dataloaders[cls.__name__] = get_dataloader(
                store=store, cls=cls)
        return dataloaders


if __name__ == '__main__':
    from constelite.models import StateModel
    # Need to import all the models
    # Would run this part in colorifix_alpha
    from colorifix_alpha.models import *
    schema = GraphQLSchemaManager().create_graphql_schema()
    # This prints out the graphql schema
    # Could use with other tools if we wanted
    with open('graphql_schema.txt', 'w') as f:
        print(schema, file=f)

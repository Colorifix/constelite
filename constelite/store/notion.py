from typing import Type, Dict, Optional, List, ClassVar, get_args

from uuid import UUID

from pydantic.v1 import BaseModel, Field
import more_itertools

from python_notion_api import NotionAPI, NotionDatabase, NotionPage
from python_notion_api.models.objects import ParentObject
from python_notion_api.models.values import PropertyValue

import python_notion_api.models.filters as filters
from python_notion_api.models.filters import and_filter, or_filter

from python_notion_api.models.values import (
    RelationPropertyValue,
    TitlePropertyValue,
    RichTextPropertyValue,
    SelectPropertyValue,
    RollupPropertyValue,
    StatusPropertyValue,
)

from python_notion_api.models.iterators import PropertyItemIterator

from constelite.models import (
    StateModel,
    StaticTypes,
    Dynamic,
    UID,
    RelInspector,
    Relationship
)

from constelite.store import BaseStore, Query, PropertyQuery


filter_map = {
    RelationPropertyValue: lambda p, v: (
        filters.RelationFilter(
            property=p,
            contains=v
        )
    ),
    TitlePropertyValue: lambda p, v: (
        filters.RichTextFilter(
            property=p,
            equals=v
        )
    ),
    RichTextPropertyValue: lambda p, v: (
        filters.RichTextFilter(
            property=p,
            equals=v
        )
    ),
    SelectPropertyValue: lambda p, v: (
        filters.SelectFilter(
            property=p,
            equals=v
        )
    ),
    RollupPropertyValue: lambda p, v: (
        filters.RollupFilter(
            property=p,
            any=filters.RelationFilter(
                contains=v
            )
        )
    ),
    StatusPropertyValue: lambda p, v: (
        filters.StatusFilter(
            property=p,
            equals=v
        )
    )
}


class ModelHandler(BaseModel):
    store: ClassVar[Optional["NotionStore"]] = Field(exclude=True)

    class Config:
        arbitrary_types_allowed = True
        allow_population_by_field_name = True

    def _to_prop_dict(self) -> Dict[str, PropertyValue]:
        return {
            field.alias: getattr(self, field_name)
            for field_name, field in self.__fields__.items()
            if getattr(self, field_name) is not None
        }

    @staticmethod
    def to_notion_rel(field_value: Relationship):
        if field_value is not None:
            return [
                ref.uid for ref in field_value
            ]
        else:
            return None

    def to_state_rel(
        self,
        value: RelationPropertyValue,
        state_model_name: str
    ):
        values = value.value
        rel_value = None
        if len(values) > 0:
            # Rollup relations can be lists of lists and can contain duplicates
            # Need to flatten lists and de-duplicate
            # This will do no harm if already flat and unique
            values = set(more_itertools.collapse(values))
            rel_value = [
                self.store.generate_ref(
                    uid=uid,
                    state_model_name=state_model_name
                )
                for uid in values
            ]
        return rel_value

    def apply_template(self, page_id):
        page = self.store.api.get_page(page_id=page_id)
        template_id = getattr(self, "_template_id", None)
        if template_id is not None:
            template_page = self.store.api.get_page(page_id=template_id)
            if page is not None:
                breakpoint()
                blocks = template_page.get_blocks()
                block_list = list(blocks)

                page.add_blocks(
                    blocks=block_list
                )

    def create_page(self) -> UID:
        properties = self._to_prop_dict()

        request = NotionDatabase.CreatePageRequest(
            parent=ParentObject(
                type="database_id",
                database_id=self._database_id
            ),
            properties=properties
        )

        data = request.json(by_alias=True, exclude_unset=True)

        new_page = self.store.api._post("pages", data=data)

        # Disabled for now as Notion API does not support creation of
        # linked databse blocks :(
        # self.apply_template(new_page.page_id)

        return new_page.page_id

    def update_page(self, uid: UID):
        properties = self._to_prop_dict()

        request = NotionPage.PatchRequest(
            properties=properties
        )

        data = request.json(by_alias=True, exclude_unset=True)

        self.store.api._patch(
            f"pages/{uid}",
            data=data
        )

    @staticmethod
    def get_field_constelite_name(field):
        extra_info = field.field_info.extra
        constelite_name = None
        if 'json_schema_extra' in extra_info:
            constelite_name = extra_info[
                    'json_schema_extra'
                ].get('constelite_name', None)
        return constelite_name

    @classmethod
    def from_page(cls, uid: UID, page: Optional[NotionPage] = None) -> StateModel:
        if page is None:
            page = cls.store.api.get_page(
                page_id=uid.replace('-', '')
            )

        properties = {}

        for field_name, field in cls.__fields__.items():
            alias = field.alias
            safety_off = field.field_info.extra.get('safety_off', True)
            try:
                property_value = page.get(alias, safety_off=safety_off)
            except ValueError as e:
                raise ValueError(
                    "Failed to get page property from"
                    f" {cls.__name__}.{field_name}"
                    f" with alias '{alias}'"
                ) from e
            if isinstance(property_value, PropertyItemIterator):
                if property_value.property_type == "relation":
                    property_value = RelationPropertyValue(
                        init=property_value.value
                    )
                elif property_value.property_type == "rollup":
                    property_value = RollupPropertyValue(
                        init=property_value.value
                    )
            properties[alias] = property_value
        handler = cls(**properties)

        return handler

    def convert_to_state(self, state_type: Type[StateModel],
                         **props):
        """
        Converts NotionHandler object to constelite state using
        conversion rules.
        You can override the conversion rules with the custom values
        provided in `props`.

        Args:
            state_type:
            props:

        Returns:

        """
        for field_name, field in self.__fields__.items():
            field_type = field.type_
            constelite_name = self.get_field_constelite_name(field)
            if constelite_name not in props:
                if constelite_name is not None:
                    value = getattr(self, field_name)
                    if (
                            (field_type == RelationPropertyValue)
                            or
                            (field_type == RollupPropertyValue and
                             value.init[0].property_type == 'relation')
                    ):
                        props[constelite_name] = self.to_state_rel(
                            value=value,
                            state_model_name=state_type.__fields__[
                                constelite_name
                            ].type_.model.__name__
                        )
                    else:
                        props[constelite_name] = value.value
        return state_type(**props)

    @classmethod
    def from_values(cls, state=None, **values):
        props = {}
        for field_name, field in cls.__fields__.items():
            field_type = field.type_
            if field_name in values:
                value = values[field_name]
            else:
                constelite_name = cls.get_field_constelite_name(field)
                if (
                    constelite_name is not None
                    and state is not None
                ):
                    value = getattr(state, constelite_name)
                    if field_type == RelationPropertyValue:
                        value = cls.to_notion_rel(value)
                else:
                    continue
            if value is None:
                props[field_name] = None
            else:
                props[field_name] = field.type_(init=value)

        return cls(**props)

    @classmethod
    def notion_filter_from_property_query(cls, query: PropertyQuery):
        filters = []
        for prop_name, value in query.property_values.items():
            field = cls.__fields__.get(prop_name, None)
            if field is not None:
                filter_factory = filter_map.get(field.type_, None)
                if filter_factory is None:
                    raise ValueError(
                        f"Don't know how to filter by {field.type_}"
                    )
                if isinstance(value, list):
                    new_filter = or_filter(
                        filters=[
                            filter_factory(field.alias, item)
                            for item in value
                        ]
                    )
                else:
                    new_filter = filter_factory(
                        field.alias,
                        value
                    )
                filters.append(new_filter)
        if len(filters) > 1:
            # Only add more nesting if needed. Notion limits to 2 levels.
            return and_filter(filters=filters)
        elif len(filters) == 1:
            return filters[0]
        else:
            return None


class NotionStore(BaseStore):
    """
    Notion store implementation.
    """
    _allowed_methods = ["PUT", "GET", "PATCH", "DELETE", "QUERY", "GRAPHQL"]

    access_token: str = Field(exclude=True)

    model_handlers: Optional[Dict[Type[StateModel], Type[ModelHandler]]] = {}
    api: Optional[NotionAPI] = Field(exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data):
        super().__init__(**data)
        self.api = NotionAPI(access_token=self.access_token)

    def get_handler_cls_or_fail(self, model_type: Type[StateModel]):
        handler_cls = self.model_handlers.get(model_type, None)

        if handler_cls is not None:
            handler_cls.store = self
            return handler_cls
        else:
            raise TypeError(
                f"{model_type} is not supported by the {self.name} store"
            )

    def uid_exists(self, uid: UID, model_type: Type[StateModel]) -> bool:
        page = self.api.get_page(page_id=uid)
        return page is not None

    def create_model(
        self,
        model_type: StateModel,
        static_props: Dict[str, StaticTypes],
        dynamic_props: Dict[str, Optional[Dynamic]]
    ) -> UID:
        handler_cls = self.get_handler_cls_or_fail(model_type=model_type)

        handler = handler_cls.from_state(
            state=model_type(**(static_props | dynamic_props))
        )

        uid = handler.create_page()

        return uid

    def delete_model(
            self,
            model_type: Type[StateModel],
            uid: UID) -> None:

        page = self.api.get_page(page_id=uid)
        page.alive = False

    def overwrite_static_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, StaticTypes]
    ) -> None:
        handler_cls = self.get_handler_cls_or_fail(model_type=model_type)

        handler = handler_cls.from_state(
            state=model_type(**props)
        )

        handler.update_page(uid=uid)

    def overwrite_dynamic_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, Optional[Dynamic]]) -> None:

        handler_cls = self.get_handler_cls_or_fail(model_type=model_type)

        handler = handler_cls.from_state(
            state=model_type(**props)
        )

        handler.update_page(uid=uid)

    def extend_dynamic_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, Optional[Dynamic]]
    ) -> None:
        handler_cls = self.get_handler_cls_or_fail(model_type=model_type)

        handler = handler_cls.from_page(uid=uid)

        state = handler.to_state(model_type=model_type)

        for prop_name, prop in props:
            points = getattr(
                state, prop_name
            ).points

            if points is None:
                points = []

            points.extend(prop.points)

            setattr(state, prop_name, points)

        handler = handler.from_state(state)

        handler.update_page(uid=uid)

    def delete_all_relationships(
            self,
            from_uid: UID,
            from_model_type: Type[StateModel],
            rel_from_name: str) -> List[UID]:

        handler_cls = self.get_handler_cls_or_fail(model_type=from_model_type)

        handler = handler_cls.from_page(uid=from_uid)

        state = handler.to_state(model_type=from_model_type)

        refs = getattr(state, rel_from_name, None)

        if refs is None:
            refs = []

        uids = [
            ref.uid for ref in refs
        ]

        handler = handler_cls.from_state(
            state=from_model_type(
                **{rel_from_name: []}
            )
        )

        handler.update_page(uid=from_uid)

        return uids

    def create_relationships(
            self,
            from_uid: UID,
            from_model_type: Type[StateModel],
            inspector: RelInspector) -> None:
        handler_cls = self.get_handler_cls_or_fail(model_type=from_model_type)

        handler = handler_cls.from_page(uid=from_uid)

        state = handler.to_state(model_type=from_model_type)

        refs = getattr(state, inspector.from_field_name)

        if refs is None:
            refs = []

        refs.extend(inspector.to_refs)

        handler = handler_cls.from_state(
            from_model_type(
                **{inspector.from_field_name: refs}
            )
        )

        handler.update_page(uid=from_uid)

    def get_state_by_uid(
            self,
            uid: UID,
            model_type: Type[StateModel]
    ) -> StateModel:
        handler_cls = self.get_handler_cls_or_fail(model_type=model_type)

        handler = handler_cls.from_page(uid=uid)

        return handler.to_state(model_type=model_type)

    def execute_query(
            self,
            query: Optional[Query],
            model_type: Type[StateModel],
            include_states: bool
    ) -> UID:
        handler_cls = self.get_handler_cls_or_fail(model_type=model_type)
        database = self.api.get_database(
            database_id=handler_cls._database_id,
        )
        if query is None:
            # Fetch all results
            pages = database.query()
        elif isinstance(query, PropertyQuery):
            notion_filter = handler_cls.notion_filter_from_property_query(
                query=query
            )
            pages = database.query(
                filters=notion_filter
            )
        else:
            raise ValueError("Unsupported query type")

        uids = {}

        if include_states is True:
            for page in pages:
                handler = handler_cls.from_page(
                    uid=page.page_id,
                    page=page
                )
                state = handler.to_state(model_type=model_type)
                uids[str(UUID(page.page_id))] = state
        else:
            uids = {
                str(UUID(page.page_id)): None for page in pages
            }

        return uids

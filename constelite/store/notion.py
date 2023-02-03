from typing import Type, Dict, Optional, List, ClassVar

from pydantic import BaseModel, Field

from python_notion_api import NotionAPI, NotionDatabase, NotionPage
from python_notion_api.models.objects import ParentObject
from python_notion_api.models.values import PropertyValue

import python_notion_api.models.filters as filters
from python_notion_api.models.filters import and_filter, or_filter

import python_notion_api.models.values as values

from python_notion_api.models.iterators import PropertyItemIterator

from constelite.models import (
    StateModel,
    StaticTypes,
    Dynamic,
    UID,
    RelInspector
)

from constelite.store import BaseStore, Query, PropertyQuery


filter_map = {
    values.RelationPropertyValue: lambda p, v: (
        filters.RelationFilter(
            property=p,
            contains=v
        )
    ),
    values.TitlePropertyValue: lambda p, v: (
        filters.RichTextFilter(
            property=p,
            contains=v
        )
    ),
    values.RichTextPropertyValue: lambda p, v: (
        filters.RichTextFilter(
            property=p,
            contains=v
        )
    ),
    values.SelectPropertyValue: lambda p, v: (
        filters.SelectFilter(
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

    @classmethod
    def from_page(cls, uid: UID, page: Optional[NotionPage] = None) -> StateModel:
        if page is None:
            page = cls.store.api.get_page(page_id=uid)

        properties = {}

        for field_name, field in cls.__fields__.items():
            alias = field.alias
            property_value = page.get(alias, cache=True, safety_off=True)
            if isinstance(property_value, PropertyItemIterator):
                if property_value.property_type == "relation":
                    property_value = values.RelationPropertyValue(
                        init=property_value.value
                    )
                elif property_value.property_type == "rollup":
                    property_value = values.RollupPropertyValue(
                        init=property_value.value
                    )
            properties[alias] = property_value
        handler = cls(**properties)

        return handler

    @classmethod
    def from_values(cls, **values):
        props = {
            key: cls.__fields__[key].type_(init=value)
            for key, value in values.items()
            if value is not None
        }

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
        return and_filter(filters=filters)


class NotionStore(BaseStore):
    _allowed_methods = ["PUT", "GET", "PATCH", "DELETE", "QUERY"]
    model_handlers: Dict[Type[StateModel], Type[ModelHandler]] = {}
    access_token: str = Field(exclude=True)
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
            query: Query,
            model_type: Type[StateModel],
            include_states: bool
    ) -> UID:
        # breakpoint()
        handler_cls = self.get_handler_cls_or_fail(model_type=model_type)
        if isinstance(query, PropertyQuery):
            notion_filter = handler_cls.notion_filter_from_property_query(
                query=query
            )
            database = self.api.get_database(
                database_id=handler_cls._database_id,
            )
            pages = database.query(
                filters=notion_filter
            )

            uids = {}

            if include_states is True:
                for page in pages:
                    handler = handler_cls.from_page(
                        uid=page.page_id,
                        page=page
                    )
                    state = handler.to_state(model_type=model_type)
                    uids[page.page_id] = state
            else:
                uids = {page.page_id: None for page in pages}

            return uids
        else:
            raise ValueError("Unsupported query type")

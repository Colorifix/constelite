import asyncio
from typing import Type, Dict, Optional, List, ClassVar, ForwardRef

from uuid import UUID

from pydantic.v1 import BaseModel, Field
import more_itertools

from python_notion_api.async_api import AsyncNotionAPI, NotionDatabase, NotionPage
from python_notion_api.async_api.iterators import AsyncPropertyItemIterator

from python_notion_api.models.objects import ParentObject
import python_notion_api.models.filters as filters
from python_notion_api.models.filters import and_filter, or_filter

from python_notion_api.models.values import (
    PropertyValue,
    RelationPropertyValue,
    TitlePropertyValue,
    RichTextPropertyValue,
    SelectPropertyValue,
    RollupPropertyValue,
    StatusPropertyValue,
)



from constelite.models import (
    StateModel,
    StaticTypes,
    Dynamic,
    UID,
    RelInspector,
    Relationship,
    Ref,
    StateInspector,
    get_auto_resolve_model
)

from constelite.store import  Query, PropertyQuery
from constelite.store.base_async import AsyncBaseStore


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

    async def to_state_rel(
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
                await self.store.generate_ref(
                    uid=uid,
                    state_model_name=state_model_name
                )
                for uid in values
            ]
        return rel_value


    async def create_page(self) -> UID:
        properties = self._to_prop_dict()

        request = NotionDatabase.CreatePageRequest(
            parent=ParentObject(
                type="database_id",
                database_id=self._database_id
            ),
            properties=properties
        )

        data = request.json(by_alias=True, exclude_unset=True)

        new_page = await self.store.api._post("pages", data=data)

        return new_page.page_id

    async def update_page(self, uid: UID):
        properties = self._to_prop_dict()

        request = NotionPage.PatchRequest(
            properties=properties
        )

        data = request.json(by_alias=True, exclude_unset=True)

        await self.store.api._patch(
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
    async def get_property_value(cls, page: NotionPage, field_name: str) -> PropertyValue:
        field = cls.__fields__.get(field_name, None)

        if field is None:
            raise ValueError(f"Invalid field '{cls.__name__}.{field_name}'")

        alias = field.alias
        safety_off = field.field_info.extra.get('safety_off', True)
        try:
            property_value = await page.get(alias, safety_off=safety_off, raw=True)
        except ValueError as e:
            raise ValueError(
                "Failed to get page property from"
                f" {cls.__name__}.{field_name}"
                f" with alias '{alias}'"
            ) from e
        if isinstance(property_value, AsyncPropertyItemIterator):
            if property_value.property_type == "relation":
                init_value = await property_value.get_value()
                property_value = RelationPropertyValue(
                    init=init_value
                )
            elif property_value.property_type == "rollup":
                init_value = await property_value.get_value()
                property_value = RollupPropertyValue(
                    init=init_value
                )
        return property_value
    @classmethod
    async def from_page(cls, uid: UID) -> "ModelHandler":
        page = NotionPage(api=cls.store.api, page_id=uid)
        
        await page.reload()
        
        tasks = {}
        async with asyncio.TaskGroup() as tg:
            for field_name in cls.__fields__:
                tasks[field_name] = tg.create_task(
                    cls.get_property_value(
                        page=page,
                        field_name=field_name
                    )
                )
        properties = {key: task.result() for key, task in tasks.items()}
        handler = cls(**properties)

        return handler

    async def convert_to_state(self, state_type: Type[StateModel],
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
                        field_model = state_type.__fields__[
                            constelite_name
                        ].type_.model

                        field_model_name = None

                        if isinstance(field_model, ForwardRef):
                            field_model_name = field_model.__forward_arg__
                        else:
                            field_model_name = field_model.__name__

                        props[constelite_name] = await self.to_state_rel(
                            value=value,
                            state_model_name=field_model_name
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


class NotionStore(AsyncBaseStore):
    _allowed_methods = ["PUT", "GET", "PATCH", "DELETE", "QUERY", "GRAPHQL"]

    access_token: str = Field(exclude=True)

    model_handlers: Optional[Dict[Type[StateModel], Type[ModelHandler]]] = {}
    api: Optional[AsyncNotionAPI] = Field(exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data):
        super().__init__(**data)
        self.api = AsyncNotionAPI(access_token=self.access_token)

    def get_handler_cls_or_fail(self, model_type: Type[StateModel]):
        handler_cls = self.model_handlers.get(model_type, None)

        if handler_cls is not None:
            handler_cls.store = self
            return handler_cls
        else:
            raise TypeError(
                f"{model_type} is not supported by the {self.name} store"
            )

    async def uid_exists(self, uid: UID, model_type: Type[StateModel]) -> bool:
        # Since Notion operations are slow, we will ignore checks for existance
        # and deal wit them somewhere else in code.
        return True

    async def create_model(
        self,
        model_type: StateModel,
        static_props: Dict[str, StaticTypes],
        dynamic_props: Dict[str, Optional[Dynamic]]
    ) -> UID:
        handler_cls = self.get_handler_cls_or_fail(model_type=model_type)

        handler = handler_cls.from_state(
            state=model_type(**(static_props | dynamic_props))
        )

        uid = await handler.create_page()

        return uid

    async def delete_model(
            self,
            model_type: Type[StateModel],
            uid: UID) -> None:

        page = NotionPage(api=self.api, page_id=uid)
        await page.archive()

    async def overwrite_static_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, StaticTypes]
    ) -> None:
        handler_cls = self.get_handler_cls_or_fail(model_type=model_type)

        handler = handler_cls.from_state(
            state=model_type(**props)
        )

        await handler.update_page(uid=uid)

    async def overwrite_dynamic_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, Optional[Dynamic]]) -> None:

        handler_cls = self.get_handler_cls_or_fail(model_type=model_type)

        handler = handler_cls.from_state(
            state=model_type(**props)
        )

        await handler.update_page(uid=uid)

    async def extend_dynamic_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, Optional[Dynamic]]
    ) -> None:
        handler_cls = self.get_handler_cls_or_fail(model_type=model_type)

        handler = await handler_cls.from_page(uid=uid)

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

        await handler.update_page(uid=uid)

    async def delete_all_relationships(
            self,
            from_uid: UID,
            from_model_type: Type[StateModel],
            rel_from_name: str) -> List[UID]:

        handler_cls = self.get_handler_cls_or_fail(model_type=from_model_type)

        handler = await handler_cls.from_page(uid=from_uid)

        state = await handler.to_state(model_type=from_model_type)

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

        await handler.update_page(uid=from_uid)

        return uids

    async def create_relationships(
            self,
            from_uid: UID,
            from_model_type: Type[StateModel],
            inspector: RelInspector) -> None:
        handler_cls = self.get_handler_cls_or_fail(model_type=from_model_type)

        handler = await handler_cls.from_page(uid=from_uid)

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

        await handler.update_page(uid=from_uid)

    async def get_state_by_uid(
            self,
            uid: UID,
            model_type: Type[StateModel]
    ) -> StateModel:
        handler_cls = self.get_handler_cls_or_fail(model_type=model_type)

        handler = await handler_cls.from_page(uid=uid)

        return await handler.to_state(model_type=model_type)

    async def execute_query(
            self,
            query: Optional[Query],
            model_type: Type[StateModel],
            include_states: bool
    ) -> UID:
        handler_cls = self.get_handler_cls_or_fail(model_type=model_type)
        database = await self.api.get_database(
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

        if include_states is True:
            tasks = {}

            async def get_state_wrapper(page_id):
                handler = await handler_cls.from_page(uid=page_id)
                return await handler.to_state(model_type=model_type)

            async with asyncio.TaskGroup() as tg:
                async for page in pages:
                    tasks[page.page_id] = tg.create_task(
                        get_state_wrapper(page_id=page.page_id)
                    )

            uids = {
                str(UUID(page_id)): task.result()
                for page_id, task in tasks.items()
            }
        else:
            uids = {
                str(UUID(page.page_id)): None async for page in pages
            }

        return uids

    async def write_relations(self, rel, method) -> List[Ref]:
        refs = []
        for to_ref in rel.to_refs:
            if to_ref.state is None:
                await self._validate_ref_uid(to_ref)
                refs.append(to_ref)
            else:
                processed_to_ref = await method(to_ref)
                refs.append(processed_to_ref)
        return refs

    async def update_page_from_state(self, state: StateModel, uid: UID):
        handler_cls = self.get_handler_cls_or_fail(
            model_type=state.__class__
        )

        handler = handler_cls.from_state(
            state=state
        )

        await handler.update_page(uid=uid)

    async def create_page_from_state(self, state: StateModel):
        handler_cls = self.get_handler_cls_or_fail(
            model_type=state.__class__
        )

        handler = handler_cls.from_state(
            state=state
        )

        return await handler.create_page()

    async def put(self, ref: Ref) -> Ref:
        self._validate_method('PUT')
        ref = await self._fetch_record_by_guid(ref)

        inspector = StateInspector.from_state(ref.state)

        tasks = {}

        async with asyncio.TaskGroup() as tg:
            for field_name, rel in (
                inspector.associations | inspector.aggregations
                | inspector.compositions
            ).items():
                tasks[field_name] = tg.create_task(
                    self.write_relations(rel, self.put)
                )

        new_rels = {
            field_name: task.result()
            for field_name, task in tasks.items()
        }

        state_dict = ref.state.dict()
        state_dict.update(new_rels)

        new_state = inspector.model_type(
            **state_dict
        )

        uid = None

        if ref.record is None:
            uid = await self.create_page_from_state(new_state)
        else:
            uid = ref.uid
            ref = await self._validate_ref_full(ref)

            await self.update_page_from_state(
                state=new_state,
                uid=ref.uid
            )
            # To comply with constelite we also need to delete all orphan compositions
            # But we don't do it here for now

        return await self.generate_ref(
            uid=uid,
            state_model_name=ref.state_model_name,
            guid=ref.guid
        )
    
    async def patch(self, ref: Ref) -> Ref:
        self._validate_method('PATCH')
        
        ref = await self._validate_ref_full(ref=ref)
        # Danger! We don't know if ref exists in the store at this point.

        if ref.state is None:
            return ref

        inspector = StateInspector.from_state(ref.state)

        current_state = await self.get_state_by_uid(
            uid=ref.uid,
            model_type=inspector.model_type
        )

        tasks = {}

        async def comp_agg_write_rels_wrapper(rel):
            new_rel = await self.write_relations(rel, self.patch)
            current_rels = getattr(current_state, field_name, [])
            
            for current_rel in current_rels:
                if current_rel.uid not in [r.uid for r in new_rel]:
                    new_rel.append(current_rel)
            return new_rel
    
        async with asyncio.TaskGroup() as tg:
            for field_name, rel in inspector.associations.items():
                tasks[field_name] = tg.create_task(
                    self.write_relations(rel, self.patch)
                )

            for field_name, rel in (
                    inspector.compositions | inspector.aggregations).items():
                tasks[field_name] = tg.create_task(
                    comp_agg_write_rels_wrapper(rel)
                )
        
        new_rels = {
            field_name: task.result()
            for field_name, task in tasks.items()
        }

        state_dict = ref.state.dict()
        state_dict.update(new_rels)

        new_state = inspector.model_type(
            **state_dict
        )

        await self.update_page_from_state(
            state=new_state,
            uid=ref.uid
        )

        return await self.generate_ref(
            uid=ref.uid,
            state_model_name=ref.state_model_name,
            guid=ref.guid
        )

    async def delete(self, ref: Ref) -> None:
        self._validate_method('DELETE')

        ref = await self._validate_ref_full(ref=ref)

        model_type = get_auto_resolve_model(
            model_name=ref.state_model_name
        )

        if model_type is None:
            raise ValueError(
                "Unknown state model name '{ref.state_model_name}'"
            )

        state = await self.get_state_by_uid(
            uid=ref.uid,
            model_type=model_type
        )

        inspector = StateInspector.from_state(state)

        for field_name, rel in inspector.compositions.items():
            for to_ref in rel.to_refs:
                async with asyncio.TaskGroup() as tg:
                    tg.create_task(
                        self.delete_model(
                            uid=to_ref.uid,
                            model_type=rel.to_model
                        )
                    )

        await self.delete_uid_record(uid=ref.uid)

        await self.delete_model(
            uid=ref.uid,
            model_type=model_type
        )
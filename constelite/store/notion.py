from typing import Type, Dict, Optional, List, ClassVar

from pydantic import BaseModel, Field

from python_notion_api import NotionAPI, NotionDatabase, NotionPage
from python_notion_api.models.objects import ParentObject
from python_notion_api.models.values import PropertyValue

from constelite.models import (
    StateModel,
    StaticTypes,
    Dynamic,
    UID,
    RelInspector
)

from constelite.store import BaseStore


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
    def from_uid(cls, uid: UID) -> StateModel:
        page = cls.store.api.get_page(page_id=uid)

        handler = cls(**page.properties)

        return handler

    @classmethod
    def from_values(cls, **values):
        props = {
            key: cls.__fields__[key].type_(init=value)
            for key, value in values.items()
            if value is not None
        }

        return cls(**props)


class NotionStore(BaseStore):
    _allowed_methods = ["PUT", "GET", "PATCH", "DELETE"]
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

        handler = handler_cls.from_uid(uid=uid)

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

        handler = handler_cls.from_uid(uid=from_uid)

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

        handler = handler_cls.from_uid(uid=from_uid)

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

        handler = handler_cls.from_uid(uid=uid)

        return handler.to_state(model_type=model_type)

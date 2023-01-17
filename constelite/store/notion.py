from typing import Type, Dict, Optional, List

from pydantic import BaseModel, Field

from python_notion_api import NotionAPI

from constelite.models import (
    StateModel,
    StaticTypes,
    Dynamic,
    UID,
    RelInspector
)

from constelite.store import BaseStore


class ModelHandler(BaseModel):
    api: Optional[NotionAPI] = Field(exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def create_page(self) -> UID:
        db = self.api.get_database(database_id=self._database_uid)
        page = db.create_page(
            properties=self.dict(by_alias=True)
        )
        return page.page_id

    def update_page(self, uid: UID):
        page = self.api.get_page(page_id=uid)

        props = self.dict(by_alias=True, exclude_unset=True)

        for prop_name, value in props.items():
            page.set(prop_name, value)

    @classmethod
    def from_uid(cls, uid: UID) -> StateModel:
        page = cls.api.get_page(page_id=uid)

        handler = cls(**page.properties)

        return handler


class NotionStore(BaseStore):
    _model_handlers: Dict[Type[StateModel], Type[ModelHandler]]
    access_token: str = Field(exclude=True)
    api: Optional[NotionAPI] = Field(exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data):
        super().__init__(**data)
        self.api = NotionAPI(access_token=self.access_token)

    def get_handler_cls_or_fail(self, model_type: Type[StateModel]):
        handler_cls = self._model_handlers.get(model_type, None)

        if handler_cls is not None:
            handler_cls.api = self.api
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
            **(static_props | dynamic_props)
        )

        uid = handler.create_page()

        return uid

    def delete_model(
            self,
            model_type: Type[StateModel],
            uid: UID) -> None:
        pass

    def overwrite_static_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, StaticTypes]
    ) -> None:

        handler_cls = self.get_handler_cls_or_fail(model_type=model_type)

        handler = handler_cls.from_state(
            model_type(**props)
        )

        handler.update_page(uid=uid)

    def overwrite_dynamic_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, Optional[Dynamic]]) -> None:

        handler_cls = self.get_handler_cls_or_fail(model_type=model_type)

        handler = handler_cls.from_state(
            model_type(**props)
        )

        handler.update_page(uid=uid)

    def extend_dynamic_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, Optional[Dynamic]]
    ) -> None:
        pass

    def delete_all_relationships(
            self,
            from_uid: UID,
            from_model_type: Type[StateModel],
            rel_from_name: str) -> List[UID]:

        handler_cls = self.get_handler_cls_or_fail(model_type=from_model_type)

        handler = handler_cls.from_uid(uid=from_uid)

        state = handler.to_state(state_model=from_model_type)

        refs = getattr(state, rel_from_name, None)

        if refs is None:
            refs = []

        uids = [
            ref.uid for ref in refs
        ]

        handler = handler_cls.from_state(
            from_model_type(
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

        state = handler.to_state(state_model=from_model_type)

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

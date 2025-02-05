from typing import List, Dict, Optional, Type

from uuid import uuid4

from constelite.models import (
    StateModel, UID, TimePoint, Dynamic,
    StaticTypes, RelInspector
)

from constelite.store.base_async import (
    AsyncBaseStore
)

class UIDKeyStoreBase(AsyncBaseStore):
    """
    Base for the pickle and memcached stores where the objects are
    stored with the uid as the key
    """
    _allowed_methods = ["PUT", "GET", "PATCH", "DELETE"]

    async def create_model(
            self,
            model_type: StateModel,
            static_props: Dict[str, StaticTypes],
            dynamic_props: Dict[str, Optional[Dynamic]]) -> UID:
        model = model_type(
            **(static_props | dynamic_props)
        )
        uid = str(uuid4())
        uid = await self.store(uid=uid, model=model)
        return uid

    async def overwrite_static_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, StaticTypes]) -> None:

        model = await self.get_state_by_uid(
            uid=uid,
            model_type=model_type
        )
        data = model.dict()
        data.update(props)

        new_model = model.__class__(
            **data
        )

        await self.store(uid=uid, model=new_model)

    async def overwrite_dynamic_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, List[TimePoint]]) -> None:
        model = await self.get_state_by_uid(
            uid=uid,
            model_type=model_type
        )
        data = model.dict()
        data.update(props)

        new_model = model.__class__(
            **data
        )
        await self.store(uid=uid, model=new_model)

    async def extend_dynamic_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, Optional[Dynamic]]) -> None:
        model = await self.get_state_by_uid(
            uid=uid,
            model_type=model_type
        )

        for prop_name, prop in props.items():
            point_type = prop._get_point_type()
            points = getattr(
                model,
                prop_name,
                Dynamic[point_type](points=[])
            ).points

            points.extend(prop.points)
            setattr(
                model,
                prop_name,
                Dynamic[point_type](points=points)
            )
        await self.store(uid=uid, model=model)

    async def delete_all_relationships(
            self,
            from_uid: UID,
            from_model_type: Type[StateModel],
            rel_from_name: str,
            ) -> List[UID]:

        model = await self.get_state_by_uid(
            uid=from_uid,
            model_type=from_model_type
        )

        orphan_refs = getattr(model, rel_from_name, [])
        setattr(model, rel_from_name, [])

        await self.store(uid=from_uid, model=model)

        return [orphan_ref.record.uid for orphan_ref in orphan_refs]

    async def create_relationships(
            self,
            from_uid: UID,
            from_model_type: Type[StateModel],
            inspector: RelInspector) -> None:
        from_model = await self.get_state_by_uid(
            uid=from_uid,
            model_type=inspector.to_model
        )

        to_refs = getattr(from_model, inspector.from_field_name, [])
        if to_refs is None:
            to_refs = []

        new_to_refs = (
            inspector.to_refs
            if inspector.to_refs is not None
            else []
        )

        for to_ref in new_to_refs:
            to_uid = to_ref.uid
            to_refs.append(to_ref)
            if inspector.to_field_name is not None:
                to_model = await self.get_state_by_uid(
                    uid=to_uid,
                    model_type=inspector.to_model
                )
                backref_list = getattr(to_model, inspector.to_field_name)
                from_ref = await self.generate_ref(uid=from_uid)
                if backref_list is None:
                    backref_list = [from_ref]
                else:
                    backref_list.append(from_ref)
                setattr(to_model, inspector.to_field_name, backref_list)
                await self.store(uid=to_uid, model=to_model)
        setattr(from_model, inspector.from_field_name, to_refs)
        await self.store(uid=from_uid, model=from_model)
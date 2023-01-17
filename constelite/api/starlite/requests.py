from typing import Optional

from pydantic import BaseModel, validator, root_validator

from constelite.models import StoreModel, Ref, resolve_model


def validate_state(ref: Ref) -> Ref:
    if ref.state is None:
        raise ValueError('Ref state is empty')
    ref = resolve_model(
        values=ref.dict()
    )

    return ref


class RefRequest(BaseModel):
    ref: Ref

    @validator('ref')
    def validate_ref_store(cls, value):
        if value.record is None:
            raise ValueError("Reference has an empy record")
        return value


class PutRequest(BaseModel):
    ref: Ref
    store: Optional[StoreModel]

    _validate_state = validator('ref', allow_reuse=True)(validate_state)

    def __init__(self, **data):
        super().__init__(**data)

    @root_validator
    def root(cls, values):
        store = values.get("store", None)
        ref = values["ref"]

        if store is None and ref.record is None:
            raise ValueError(
                "Unknown store."
                "Either send a reference with a record or supply a store"
            )
        if store is None:
            values['store'] = ref.record.store
        return values


class PatchRequest(RefRequest):
    _validate_state = validator('ref', allow_reuse=True)(validate_state)


class GetRequest(RefRequest):
    pass


class DeleteRequest(RefRequest):
    pass

import os
import pickle

from pydantic import BaseModel

from uuid import uuid4

from constelite import Config, get_config


class Ref(BaseModel):
    ref: str


class Store:
    def store(self, model: "Model") -> Ref:
        pass

    def load(self, ref: Ref) -> "Model":
        pass

    def ref_exists(self, ref: Ref) -> bool:
        pass

    def new_ref(self) -> Ref:
        ref = None
        while ref is None or self.ref_exists(ref):
            ref = Ref(ref=str(uuid4()))

        return ref


class PickleStore(Store):
    def __init__(self, path: str):
        if not os.path.isdir(path):
            os.makedirs(path)
        self.path = path

    def store(self, model: "Model") -> Ref:
        new_ref = self.new_ref()

        path = os.path.join(self.path, new_ref.ref)

        exception = None

        with open(path, 'wb') as f:
            try:
                pickle.dump(model, f)
            except Exception as e:
                exception = e

        if exception is not None:
            os.remove(path)
            raise exception

        return new_ref

    def load(self, ref: Ref) -> "Model":
        if not self.ref_exists(ref):
            raise ValueError(f"Model with reference '{ref}' cannon be found")
        else:
            path = os.path.join(self.path, ref.ref)
            with open(path, 'rb') as f:
                return pickle.load(f)

    def ref_exists(self, ref: Ref) -> bool:
        path = os.path.join(self.path, ref.ref)
        return os.path.exists(path)


class StoreConfig(Config):
    path: str = 'store'


def get_store() -> Store:
    config = get_config(StoreConfig)
    return PickleStore(path=config.path)

from typing import Dict, List
import os
import toml

from pydantic.v1 import BaseModel

from constelite.models.store import StoreModel


class Config(BaseModel):
    stores: List[StoreModel]


def search_key(key: str, data: Dict, parent: str = "root"):
    key_parts = key.split('.')
    sub_key = key_parts[0]
    remainder = ".".join(key_parts[1:])

    data = data.get(key_parts[0], None)
    if data is None:
        raise ValueError("Can't find {sub_key} in {parent}")

    if remainder == "":
        return data
    else:
        return search_key(remainder, data, f"{parent}.{sub_key}")


def load_config():
    env = os.getenv("API_CONFIG", ".config")
    try:
        data = toml.load(env)
        return Config(**data)
    except toml.TomlDecodeError as e:
        raise BaseException(f"Invalid config: {str(e)}")

import os
import toml

from pydantic import BaseModel

from loguru import logger


class Config(BaseModel):
    pass


def get_config(getter_cls):
    env = os.getenv("API_CONFIG", ".config")

    config_cls = getter_cls.__fields__['config'].type_

    try:
        config = toml.load(env)
        return config_cls(**config[getter_cls.__name__])
    except toml.TomlDecodeError as e:
        raise BaseException(f"Invalid config: {str(e)}")
    except KeyError:
        logger.debug(f"Failed to find config for {getter_cls}")
        return config_cls()
    except FileNotFoundError:
        logger.debug("Failed to find config file")
        return config_cls()

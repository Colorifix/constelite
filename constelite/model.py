from typing import Type
from pydantic import BaseModel, ValidationError

from loguru import logger

from constelite import Config, get_config


class Model(BaseModel):

    @classmethod
    def get(
            cls,
            config: Config = None,
            getter_cls: Type["Getter"] = None,
            **kwargs
    ):

        if getter_cls is not None:
            if config is None:
                config = get_config(getter_cls)
            getter = getter_cls(config=config)
            return getter.get(cls, **kwargs)
        else:
            from constelite import getter
            getters = getter.getters()

            for getter_cls in getters[cls]:
                try:
                    if config is None:
                        config = get_config(getter_cls)
                    getter = getter_cls(config=config)
                    return getter.get(cls=cls, **kwargs)
                except ValidationError as e:
                    logger.debug(f"Failed validation, {e}")
                    continue
            raise ValidationError(
                f"Failed to find a suitable getter for {cls}"
                " with given kwargs"
            )

    def set(
        self,
        setter_cls: Type["Setter"],
        config: Config = None
    ):
        if config is None:
            config = get_config(setter_cls)
        setter = setter_cls(config=config)
        setter.set(self)

from typing import Optional, Any, Union

from socket import gethostname

from pyzeebe import Job

import asyncio
import json
import os

from typing import Type
from constelite.api import ConsteliteAPI
from constelite.protocol import ProtocolModel
from constelite.hook import HookConfig, HookModel
from pydantic.v1 import BaseModel, ValidationError

from python_camunda_sdk.runtime import CamundaRuntime
from python_camunda_sdk.runtime.config import ConnectionConfig
from loguru import logger

from .template_generator import generate_template

from .defs import (
    CONSTELITE_ENV_EVN_VARIABLE,
    RESPONSE_FIELD ,
    HOOK_CALL_RESPONSE_FIELD
)

Model = Union[ProtocolModel, HookModel]
class CamundaHookConfig(HookConfig):
    message_name: str
    correlation_key: str

class CamundaAPI(ConsteliteAPI):
    """
    Camunda API for constelite.

    Starts a worker and connects to zeebe server. Listens to service tasks with
    type equal to the protocol slug.

    Arguments:
        config: Connection config.
    """
    def __init__(self, config: ConnectionConfig, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.runtime = CamundaRuntime(
            config=self.config,
            outbound_connectors=[],
            inbound_connectors=[]
        )
        self.protocol_timeout = 1000 * 60 * 30
        self.hook_timeout = 1000 * 30

    def run(self):
        self.runtime._connect()

        for protocol_model in self.protocols:
            self.register_protocol(protocol_model=protocol_model)
        
        for hook_model in self.hooks:
            self.register_hook(hook_model=hook_model)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.start_persistent_hooks())
        loop.run_until_complete(self.runtime._worker.work())

    async def trigger_hook(self, ret: Any, hook_config: CamundaHookConfig | dict) -> None:
        """
        Sends a zeebe message to the Camunda server.

        Arguments:
            ret: Payload of the message.
            hook_config: Hook config.
        """
        if isinstance(hook_config, dict):
            hook_config = CamundaHookConfig(**hook_config)

        if self.runtime is None:
            raise Exception("Can't trigger a hook. Runtime is not started")
        
        return_value = None

        if isinstance(ret, BaseModel):
            return_value = json.loads(ret.json())
        else:
            return_value = ret
        variables = {RESPONSE_FIELD: return_value}
        logger.info(f"Triggering hook {hook_config.message_name}")

        await self.runtime._client.publish_message(
            name=hook_config.message_name,
            correlation_key=hook_config.correlation_key,
            variables=variables
        )
    @staticmethod
    def generate_task_type(protocol_model: Model) -> str:
        """
        Generates environment-aware task type.
        """
        env_tag = os.environ.get(CONSTELITE_ENV_EVN_VARIABLE, gethostname())
        return f"{env_tag}-{protocol_model.slug}"
    
    def register_protocol(self, protocol_model: ProtocolModel) -> None:
        async def task(job: Job, **kwargs):
            kwargs = {
                field_name:kwargs.get(field_name, None)
                for field_name in protocol_model.fn_model.__fields__
            }
            kwargs["logger"] = await self.get_logger(kwargs.get("logger", None))

            try:
                ret = await self.run_protocol(protocol_model.slug, **kwargs)
            except ValidationError as e:
                logger.exception(
                    "Failed to validate arguments for " f"{protocol_model.name}"
                )
                raise e
            
            if isinstance(ret, BaseModel):
                ret = json.loads(ret.json())

            return {RESPONSE_FIELD: ret}

        self.runtime._worker.task(
            task_type=self.generate_task_type(protocol_model),
            timeout_ms=self.protocol_timeout,
            before=[],
            after=[]
        )(task)
    
    def register_hook(self, hook_model: HookModel) -> None:
        async def task(
                job: Job,
                correlation_key: str,
                message_name: str,
                **kwargs
            ):
            kwargs = {
                field_name:kwargs.get(field_name, None)
                for field_name in hook_model.fn_model.__fields__
            }

            hook_config = CamundaHookConfig(
                correlation_key=correlation_key,
                message_name=message_name
            )
            
            hook_call_hash = await self.start_hook(slug=hook_model.slug, hook_config=hook_config, **kwargs)

            return {HOOK_CALL_RESPONSE_FIELD: str(hook_call_hash)}

        self.runtime._worker.task(
            task_type=self.generate_task_type(hook_model),
            timeout_ms=self.hook_timeout,
            before=[],
            after=[]
        )(task)
    
    def generate_templates(self, dir: str) -> None:
        """
        Generates Camunda modeller templates for each protocol and dumps them into
        the the specified directory.

        Arguments:
            dir: Directory to dump templates into.
        """

        if not os.path.exists(dir):
            os.makedirs(dir)

        for model in self.protocols + self.hooks:
            template = generate_template(model)
            filename = os.path.join(dir, model.slug) + ".json"
            with open(filename, "w") as f:
                data = json.dumps(
                    template.dict(exclude_none=True, by_alias=True), indent=2
                )
                f.write(data)
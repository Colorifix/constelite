import pytest

from constelite.api import ConsteliteAPI

from constelite.protocol import protocol, Protocol
from constelite.loggers import Logger


@protocol(name="Test function protocol")
async def fn_protocol(api: ConsteliteAPI, logger: Logger, a: int) -> int:
    await logger.log("Async function protocol with logger")
    return a

class ClassProtocol(Protocol):
    a: int

    async def run(self, api: ConsteliteAPI, logger: Logger) -> int:
        return self.a

class ExceptionClassProtocol(Protocol):
    a: int

    async def run(self, api: ConsteliteAPI, logger: Logger) -> int:
        raise RuntimeError("Protocol fail as expected")

@pytest.fixture
def api():
    api = ConsteliteAPI(name="Test API")
    api.add_protocol(ClassProtocol)
    api.add_protocol(ExceptionClassProtocol)
    api.add_protocol(fn_protocol)
    return api

@pytest.fixture
def logger():
    return Logger("Test Logger")

@pytest.mark.asyncio
async def test_function_protocol(api, logger):
    ret = await api.run_protocol(slug="fn_protocol", logger=logger, a=5)
    assert ret == 5

@pytest.mark.asyncio
async def test_class_protocol(api, logger):
    ret = await api.run_protocol(slug="class_protocol", logger=logger, a=10)
    assert ret == 10

@pytest.mark.asyncio
async def test_exception_protocol(api, logger):
    with pytest.raises(RuntimeError):
        await api.run_protocol(slug="exception_class_protocol", logger=logger, a=10)
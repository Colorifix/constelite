import unittest

from colorifix_alpha.util import get_config
from constelite.store import NeofluxStore
from constelite.guid_map import NeoGUIDMap
from constelite.models import StateModel, ref


class FooGUID(StateModel):
    pass

class GuidTestContext():

    def __init__(self):
        self.initialised = False

    async def initialise(self):
        if self.initialised:
            return
    
        self.store = NeofluxStore(
            uid="78be519a-fdec-4e4a-85a5-26364ccf52e4",
            name="StarGate",
            neo_config={
                "url": get_config("stores", "neoflux_store", "neo_config", "url"),
                "auth": get_config("stores", "neoflux_store", "neo_config", "auth"),
            },
            influx_config={
                "url": get_config("stores", "neoflux_store", "influx_config", "url"),
                "token": get_config("stores", "neoflux_store", "influx_config", "token"),
                "org": get_config("stores", "neoflux_store", "influx_config", "org"),
                "bucket": get_config("stores", "neoflux_store", "influx_config", "bucket"),
            }
        )

        self.guid_map = NeoGUIDMap(
            config={
                "url": get_config("guid_map", "neo", "url"),
                "auth": get_config("guid_map", "neo", "auth"),
            }
        )

        self.store.set_guid_map(guid_map=self.guid_map)

        self.initialised = True
class TestGUID(unittest.IsolatedAsyncioTestCase):
    
    context: GuidTestContext = GuidTestContext()

    async def asyncSetUp(self):
        await self.context.initialise()

    async def test_init(self):
        self.assertIsNotNone(self.context.store)
        self.assertIsNotNone(self.context.store._guid_map)

    async def test_put_new(self):
        r_foo = await self.context.store.put(ref(FooGUID()))

        self.assertIsNotNone(r_foo.guid)

    async def test_put_old_with_guid(self):
        r_foo_a = await self.context.store.put(ref(FooGUID()))
        guid = r_foo_a.guid

        r_foo_a.state = FooGUID()
        r_foo_b = await self.context.store.put(r_foo_a)

        self.assertEqual(r_foo_b.guid, guid)

    async def test_put_old_without_guid(self):
        r_foo_a = await self.context.store.put(ref(FooGUID()))
        guid = r_foo_a.guid
        r_foo_a.guid = None

        r_foo_a.state = FooGUID()
        r_foo_b = await self.context.store.put(r_foo_a)

        self.assertEqual(r_foo_b.guid, guid)

    async def test_patch_with_guid(self):
        r_foo_a = await self.context.store.put(ref(FooGUID()))
        guid = r_foo_a.guid

        r_foo_a.state = FooGUID()
        r_foo_b = await self.context.store.patch(r_foo_a)

        self.assertEqual(r_foo_b.guid, guid)

    async def test_patch_without_guid(self):
        r_foo_a = await self.context.store.put(ref(FooGUID()))
        guid = r_foo_a.guid
        r_foo_a.guid = None

        r_foo_a.state = FooGUID()
        r_foo_b = await self.context.store.patch(r_foo_a)

        self.assertEqual(r_foo_b.guid, guid)

    async def test_delete_with_guid(self):
        r_foo_a = await self.context.store.put(ref(FooGUID()))

        await self.context.store.delete(r_foo_a)

    async def test_delete_without_guid(self):
        r_foo_a = await self.context.store.put(ref(FooGUID()))
        r_foo_a.guid = None
        await self.context.store.delete(r_foo_a)

    async def test_get_with_guid(self):
        r_foo_a = await self.context.store.put(ref(FooGUID()))

        r_foo_b = await self.context.store.get(ref=r_foo_a)

        self.assertEqual(r_foo_a.guid, r_foo_b.guid)

    async def test_get_without_guid(self):
        r_foo_a = await self.context.store.put(ref(FooGUID()))
        guid = r_foo_a.guid
        r_foo_a.guid = None

        r_foo_b = await self.context.store.get(ref=r_foo_a)

        self.assertEqual(guid, r_foo_b.guid)

    async def test_get_by_guid(self):
        r_foo_a = await self.context.store.put(ref(FooGUID()))
        uid = r_foo_a.uid
        r_foo_a.record = None

        r_foo_b = await self.context.store.get(r_foo_a)

        self.assertIsNotNone(r_foo_b)
        self.assertEqual(uid, r_foo_b.uid)

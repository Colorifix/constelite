import unittest

from constelite.store import NeofluxStore
from constelite.guid_map import NeoGUIDMap
from constelite.models import StateModel, ref


class Foo(StateModel):
    pass


class TestGUID(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = NeofluxStore(
            uid="78be519a-fdec-4e4a-85a5-26364ccf52e4",
            name="StarGate",
            neo_config={
                "url": "bolt://127.0.0.1:7697",
                "auth": ("neo4j", "constelite")
            },
            influx_config={
                "url": "http://127.0.0.1:8086",
                "token": "token",
                "org": "my-org",
                "bucket": "my-bucket"
            }
        )

        cls.guid_map = NeoGUIDMap(
            config={
                "url": "bolt://127.0.0.1:7697",
                "auth": ("neo4j", "constelite")
            }
        )

        cls.store.set_guid_map(guid_map=cls.guid_map)

    def test_init(self):
        self.assertIsNotNone(self.store)
        self.assertIsNotNone(self.store._guid_map)

    def test_put_new(self):
        r_foo = self.store.put(ref(Foo()))

        self.assertIsNotNone(r_foo.guid)

    def test_put_old_with_guid(self):
        r_foo_a = self.store.put(ref(Foo()))
        guid = r_foo_a.guid

        r_foo_a.state = Foo()
        r_foo_b = self.store.put(r_foo_a)

        self.assertEqual(r_foo_b.guid, guid)

    def test_put_old_without_guid(self):
        r_foo_a = self.store.put(ref(Foo()))
        guid = r_foo_a.guid
        r_foo_a.guid = None

        r_foo_a.state = Foo()
        r_foo_b = self.store.put(r_foo_a)

        self.assertEqual(r_foo_b.guid, guid)

    def test_patch_with_guid(self):
        r_foo_a = self.store.put(ref(Foo()))
        guid = r_foo_a.guid

        r_foo_a.state = Foo()
        r_foo_b = self.store.patch(r_foo_a)

        self.assertEqual(r_foo_b.guid, guid)

    def test_patch_without_guid(self):
        r_foo_a = self.store.put(ref(Foo()))
        guid = r_foo_a.guid
        r_foo_a.guid = None

        r_foo_a.state = Foo()
        r_foo_b = self.store.patch(r_foo_a)

        self.assertEqual(r_foo_b.guid, guid)

    def test_delete_with_guid(self):
        r_foo_a = self.store.put(ref(Foo()))

        self.store.delete(r_foo_a)

    def test_delete_without_guid(self):
        r_foo_a = self.store.put(ref(Foo()))
        r_foo_a.guid = None
        self.store.delete(r_foo_a)

    def test_get_with_guid(self):
        r_foo_a = self.store.put(ref(Foo()))

        r_foo_b = self.store.get(ref=r_foo_a)

        self.assertEqual(r_foo_a.guid, r_foo_b.guid)

    def test_get_without_guid(self):
        r_foo_a = self.store.put(ref(Foo()))
        guid = r_foo_a.guid
        r_foo_a.guid = None

        r_foo_b = self.store.get(ref=r_foo_a)

        self.assertEqual(guid, r_foo_b.guid)

    def test_get_by_guid(self):
        r_foo_a = self.store.put(ref(Foo()))
        uid = r_foo_a.uid
        r_foo_a.record = None

        r_foo_b = self.store.get(r_foo_a)

        self.assertIsNotNone(r_foo_b)
        self.assertEqual(uid, r_foo_b.uid)


if __name__ == "__main__":
    unittest.main()

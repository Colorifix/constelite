import unittest
from typing import List

from constelite.store import BaseStore, RefQuery
from constelite.models import Ref, Model


class TestStore(unittest.TestCase):

    def generate_dummy_store(self, allowed_methods: List[str]):
        return type(
            "DummyStore", (BaseStore,), {
                '_allowed_methods': allowed_methods,
                'ref_exists': lambda x: True
            }
        )(name="dummy_store")

    def test_method_validation(self):
        store = self.generate_dummy_store([])

        with self.assertRaises(NotImplementedError):
            store.get(
                query=RefQuery(ref=Ref(ref='xxx', store_name='dummy_store'))
            )

        with self.assertRaises(NotImplementedError):
            store.patch(model=Model())

        with self.assertRaises(NotImplementedError):
            store.delete(model=Model())

        with self.assertRaises(NotImplementedError):
            store.put(
                model=Model(ref=Ref(ref='xxx', store_name='dummy_store'))
            )

    def test_ref_validation(self):
        store = self.generate_dummy_store(['GET', 'POST', 'PUT', 'DELETE'])

        ref = Ref(ref='xxx', store_name='foo')
        model = Model(ref=ref)

        with self.assertRaises(ValueError):
            store.put(model=model)

        with self.assertRaises(ValueError):
            store.patch(model=model)

        with self.assertRaises(ValueError):
            store.delete(model=model)


if __name__ == '__main__':
    unittest.main()

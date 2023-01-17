import unittest
from typing import Optional, ForwardRef, List

import pandera as pa

from constelite.models import (
    StateModel, ref, Dynamic, TimePoint,
    Tensor, TensorSchema,
    Association, Composition, Aggregation,
    backref
)
from constelite.store import PickleStore, NeofluxStore


class AbsorbanceSchema(TensorSchema):
    pa_schema = pa.SeriesSchema(
        'float64',
        name='absorbance',
        index=pa.MultiIndex([
            pa.Index(
                'int',
                checks=[
                    pa.Check(lambda a: a > 0)
                ],
                name='wavelenghts'
            )
        ])
    )


class Bar(StateModel):
    name: str


class Baz(StateModel):
    name: str
    foo: backref(model="Foo", from_field="baz")


class Foo(StateModel):
    int_field: Optional[int]
    str_field: Optional[str]
    bool_field: Optional[bool]
    float_field: Optional[float]
    model_field: Optional[Bar]
    list_field: Optional[List[int]]
    extra_field: Optional[int]

    dynamic_int: Optional[Dynamic[int]]
    dynamic_tensor: Optional[Dynamic[Tensor[AbsorbanceSchema]]]

    self_association: Optional[Association[ForwardRef("Foo")]]
    association: Optional[Association[Bar]]
    composition: Optional[Composition[Bar]]
    aggregation: Optional[Aggregation[Bar]]
    baz: Optional[Association[Baz]]


class StoreTestMixIn():
    store = None

    def run_field_check(self, field_name, field_value):
        state = Foo(**{field_name: field_value})
        r_state = self.store.put(ref=ref(state))

        r_state = self.store.get(ref=r_state)
        state_value = getattr(r_state.state, field_name)

        self.assertEqual(field_value, state_value)

    def overwrite_field(self, field_name, field_value_ori, field_value):
        foo = Foo(**{field_name: field_value_ori})

        r_foo = self.store.put(ref=ref(foo))

        r_foo.state = Foo(**{field_name: field_value})

        self.store.put(ref=r_foo)

        r_foo = self.store.get(ref=r_foo)

        return r_foo

    def patch_field(self, field_name, field_value_ori, field_value):
        foo = Foo(**{field_name: field_value_ori, 'extra_field': 55})

        r_foo = self.store.put(ref=ref(foo))

        r_foo.state = Foo(**{field_name: field_value})

        self.store.patch(ref=r_foo)

        r_foo = self.store.get(ref=r_foo)

        return r_foo

    def run_overwrite_check(self, field_name, field_value_ori, field_value):
        r_state = self.overwrite_field(
            field_name, field_value_ori, field_value
        )

        self.assertEqual(getattr(r_state.state, field_name), field_value)

    def run_patch_check(
            self,
            field_name,
            field_value_ori,
            field_value,
            expected_field_value=None
    ):

        if expected_field_value is None:
            expected_field_value = field_value

        r_state = self.patch_field(
            field_name, field_value_ori, field_value
        )
        state_value = getattr(r_state.state, field_name)
        extra_value = getattr(r_state.state, 'extra_field')

        self.assertEqual(expected_field_value, state_value)
        self.assertEqual(extra_value, 55)

    def run_rel_check(self, field_name, field_value):
        state = Foo(**{field_name: field_value})
        r_state = self.store.put(ref=ref(state))

        r_state = self.store.get(ref=r_state)
        state_value = getattr(r_state.state, field_name)

        state_rels = []

        for r in state_value:
            state_rels.append(
                self.store.get(ref=r).state
            )
        for field_rel in field_value:
            self.assertIn(field_rel.state, state_rels)

    def test_put_int(self):
        self.run_field_check('int_field', 123)

    def test_put_float(self):
        self.run_field_check('float_field', 10.4)

    def test_put_bool(self):
        self.run_field_check('bool_field', True)

    def test_put_model(self):
        self.run_field_check('model_field', Bar(name="bar"))

    def test_put_list(self):
        self.run_field_check('list_field', [1, 2, 3])

    def test_put_dynamic_int(self):
        value = Dynamic[int](
            points=[
                TimePoint(
                    timestamp=0,
                    value=1
                ),
                TimePoint(
                    timestamp=1,
                    value=2
                )
            ]
        )

        self.run_field_check('dynamic_int', value)

    def test_put_dynamic_tensor(self):
        value = Dynamic[Tensor[AbsorbanceSchema]](
            points=[
                TimePoint(
                    timestamp=0,
                    value=Tensor[AbsorbanceSchema](
                        data=[1.0, 2.0],
                        index=[[220, 230]]
                    )
                ),
                TimePoint(
                    timestamp=1,
                    value=Tensor[AbsorbanceSchema](
                        data=[3.0, 4.0],
                        index=[[220, 230]]
                    )
                )
            ]
        )

        self.run_field_check('dynamic_tensor', value)

    def test_put_association(self):
        value = [ref(Bar(name='bar'))]

        self.run_rel_check('association', value)

    def test_put_self_association(self):
        value = [ref(Foo(int_field=123))]

        self.run_rel_check('self_association', value)

    def test_put_composition(self):
        value = [ref(Bar(name='bar'))]

        self.run_rel_check('composition', value)

    def test_put_aggregation(self):
        value = [ref(Bar(name='bar'))]

        self.run_rel_check('aggregation', value)

    def test_put_backref(self):
        foo = Foo(
            baz=[ref(Baz(name='baz'))]
        )

        r_foo = self.store.put(ref=ref(foo))

        r_foo = self.store.get(ref=r_foo)

        r_baz = self.store.get(ref=r_foo.state.baz[0])

        self.assertIsNotNone(r_baz.state.foo)
        self.assertEqual(r_baz.state.foo[0].uid, r_foo.uid)

    def test_overwrite_int(self):
        self.run_overwrite_check('int_field', 1, 2)

    def test_overwrite_float(self):
        self.run_overwrite_check('float_field', 1.0, 2.3)

    def test_overwrite_bool(self):
        self.run_overwrite_check('bool_field', False, True)

    def test_overwrite_model(self):
        self.run_overwrite_check(
            'model_field',
            Bar(name="bar"),
            Bar(name="barbar")
        )

    def test_overwrite_list(self):
        self.run_overwrite_check(
            'list_field',
            [1, 2, 3],
            [4, 5, 6]
        )

    def test_overwrite_specificity(self):
        foo = Foo(
            int_field=123,
            bool_field=False
        )

        r_foo = self.store.put(ref=ref(foo))

        r_foo.state = Foo(
            int_field=234
        )

        self.store.put(ref=r_foo)

        r_foo = self.store.get(ref=r_foo)

        self.assertEqual(r_foo.state.int_field, 234)
        self.assertEqual(r_foo.state.bool_field, False)

    def test_overwrite_dynamic_int(self):
        value1 = Dynamic[int](
            points=[
                TimePoint(
                    timestamp=0,
                    value=1
                ),
                TimePoint(
                    timestamp=1,
                    value=2
                )
            ]
        )

        value2 = Dynamic[int](
            points=[
                TimePoint(
                    timestamp=0,
                    value=3
                ),
                TimePoint(
                    timestamp=1,
                    value=4
                )
            ]
        )

        self.run_overwrite_check('dynamic_int', value1, value2)

    def test_overwrite_dynamic_tensor(self):
        value1 = Dynamic[Tensor[AbsorbanceSchema]](
            points=[
                TimePoint(
                    timestamp=0,
                    value=Tensor[AbsorbanceSchema](
                        data=[1.0, 2.0],
                        index=[[220, 230]]
                    )
                ),
                TimePoint(
                    timestamp=1,
                    value=Tensor[AbsorbanceSchema](
                        data=[3.0, 4.0],
                        index=[[220, 230]]
                    )
                )
            ]
        )

        value2 = Dynamic[Tensor[AbsorbanceSchema]](
            points=[
                TimePoint(
                    timestamp=0,
                    value=Tensor[AbsorbanceSchema](
                        data=[3.0, 4.0],
                        index=[[220, 230]]
                    )
                ),
                TimePoint(
                    timestamp=1,
                    value=Tensor[AbsorbanceSchema](
                        data=[5.0, 6.0],
                        index=[[220, 230]]
                    )
                )
            ]
        )

        self.run_overwrite_check('dynamic_tensor', value1, value2)

    def test_overwrite_association(self):
        r_bar_ori = self.store.put(ref=ref(Bar(name='bar')))

        r_foo = self.overwrite_field(
            'association',
            [r_bar_ori],
            [ref(Bar(name='barbar'))]
        )

        r_bar = self.store.get(ref=r_foo.state.association[0])

        self.assertEqual(r_bar.state.name, 'barbar')
        self.assertEqual(len(r_foo.state.association), 1)
        self.assertTrue(
            self.store.uid_exists(
                uid=r_bar_ori.uid,
                model_type=Bar
            )
        )

    def test_overwrite_aggregation(self):
        r_bar_ori = self.store.put(ref=ref(Bar(name='bar')))

        r_foo = self.overwrite_field(
            'aggregation',
            [r_bar_ori],
            [ref(Bar(name='barbar'))]
        )

        r_bar = self.store.get(ref=r_foo.state.aggregation[0])

        self.assertEqual(r_bar.state.name, 'barbar')
        self.assertEqual(len(r_foo.state.aggregation), 1)
        self.assertTrue(
            self.store.uid_exists(
                uid=r_bar_ori.uid,
                model_type=Bar
            )
        )

    def test_overwrite_composition(self):
        r_bar_ori = self.store.put(ref=ref(Bar(name='bar')))

        r_foo = self.overwrite_field(
            'composition',
            [r_bar_ori],
            [ref(Bar(name='barbar'))]
        )

        r_bar = self.store.get(ref=r_foo.state.composition[0])

        self.assertEqual(r_bar.state.name, 'barbar')
        self.assertEqual(len(r_foo.state.composition), 1)
        self.assertFalse(
            self.store.uid_exists(
                uid=r_bar_ori.uid,
                model_type=Bar
            )
        )

    def test_patch_int(self):
        self.run_patch_check('int_field', 1, 2)

    def test_patch_float(self):
        self.run_patch_check('float_field', 1.0, 2.3)

    def test_patch_bool(self):
        self.run_patch_check('bool_field', False, True)

    def test_patch_model(self):
        self.run_patch_check(
            'model_field',
            Bar(name="bar"),
            Bar(name="barbar")
        )

    def test_patch_list(self):
        self.run_overwrite_check(
            'list_field',
            [1, 2, 3],
            [4, 5, 6]
        )

    def test_patch_dynamic_int(self):
        value1 = Dynamic[int](
            points=[
                TimePoint(
                    timestamp=0,
                    value=1
                ),
                TimePoint(
                    timestamp=1,
                    value=2
                )
            ]
        )

        value2 = Dynamic[int](
            points=[
                TimePoint(
                    timestamp=2,
                    value=3
                ),
                TimePoint(
                    timestamp=3,
                    value=4
                )
            ]
        )

        expected = Dynamic[int](
            points=value1.points + value2.points
        )

        self.run_patch_check(
            'dynamic_int',
            value1, value2, expected
        )

    def test_patch_dynamic_tensor(self):
        value1 = Dynamic[Tensor[AbsorbanceSchema]](
            points=[
                TimePoint(
                    timestamp=0,
                    value=Tensor[AbsorbanceSchema](
                        data=[1.0, 2.0],
                        index=[[220, 230]]
                    )
                ),
                TimePoint(
                    timestamp=1,
                    value=Tensor[AbsorbanceSchema](
                        data=[3.0, 4.0],
                        index=[[220, 230]]
                    )
                )
            ]
        )

        value2 = Dynamic[Tensor[AbsorbanceSchema]](
            points=[
                TimePoint(
                    timestamp=3,
                    value=Tensor[AbsorbanceSchema](
                        data=[3.0, 4.0],
                        index=[[220, 230]]
                    )
                ),
                TimePoint(
                    timestamp=4,
                    value=Tensor[AbsorbanceSchema](
                        data=[5.0, 6.0],
                        index=[[220, 230]]
                    )
                )
            ]
        )

        expected = Dynamic[Tensor[AbsorbanceSchema]](
            points=value1.points + value2.points
        )

        self.run_patch_check(
            'dynamic_tensor',
            value1, value2, expected
        )

    def test_patch_association(self):
        r_bar_ori = self.store.put(ref=ref(Bar(name='bar')))
        r_bar = self.store.put(ref=(ref(Bar(name='barbar'))))

        r_foo = self.patch_field(
            'association',
            [r_bar_ori],
            [r_bar]
        )

        self.assertEqual(
            r_foo.state.association[0].uid,
            r_bar.uid
        )

        self.assertEqual(len(r_foo.state.association), 1)
        self.assertTrue(
            self.store.uid_exists(
                uid=r_bar_ori.uid,
                model_type=Bar
            )
        )

    def test_patch_aggregation(self):
        r_bar_ori = self.store.put(ref=ref(Bar(name='bar')))
        r_bar = self.store.put(ref=(ref(Bar(name='barbar'))))

        r_foo = self.patch_field(
            'aggregation',
            [r_bar_ori],
            [r_bar]
        )

        self.assertEqual(len(r_foo.state.aggregation), 2)

        self.assertTrue(
            self.store.uid_exists(
                uid=r_bar_ori.uid,
                model_type=Bar
            )
        )
        self.assertTrue(
            self.store.uid_exists(
                uid=r_bar.uid,
                model_type=Bar
            )
        )

        self.assertIn(
            r_bar,
            r_foo.state.aggregation
        )
        self.assertIn(
            r_bar_ori,
            r_foo.state.aggregation,
        )

    def test_patch_composition(self):
        r_bar_ori = self.store.put(ref=ref(Bar(name='bar')))
        r_bar = self.store.put(ref=(ref(Bar(name='barbar'))))

        r_foo = self.patch_field(
            'composition',
            [r_bar_ori],
            [r_bar]
        )

        self.assertEqual(len(r_foo.state.composition), 2)

        self.assertTrue(
            self.store.uid_exists(
                uid=r_bar_ori.uid,
                model_type=Bar
            )
        )
        self.assertTrue(
            self.store.uid_exists(
                uid=r_bar.uid,
                model_type=Bar
            )
        )

        self.assertIn(
            r_bar,
            r_foo.state.composition
        )
        self.assertIn(
            r_bar_ori,
            r_foo.state.composition,
        )

    def test_delete_simple(self):
        r_foo = self.store.put(ref=ref(Foo()))

        self.store.delete(ref=r_foo)

        self.assertFalse(
            self.store.uid_exists(
                uid=r_foo.uid,
                model_type=Foo
            )
        )

    def test_delete_composite(self):
        r_bar = self.store.put(ref=ref(Bar(name='bar')))
        r_foo = self.store.put(
            ref=ref(
                Foo(
                    composition=[r_bar]
                )
            )
        )

        self.store.delete(ref=r_foo)

        self.assertFalse(
            self.store.uid_exists(
                uid=r_foo.uid,
                model_type=Foo
            )
        )
        self.assertFalse(self.store.uid_exists(
            uid=r_bar.uid,
            model_type=Bar
        ))


class TestPickleStore(unittest.TestCase, StoreTestMixIn):
    store = PickleStore(
        uid="4a0929bb-d691-4f04-81f9-4780897e959f",
        name="Pickle Rick",
        path="/Users/md/store"
    )


class TestNeofluxStore(unittest.TestCase, StoreTestMixIn):
    store = NeofluxStore(
        uid="78be519a-fdec-4e4a-85a5-26364ccf52e4",
        name="StarGate",
        neo_config={
            "url": "bolt://127.0.0.1:7697",
            "auth": ("neo4j", "constelite")
        },
        influx_config={
            "host": "127.0.0.1",
            "port": 8087,
            "username": None,
            "password": None
        }
    )


if __name__ == '__main__':
    unittest.main()

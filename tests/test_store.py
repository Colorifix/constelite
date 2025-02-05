import unittest

from uuid import uuid4

from typing import Optional, ForwardRef, List, Type

import pandera as pa

from constelite.models import (
    StateModel, ref, Dynamic, TimePoint,
    Tensor, TensorSchema,
    Association, Composition, Aggregation,
    backref
)
from constelite.store import (
    MemoryStore,
    PropertyQuery,
    BaseStore
)


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


class Qux(StateModel):
    # Just for the get all query test
    name: str


class StoreTestMixIn():
    store = None

    async def uid_exists(self, uid:str, model_type: Type[StateModel]):
        if isinstance(self.store, BaseStore):
            return self.store.uid_exists(uid=uid, model_type=model_type)
        else:
            return await self.store.uid_exists(uid=uid, model_type=model_type)
    
    async def run_field_check(self, field_name, field_value):
        state = Foo(**{field_name: field_value})
        r_state = await self.store.put(ref=ref(state))

        r_state = await self.store.get(ref=r_state)
        state_value = getattr(r_state.state, field_name)

        self.assertEqual(field_value, state_value)

    async def overwrite_field(self, field_name, field_value_ori, field_value):
        foo = Foo(**{field_name: field_value_ori})

        r_foo = await self.store.put(ref=ref(foo))

        r_foo.state = Foo(**{field_name: field_value})

        await self.store.put(ref=r_foo)

        r_foo = await self.store.get(ref=r_foo)

        return r_foo

    async def patch_field(self, field_name, field_value_ori, field_value):
        foo = Foo(**{field_name: field_value_ori, 'extra_field': 55})

        r_foo = await self.store.put(ref=ref(foo))

        r_foo.state = Foo(**{field_name: field_value})

        await self.store.patch(ref=r_foo)

        r_foo = await self.store.get(ref=r_foo)

        return r_foo

    async def run_overwrite_check(self, field_name, field_value_ori, field_value):
        r_state = await self.overwrite_field(
            field_name, field_value_ori, field_value
        )

        self.assertEqual(getattr(r_state.state, field_name), field_value)

    async def run_patch_check(
            self,
            field_name,
            field_value_ori,
            field_value,
            expected_field_value=None
    ):

        if expected_field_value is None:
            expected_field_value = field_value

        r_state = await self.patch_field(
            field_name, field_value_ori, field_value
        )
        state_value = getattr(r_state.state, field_name)
        extra_value = getattr(r_state.state, 'extra_field')

        self.assertEqual(expected_field_value, state_value)
        self.assertEqual(extra_value, 55)

    async def run_rel_check(self, field_name, field_value):
        state = Foo(**{field_name: field_value})
        r_state = await self.store.put(ref=ref(state))

        r_state = await self.store.get(ref=r_state)
        state_value = getattr(r_state.state, field_name)

        state_rels = []

        for r in state_value:
            r = await self.store.get(ref=r)
            state_rels.append(
                r.state
            )
        for field_rel in field_value:
            self.assertIn(field_rel.state, state_rels)

    async def test_put_int(self):
        await self.run_field_check('int_field', 123)

    async def test_put_float(self):
        await self.run_field_check('float_field', 10.4)

    async def test_put_bool(self):
        await self.run_field_check('bool_field', True)

    async def test_put_model(self):
        await self.run_field_check('model_field', Bar(name="bar"))

    async def test_put_list(self):
        await self.run_field_check('list_field', [1, 2, 3])

    async def test_put_dynamic_int(self):
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

        await self.run_field_check('dynamic_int', value)

    async def test_put_dynamic_tensor(self):
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

        await self.run_field_check('dynamic_tensor', value)

    async def test_put_association(self):
        value = [ref(Bar(name='bar'))]

        await self.run_rel_check('association', value)

    async def test_put_self_association(self):
        value = [ref(Foo(int_field=123))]

        await self.run_rel_check('self_association', value)

    async def test_put_composition(self):
        value = [ref(Bar(name='bar'))]

        await self.run_rel_check('composition', value)

    async def test_put_aggregation(self):
        value = [ref(Bar(name='bar'))]

        await self.run_rel_check('aggregation', value)

    async def test_put_backref(self):
        foo = Foo(
            baz=[ref(Baz(name='baz'))]
        )

        r_foo = await self.store.put(ref=ref(foo))

        r_foo = await self.store.get(ref=r_foo)

        r_baz = await self.store.get(ref=r_foo.state.baz[0])

        self.assertIsNotNone(r_baz.state.foo)
        self.assertEqual(r_baz.state.foo[0].uid, r_foo.uid)

    async def test_overwrite_int(self):
        await self.run_overwrite_check('int_field', 1, 2)

    async def test_overwrite_float(self):
        await self.run_overwrite_check('float_field', 1.0, 2.3)

    async def test_overwrite_bool(self):
        await self.run_overwrite_check('bool_field', False, True)

    async def test_overwrite_model(self):
        await self.run_overwrite_check(
            'model_field',
            Bar(name="bar"),
            Bar(name="barbar")
        )

    async def test_overwrite_list(self):
        await self.run_overwrite_check(
            'list_field',
            [1, 2, 3],
            [4, 5, 6]
        )

    async def test_overwrite_specificity(self):
        foo = Foo(
            int_field=123,
            bool_field=False
        )

        r_foo = await self.store.put(ref=ref(foo))

        r_foo.state = Foo(
            int_field=234
        )

        await self.store.put(ref=r_foo)

        r_foo = await self.store.get(ref=r_foo)

        self.assertEqual(r_foo.state.int_field, 234)
        self.assertEqual(r_foo.state.bool_field, False)

    async def test_overwrite_dynamic_int(self):
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

        await self.run_overwrite_check('dynamic_int', value1, value2)

    async def test_overwrite_dynamic_tensor(self):
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

        await self.run_overwrite_check('dynamic_tensor', value1, value2)

    async def test_overwrite_association(self):
        r_bar_ori = await self.store.put(ref=ref(Bar(name='bar')))

        r_foo = await self.overwrite_field(
            'association',
            [r_bar_ori],
            [ref(Bar(name='barbar'))]
        )

        r_bar = await self.store.get(ref=r_foo.state.association[0])

        self.assertEqual(r_bar.state.name, 'barbar')
        self.assertEqual(len(r_foo.state.association), 1)
        self.assertTrue(
            await self.uid_exists(
                uid=r_bar_ori.uid,
                model_type=Bar
            )
        )

    async def test_overwrite_aggregation(self):
        r_bar_ori = await self.store.put(ref=ref(Bar(name='bar')))

        r_foo = await self.overwrite_field(
            'aggregation',
            [r_bar_ori],
            [ref(Bar(name='barbar'))]
        )

        r_bar = await self.store.get(ref=r_foo.state.aggregation[0])

        self.assertEqual(r_bar.state.name, 'barbar')
        self.assertEqual(len(r_foo.state.aggregation), 1)
        
        self.assertTrue(
            await self.uid_exists(
                uid=r_bar.uid,
                model_type=Bar
            )
        )

    async def test_overwrite_composition(self):
        r_bar_ori = await self.store.put(ref=ref(Bar(name='bar')))

        r_foo = await self.overwrite_field(
            'composition',
            [r_bar_ori],
            [ref(Bar(name='barbar'))]
        )

        r_bar = await self.store.get(ref=r_foo.state.composition[0])

        self.assertEqual(r_bar.state.name, 'barbar')
        self.assertEqual(len(r_foo.state.composition), 1)
        self.assertFalse(
            await self.uid_exists(
                uid=r_bar_ori.uid,
                model_type=Bar
            )
        )

    async def test_patch_int(self):
        await self.run_patch_check('int_field', 1, 2)

    async def test_patch_float(self):
        await self.run_patch_check('float_field', 1.0, 2.3)

    async def test_patch_bool(self):
        await self.run_patch_check('bool_field', False, True)

    async def test_patch_model(self):
        await self.run_patch_check(
            'model_field',
            Bar(name="bar"),
            Bar(name="barbar")
        )

    async def test_patch_list(self):
        await self.run_overwrite_check(
            'list_field',
            [1, 2, 3],
            [4, 5, 6]
        )

    async def test_patch_dynamic_int(self):
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

        await self.run_patch_check(
            'dynamic_int',
            value1, value2, expected
        )

    async def test_patch_dynamic_tensor(self):
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

        await self.run_patch_check(
            'dynamic_tensor',
            value1, value2, expected
        )

    async def test_patch_association(self):
        r_bar_ori = await self.store.put(ref=ref(Bar(name='bar')))
        r_bar = await self.store.put(ref=(ref(Bar(name='barbar'))))

        r_foo = await self.patch_field(
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
            await self.uid_exists(
                uid=r_bar_ori.uid,
                model_type=Bar
            )
        )

    async def test_patch_aggregation(self):
        r_bar_ori = await self.store.put(ref=ref(Bar(name='bar')))
        r_bar = await self.store.put(ref=(ref(Bar(name='barbar'))))

        r_foo = await self.patch_field(
            'aggregation',
            [r_bar_ori],
            [r_bar]
        )

        self.assertEqual(len(r_foo.state.aggregation), 2)

        self.assertTrue(
            await self.uid_exists(
                uid=r_bar_ori.uid,
                model_type=Bar
            )
        )
        self.assertTrue(
            await self.uid_exists(
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

    async def test_patch_composition(self):
        r_bar_ori = await self.store.put(ref=ref(Bar(name='bar')))
        r_bar = await self.store.put(ref=(ref(Bar(name='barbar'))))

        r_foo = await self.patch_field(
            'composition',
            [r_bar_ori],
            [r_bar]
        )

        self.assertEqual(len(r_foo.state.composition), 2)

        self.assertTrue(
            await self.uid_exists(
                uid=r_bar_ori.uid,
                model_type=Bar
            )
        )
        self.assertTrue(
            await self.uid_exists(
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

    async def test_delete_simple(self):
        r_foo = await self.store.put(ref=ref(Foo()))

        await self.store.delete(ref=r_foo)

        self.assertFalse(
            await self.uid_exists(
                uid=r_foo.uid,
                model_type=Foo
            )
        )

    async def test_delete_composite(self):
        r_bar = await self.store.put(ref=ref(Bar(name='bar')))
        r_foo = await self.store.put(
            ref=ref(
                Foo(
                    composition=[r_bar]
                )
            )
        )

        await self.store.delete(ref=r_foo)

        self.assertFalse(
            await self.uid_exists(
                uid=r_foo.uid,
                model_type=Foo
            )
        )
        self.assertFalse(
            await self.uid_exists(
                uid=r_bar.uid,
                model_type=Bar
            )
        )

    async def test_delete_association(self):
        r_bar = await self.store.put(ref=ref(Bar(name='bar')))
        r_foo = await self.store.put(
            ref=ref(
                Foo(
                    association=[r_bar]
                )
            )
        )

        await self.store.delete(ref=r_foo)

        self.assertFalse(
            await self.uid_exists(
                uid=r_foo.uid,
                model_type=Foo
            )
        )
        self.assertTrue(
            await self.uid_exists(
                uid=r_bar.uid,
                model_type=Bar
            )
        )

    async def test_property_query(self):
        try:
            self.store._validate_method('QUERY')

            await self.store.put(
                ref=ref(
                    Foo(int_field=1234)
                )
            )

            foos = await self.store.query(
                query=PropertyQuery(
                    int_field=1234
                ),
                include_states=True,
                model_name="Foo"
            )
            self.assertTrue(foos[0].int_field == 1234)
        except NotImplementedError:
            pass

    async def test_get_all_property_query(self):
        # Create and delete the items in the test to control numbers
        try:
            self.store._validate_method('QUERY')

            await self.store.put(
                ref=ref(
                    Qux(name="Qux1")
                )
            )
            await self.store.put(
                ref=ref(
                    Qux(name="Qux2")
                )
            )
            quxes = await self.store.query(
                include_states=True,
                model_name="Qux"
            )
            self.assertTrue(len(quxes) == 2)
            for q in quxes:
                await self.store.delete(q)
        except NotImplementedError:
            pass

    async def test_bulk_get(self):

        try:
            self.store._validate_method('GET')

            ref1 = await self.store.put(
                ref=ref(
                    Qux(name="Qux1")
                )
            )
            ref2 = await self.store.put(
                ref=ref(
                    Qux(name="Qux2")
                )
            )

            ref1, ref2 = await self.store.bulk_get([ref1, ref2])
            assert ref1.name == "Qux1"
            assert ref2.name == "Qux2"

            # delete the items to clean up
            await self.store.delete(ref1)
            await self.store.delete(ref2)
        except NotImplementedError:
            pass


class TestMemoryStore(unittest.IsolatedAsyncioTestCase, StoreTestMixIn):
    store = MemoryStore(
        uid=uuid4(),
        name="MemoryStore",
    )

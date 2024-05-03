import unittest
from typing import Optional, ForwardRef, List

import pandera as pa

from constelite.models import (
    StateModel, ref, Dynamic, TimePoint,
    Tensor, TensorSchema,
    Association, Composition, Aggregation,
    backref
)
from constelite.models import StateInspector


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


class BarInspector(StateModel):
    name: str


class BazInspector(StateModel):
    name: str
    foo: backref(model="FooInspector", from_field="baz")


class BazUnfixedBackrefs(StateModel):
    name: str
    foo: backref(model="FooInspector", from_field="baz_unfixed_backrefs")


class FooInspector(StateModel):
    int_field: Optional[int]
    str_field: Optional[str]
    bool_field: Optional[bool]
    float_field: Optional[float]
    model_field: Optional[BarInspector]
    list_field: Optional[List[int]]
    extra_field: Optional[int]

    dynamic_int: Optional[Dynamic[int]]
    dynamic_tensor: Optional[Dynamic[Tensor[AbsorbanceSchema]]]

    self_association: Optional[Association[ForwardRef("FooInspector")]]
    association: Optional[Association[BarInspector]]
    composition: Optional[Composition[BarInspector]]
    aggregation: Optional[Aggregation[BarInspector]]
    baz: Optional[Association[BazInspector]]
    baz_unfixed_backrefs: Optional[Association[BazUnfixedBackrefs]]


class QuxInspector(FooInspector):
    pass


BazInspector.fix_backrefs()
# Not fixing backrefs for BazUnfixedBackrefs


class TestInspector(unittest.TestCase):

    def test_rel_inspection(self):
        foo = FooInspector(
            association=[ref(BarInspector(name='association'))],
            composition=[ref(BarInspector(name='composition'))],
            aggregation=[ref(BarInspector(name='aggregation'))]
        )

        inspector = StateInspector.from_state(foo)

        self.assertTrue('association' in inspector.associations)
        self.assertEqual(
            inspector.associations['association'].from_field_name,
            'association'
        )
        self.assertIsNone(
            inspector.associations['association'].to_field_name,
        )

        self.assertTrue('composition' in inspector.compositions)
        self.assertEqual(
            inspector.compositions['composition'].from_field_name,
            'composition'
        )
        self.assertIsNone(
            inspector.compositions['composition'].to_field_name,
        )

        self.assertTrue('aggregation' in inspector.aggregations)
        self.assertEqual(
            inspector.aggregations['aggregation'].from_field_name,
            'aggregation'
        )
        self.assertIsNone(
            inspector.aggregations['aggregation'].to_field_name,
        )

    def test_rel_with_backref(self):
        foo = FooInspector(
            baz=[ref(BazInspector(name='baz'))]
        )

        inspector = StateInspector.from_state(foo)

        self.assertTrue('baz' in inspector.associations)
        self.assertEqual(inspector.associations['baz'].from_field_name, 'baz')
        self.assertEqual(inspector.associations['baz'].to_field_name, 'foo')

    def test_rel_with_unfixed_backref(self):
        # This only matters for subclasses of the model with the relationship
        foo = QuxInspector(
            baz_unfixed_backrefs=[ref(BazUnfixedBackrefs(name='baz'))]
        )

        inspector = StateInspector.from_state(foo)

        self.assertTrue('baz_unfixed_backrefs' in inspector.associations)
        self.assertEqual(
            inspector.associations['baz_unfixed_backrefs'].from_field_name,
            'baz_unfixed_backrefs')
        self.assertEqual(
            inspector.associations['baz_unfixed_backrefs'].to_field_name,
            'foo')

    def test_subclass_backref(self):
        qux = QuxInspector(
            baz=[ref(BazInspector(name='baz'))]
        )

        inspector = StateInspector.from_state(qux)

        self.assertTrue('baz' in inspector.associations)
        self.assertEqual(inspector.associations['baz'].from_field_name, 'baz')
        self.assertEqual(inspector.associations['baz'].to_field_name, 'foo')

    def test_backref(self):
        baz = BazInspector(
            name='baz',
            foo=[ref(FooInspector())]
        )

        inspector = StateInspector.from_state(baz)

        self.assertTrue('foo' in inspector.backrefs)
        self.assertEqual(inspector.backrefs['foo'].from_field_name, 'baz')
        self.assertEqual(inspector.backrefs['foo'].to_field_name, 'foo')

    def test_forward_ref(self):
        foo = FooInspector(
            self_association=[ref(FooInspector())]
        )

        inspector = StateInspector.from_state(foo)

        self.assertTrue('self_association' in inspector.associations)
        self.assertEqual(
            inspector.associations['self_association'].from_field_name,
            'self_association'
        )
        self.assertIsNone(
            inspector.associations['self_association'].to_field_name,
            None
        )

    def test_static_properties(self):
        static_values = dict(
            int_field=1,
            str_field='str',
            bool_field=True,
            float_field=1.5,
            model_field=BarInspector(name='bar'),
            model_name='FooInspector'
        )
        foo = FooInspector(**static_values)

        inspector = StateInspector.from_state(foo)

        self.assertEqual(inspector.static_props, static_values)

    def test_dynamic_properties(self):
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
        foo = FooInspector(
            dynamic_int=value
        )

        inspector = StateInspector.from_state(foo)

        self.assertEqual(inspector.dynamic_props['dynamic_int'], value)


if __name__ == '__main__':
    unittest.main()

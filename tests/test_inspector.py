import unittest
from typing import Optional, ForwardRef, List

from constelite.models import (
    StateModel, ref, Dynamic, TimePoint,
    Association, Composition, Aggregation,
    backref
)
from constelite.models import StateInspector


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

    self_association: Optional[Association[ForwardRef("Foo")]]
    association: Optional[Association[Bar]]
    composition: Optional[Composition[Bar]]
    aggregation: Optional[Aggregation[Bar]]
    baz: Optional[Association[Baz]]


Baz.fix_backrefs()


class TestInspector(unittest.TestCase):

    def test_rel_inspection(self):
        foo = Foo(
            association=[ref(Bar(name='association'))],
            composition=[ref(Bar(name='composition'))],
            aggregation=[ref(Bar(name='aggregation'))]
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

    def test_ref_with_backref(self):
        foo = Foo(
            baz=[ref(Baz(name='baz'))]
        )

        inspector = StateInspector.from_state(foo)

        self.assertTrue('baz' in inspector.associations)
        self.assertEqual(inspector.associations['baz'].from_field_name, 'baz')
        self.assertEqual(inspector.associations['baz'].to_field_name, 'foo')

    def test_backref(self):
        baz = Baz(
            name='baz',
            foo=[ref(Foo())]
        )

        inspector = StateInspector.from_state(baz)

        self.assertTrue('foo' in inspector.backrefs)
        self.assertEqual(inspector.backrefs['foo'].from_field_name, 'baz')
        self.assertEqual(inspector.backrefs['foo'].to_field_name, 'foo')

    def test_forward_ref(self):
        foo = Foo(
            self_association=[ref(Foo())]
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
            model_field=Bar(name='bar'),
            model_name='Foo'
        )
        foo = Foo(**static_values)

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
        foo = Foo(
            dynamic_int=value
        )

        inspector = StateInspector.from_state(foo)

        self.assertEqual(inspector.dynamic_props['dynamic_int'], value)


if __name__ == '__main__':
    unittest.main()

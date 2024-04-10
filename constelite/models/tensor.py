from typing import TypeVar, Generic, List, Optional, ClassVar, Any

from functools import reduce

from pydantic.v1 import BaseModel, Field, validator, root_validator
from pydantic.v1.generics import GenericModel


import pandera as pa
import pandas as pd


V = TypeVar('ValueType')
S = TypeVar('SchemaType')


class TensorSchema(BaseModel):
    pa_schema: ClassVar[pa.SeriesSchema]


class DefaultSchema(TensorSchema):
    pa_schema = pa.SeriesSchema()


class Tensor(GenericModel, Generic[S]):
    tensor_schema: Optional[S] = Field(exclude=True, default=DefaultSchema())
    data: List
    index: Optional[List[List]]
    index_names: Optional[List[str]]
    name: Optional[str]

    @classmethod
    @property
    def pa_schema(cls):
        return cls.__fields__['tensor_schema'].type_.pa_schema

    @classmethod
    @property
    def schema_cls(cls):
        return cls.__fields__['tensor_schema'].type_

    @staticmethod
    def _generate_series(index: List[List], data: List,
                         index_names: List[str], name: str):
        return pd.Series(
            index=pd.MultiIndex.from_product(index, names=index_names),
            data=data,
            name=name
        )

    @validator('tensor_schema', always=True)
    def validate_schema(cls, v):
        schema_cls = cls.__fields__['tensor_schema'].type_
        if schema_cls != Any:
            assert issubclass(
                schema_cls, TensorSchema
            ), "Supplies schema must be derived from TensorSchema"
            assert hasattr(
                schema_cls, 'pa_schema'
            ), "Schema has no pa_schema attribute"
            assert schema_cls.pa_schema is not None, "pa_schema is None"
            assert isinstance(
                schema_cls.pa_schema, pa.SeriesSchema
            ), "pa_schema is not pa.SeriesSchema"
            return schema_cls()
        return None

    @validator('index', always=True)
    def validate_index(cls, v, values):
        data = values.get('data', None)

        if data is None:
            return v

        if v is None:
            v = [list(range(len(data)))]

        index_len = reduce(
            (lambda x, y: x * y),
            [len(idx) for idx in v],
            1
        )

        data_len = len(values['data'])
        if index_len != data_len:
            raise ValueError(
                f"Index len ({index_len}) does not match "
                f"data len ({data_len})"
            )
        return v

    @validator('index_names', always=True)
    def validate_index_names(cls, v, values):
        index = values.get('index', None)
        if index is None:
            return v

        if v is None:
            schema = values.get('tensor_schema', None)
            if (
                schema is not None
                and schema.pa_schema.index is not None
            ):
                v = schema.pa_schema.index.names
            return v

        assert len(v) == len(index), (
            "Mismatch between length of index_name and index"
        )

        return v

    @validator('name')
    def validate_name(cls, v, values):
        if v is None:
            schema = values['schema']
            v = schema.pa_index.name
        return v

    @root_validator
    def validate(cls, values):
        if isinstance(values, dict):
            schema = values.get('tensor_schema', None)
            if schema is not None:
                index_names = values.get('index_names', None)
                name = values.get('name', None)

                if index_names is not None or index_names == []:
                    values['index_names'] = schema.pa_schema.index.names

                if name is None:
                    values['name'] = schema.pa_schema.name
                series = cls._generate_series(
                    index=values['index'],
                    data=values['data'],
                    index_names=values['index_names'],
                    name=values['name']
                )
                try:
                    schema.pa_schema.validate(series)
                except pa.errors.SchemaError as e:
                    raise ValueError(f'Schema validation failed: {e}')

        return values

    @classmethod
    def from_series(cls, series: pd.Series):
        pa_schema = cls.pa_schema

        series.rename(pa_schema.name, inplace=True)

        df = series.reset_index()
        df.set_index(pa_schema.index.names, inplace=True)

        if not isinstance(df.index, pd.MultiIndex):
            df.index = pd.MultiIndex.from_product([df.index])

        series = df[pa_schema.name]
        pa_schema.validate(series)

        index = [
            list(level) for level in
            pd.MultiIndex.from_product(series.index.levels).levels
        ]

        data = list(series.to_numpy().flatten())

        return cls(index=index, data=data)

    def to_series(self) -> pd.Series:
        return self._generate_series(
            index=self.index,
            data=self.data,
            index_names=self.index_names,
            name=self.name
        )

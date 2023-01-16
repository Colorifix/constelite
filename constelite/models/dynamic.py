import datetime

from typing import TypeVar, Generic, List, Type
from pydantic import validator
from pydantic.generics import GenericModel

import pandera as pa
import pandas as pd

from constelite.models.tensor import Tensor


V = TypeVar('ValueType')


class TimePoint(GenericModel, Generic[V]):
    timestamp: float
    value: V

    @classmethod
    @property
    def _point_type(cls) -> Type:
        return cls.__fields__['value'].type_

    @validator('value')
    def convert_value(cls, v):
        if isinstance(v, dict) and cls._point_type != dict:
            return cls._point_type(**v)
        return v


class Dynamic(GenericModel, Generic[V]):
    points: List[TimePoint[V]]

    def __len__(self):
        return len(self.points)

    @classmethod
    @property
    def _point_type(cls) -> Type:
        return cls.__fields__['points'].type_._point_type

    def to_series(self):
        times = [
            datetime.datetime.fromtimestamp(point.timestamp)
            for point in self.points
        ]
        if issubclass(self._point_type, Tensor):
            series = [point.value.to_series() for point in self.points]
            return pd.concat(series, keys=times, names=['timestamp'])
        else:
            index = pd.Index(times, name='timestamp')
            data = [point.value for point in self.points]
            return pd.Series(index=index, data=data)

    @classmethod
    def from_series(cls, series: pd.Series):
        if issubclass(cls._point_type, Tensor):
            tensor_schema_cls = cls._point_type._schema_cls
            tensor_schema = cls._point_type._schema.pa_schema

            value_type = None
            schema_indexes = []

            if tensor_schema is not None:
                value_type = tensor_schema.dtype

                if isinstance(tensor_schema.index, pa.MultiIndex):
                    schema_indexes = tensor_schema.index.indexes
                elif isinstance(tensor_schema.index, pa.Indes):
                    schema_indexes = [tensor_schema.index]

            schema = pa.SeriesSchema(
                value_type,
                index=pa.MultiIndex(
                     [pa.Index('datetime64[ns]', name='timestamp')]
                     + schema_indexes
                )
            )

            schema.validate(series)

            datetime_index = series.index.levels[0]

            points = []

            for timestamp in datetime_index:
                points.append(
                    TimePoint[Tensor[tensor_schema_cls]](
                        timestamp=timestamp.to_pydatetime().timestamp(),
                        value=series[timestamp]
                    )
                )
            return cls(
                points=points
            )

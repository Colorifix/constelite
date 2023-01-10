from typing import Optional, Dict, List, Tuple, Type
from uuid import uuid4

import datetime
from dateutil.parser import isoparse

import pandas as pd

from inspect import getmro

from pydantic import Field, BaseModel

from constelite.store import BaseStore

from constelite.models import (
    StateModel, StaticTypes, Dynamic, UID,
    RelInspector, resolve_model, Tensor, TimePoint
)

from py2neo import Graph, Node, Relationship
from influxdb import InfluxDBClient

UID_FIELD = '_uid'
LIVE_LABEL = "_LiveNode"


class NeoConfig(BaseModel):
    url: str
    auth: Tuple[str, str]


class InfluxConfig(BaseModel):
    host: str
    port: int
    username: Optional[str]
    password: Optional[str]


class NeofluxStore(BaseStore):
    _allowed_methods = ["PUT", "GET", "PATCH", "DELETE"]

    neo_config: NeoConfig = Field(exclude=True)
    influx_config: InfluxConfig = Field(exclude=True)

    graph: Optional[Graph] = Field(exclude=True)
    influx: Optional[InfluxDBClient] = Field(exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data):
        super().__init__(**data)
        self.graph = Graph(self.neo_config.url, auth=self.neo_config.auth)
        self.influx = InfluxDBClient(**self.influx_config.dict())
        self.influx.create_database("constelite")
        self.influx.switch_database("constelite")

    def uid_exists(self, uid: UID) -> bool:
        return self.graph.nodes.match(
                LIVE_LABEL,
                **{UID_FIELD: uid}
            ).exists()

    def get_node(self, uid: UID) -> Node:
        return self.graph.nodes.match(
                LIVE_LABEL,
                **{UID_FIELD: uid}
            ).first()

    def create_model(
            self,
            model_type: StateModel,
            static_props: Dict[str, StaticTypes],
            dynamic_props: Dict[str, Optional[Dynamic]]) -> UID:
        mro = getmro(model_type)
        labels = []

        for cls in mro:
            labels.append(cls.__name__)
            if cls == StateModel:
                break

        labels.append(LIVE_LABEL)

        uid = str(uuid4())

        static_props[UID_FIELD] = uid

        node = Node(*labels, **static_props)

        tx = self.graph.begin()
        tx.create(node)
        tx.commit()

        for prop_name, prop in dynamic_props.items():
            self.write_dynamic_to_influx(
                uid=uid,
                model_type_name=model_type.__name__,
                prop_name=prop_name,
                prop=prop
            )

        return uid

    def write_dynamic_to_influx(
        self, uid: UID, model_type_name: str, prop_name: str, prop: Dynamic
    ):
        points = []
        for timepoint in prop.points:
            tags = {
                UID_FIELD: uid
            }
            value = timepoint.value

            time = datetime.datetime.fromtimestamp(
                timepoint.timestamp
            )

            if isinstance(value, Tensor):
                series = value.to_series().reset_index()
                for idx, row in series.iterrows():
                    fields = {
                        f"{prop_name}": row[value.name]
                    }
                    tags = tags | {
                        f"{prop_name}.{idx_name}": row[idx_name]
                        for idx_name in value.index_names
                    }
                    points.append(
                        {
                            "time": time,
                            "measurement": model_type_name,
                            "fields": fields,
                            "tags": tags
                        }
                    )
            else:
                fields = {
                    prop_name: value
                }
                points.append(
                    {
                        "time": time,
                        "measurement": model_type_name,
                        "fields": fields,
                        "tags": tags
                    }
                )
        self.influx.write_points(points)

    def delete_model(
            self,
            model_type: Type[StateModel],
            uid: UID) -> None:
        node = self.get_node(uid=uid)
        self.graph.delete(node)

        self.influx.delete_series(
            measurement=model_type.__name__,
            tags={
                UID_FIELD: uid
            }
        )

    def overwrite_static_props(
            self,
            uid: UID,
            props: Dict[str, StaticTypes]) -> None:
        node = self.get_node(uid=uid)
        node.update(props)
        self.graph.push(node)

    def overwrite_dynamic_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, Optional[Dynamic]]) -> None:
        for prop_name, prop in props.items():
            self.influx.delete_series(
                measurement=model_type.__name__,
                tags={
                    UID_FIELD: uid,
                    "_field": prop_name
                }
            )
            self.write_dynamic_to_influx(
                uid=uid,
                model_type_name=model_type.__name__,
                prop_name=prop_name,
                prop=prop
            )

    def extend_dynamic_props(
            self,
            uid: UID,
            model_type: Type[StateModel],
            props: Dict[str, Optional[Dynamic]]) -> None:

        for prop_name, prop in props.items():
            self.write_dynamic_to_influx(
                uid=uid,
                model_type_name=model_type.__name__,
                prop_name=prop_name,
                prop=prop
            )

    def delete_all_relationships(
            self,
            from_uid: UID,
            rel_from_name: str) -> List[UID]:

        ret = self.graph.run(
            f"MATCH (:{LIVE_LABEL} {{{UID_FIELD}:\"{from_uid}\"}})"
            f"-[r {{from_field: \"{rel_from_name}\"}}]->(n:{LIVE_LABEL})"
            f" DELETE r"
            f" RETURN n.{UID_FIELD}"
        )
        return [r.get(f"n.{UID_FIELD}") for r in ret]

    def create_relationships(self, from_uid: UID, inspector: RelInspector) -> None:
        node = self.get_node(uid=from_uid)

        new_to_refs = (
            inspector.to_refs
            if inspector.to_refs is not None
            else []
        )

        for to_ref in new_to_refs:
            to_node = self.get_node(uid=to_ref.uid)
            rel_props = {
                "from_field": inspector.from_field_name
            }

            if inspector.to_field_name is not None:
                rel_props["to_field"] = inspector.to_field_name

            rel = Relationship(
                node, inspector.rel_type, to_node,
                **rel_props
            )

            if not self.graph.exists(rel):
                self.graph.create(rel)

    def get_model_by_uid(
            self,
            uid: UID,
            model_type: Type[StateModel]
    ) -> StateModel:
        node = self.get_node(uid=uid)

        data = dict(node)

        for field_name, field in model_type.__fields__.items():
            if issubclass(field.type_, Dynamic):
                point_type = field.type_._point_type
                if issubclass(point_type, Tensor):
                    pa_schema = point_type.pa_schema
                    index_names_string = ",".join(
                        [
                            f"{field_name}.{idx_name}"
                            for idx_name in pa_schema.index.names
                        ]
                    )
                    query = (
                        f"SELECT {field_name},{index_names_string}"
                        f" FROM {model_type.__name__}"
                        f" WHERE {UID_FIELD}='{uid}'"
                    )

                    points = list(self.influx.query(query).get_points(
                        measurement=model_type.__name__
                    ))

                    time_groups = pd.DataFrame(data=points).groupby('time')
                    timepoints = []
                    breakpoint()
                    for timestamp, time_group in time_groups:
                        df = time_group.drop('time', axis=1)
                        df.columns = df.columns.map(
                            lambda x: x.split('.')[1] if '.' in x else x
                        )
                        df.set_index(pa_schema.index.names, inplace=True)

                        timepoint = TimePoint(
                            timestamp=int(isoparse(timestamp).timestamp()),
                            value=point_type(
                                data=list(df.to_numpy().flatten())
                            )
                        )

                        timepoints.append(timepoint)
                    data[field_name] = field.type_(
                        points=timepoints
                    )

        return resolve_model(values=data)

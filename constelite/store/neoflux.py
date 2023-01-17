from typing import Optional, Dict, List, Tuple, Type
from uuid import uuid4

import json

import datetime
from dateutil.parser import isoparse

import pandas as pd

from inspect import getmro

from pydantic import Field, BaseModel

from constelite.store import BaseStore

from constelite.models import (
    StateModel, StaticTypes, Dynamic, UID,
    RelInspector, resolve_model, Tensor, TimePoint, Ref
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

    def uid_exists(self, uid: UID, model_type: Type[StateModel]) -> bool:
        return self.graph.nodes.match(
                LIVE_LABEL,
                **{UID_FIELD: uid}
            ).exists()

    def get_node(self, uid: UID) -> Node:
        return self.graph.nodes.match(
                LIVE_LABEL,
                **{UID_FIELD: uid}
            ).first()

    def get_relations(self, node) -> Dict[str, Ref]:
        rel_dict = {}
        res = self.graph.run(
            f"MATCH (n {{{UID_FIELD}:\"{node[UID_FIELD]}\"}})"
            "-[r]->(m)"
            f" RETURN r.from_field, m.{UID_FIELD}, m.model_name"
        ).data()

        for row in res:
            from_field_name = row['r.from_field']

            if from_field_name not in rel_dict:
                rel_dict[from_field_name] = []
            rel_dict[from_field_name].append(
                self.generate_ref(
                    uid=row[f"m.{UID_FIELD}"],
                    state_model_name=row["m.model_name"]
                )
            )

        res = self.graph.run(
            "MATCH (m)"
            f"-[r]->(n {{{UID_FIELD}:\"{node[UID_FIELD]}\"}})"
            " WHERE EXISTS(r.to_field)"
            f" RETURN r.to_field, m.{UID_FIELD}, m.model_name"
        ).data()

        for row in res:
            to_field_name = row['r.to_field']

            if to_field_name not in rel_dict:
                rel_dict[to_field_name] = []
            rel_dict[to_field_name].append(
                self.generate_ref(
                    uid=row[f"m.{UID_FIELD}"],
                    state_model_name=row["m.model_name"]
                )
            )

        return rel_dict

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

        for prop_name, prop in static_props.items():
            if isinstance(prop, BaseModel):
                static_props[prop_name] = prop.json()

        node = Node(*labels, **static_props)

        tx = self.graph.begin()
        tx.create(node)
        self.graph.commit(tx)

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
        if prop is None:
            return

        points = []
        for timepoint in prop.points:
            tags = {
                UID_FIELD: uid
            }
            value = timepoint.value

            time = datetime.datetime.utcfromtimestamp(
                timepoint.timestamp
            )

            if isinstance(value, Tensor):
                series = value.to_series().reset_index()
                for idx in range(len(series)):
                    fields = {
                        f"{prop_name}": series.iloc[idx:idx+1][value.name].iloc[0]
                    }
                    tags = tags | {
                        f"{prop_name}.{idx_name}": series.iloc[idx:idx+1][idx_name].iloc[0]
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

    def influx_to_dynamic(
            self,
            uid: UID,
            model_type: Type,
            field_name: str,
            point_type: Type,
    ) -> Dynamic:
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

            if len(points) == 0:
                return None
            else:
                df = pd.DataFrame(data=points)

                df.columns = df.columns.map(
                    lambda x: x.split('.')[1] if '.' in x else x
                )

                for schema_idx in pa_schema.index.indexes:
                    df[schema_idx.name] = df[schema_idx.name].astype(
                        pa_schema.index.indexes[0].dtype.type
                    )

                df.set_index(pa_schema.index.names, inplace=True)

                time_groups = df.groupby('time')
                timepoints = []

                for timestamp, time_group in time_groups:
                    df = time_group.drop('time', axis=1)
                    timepoint = TimePoint(
                        timestamp=int(isoparse(timestamp).timestamp()),
                        value=point_type.from_series(df[field_name])
                    )

                    timepoints.append(timepoint)
        else:
            query = (
                f"SELECT {field_name} FROM {model_type.__name__}"
                f" WHERE {UID_FIELD}='{uid}'"
            )

            points = list(self.influx.query(query).get_points(
                measurement=model_type.__name__
            ))

            if len(points) == 0:
                return None

            timepoints = [
                TimePoint(
                    timestamp=int(isoparse(point['time']).timestamp()),
                    value=point_type(point[field_name])
                )
                for point in points
            ]

        return Dynamic[point_type](points=timepoints)

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
            model_type: Type[StateModel],
            props: Dict[str, StaticTypes]) -> None:
        node = self.get_node(uid=uid)

        for prop_name, prop in props.items():
            if isinstance(prop, BaseModel):
                props[prop_name] = prop.json()

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
            from_model_type: Type[StateModel],
            rel_from_name: str) -> List[UID]:

        ret = self.graph.run(
            f"MATCH (:{LIVE_LABEL} {{{UID_FIELD}:\"{from_uid}\"}})"
            f"-[r {{from_field: \"{rel_from_name}\"}}]->(n:{LIVE_LABEL})"
            f" DELETE r"
            f" RETURN n.{UID_FIELD}"
        )
        return [r.get(f"n.{UID_FIELD}") for r in ret]

    def create_relationships(
            self,
            from_uid: UID,
            from_model_type: Type[StateModel],
            inspector: RelInspector) -> None:
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

    def get_state_by_uid(
            self,
            uid: UID,
            model_type: Type[StateModel]
    ) -> StateModel:
        node = self.get_node(uid=uid)
        rels = self.get_relations(node=node)
        data = dict(node)

        for field_name, field in model_type.__fields__.items():
            if issubclass(field.type_, Dynamic):
                point_type = field.type_._point_type
                data[field_name] = self.influx_to_dynamic(
                    uid=uid,
                    model_type=model_type,
                    field_name=field_name,
                    point_type=point_type,
                )
            elif (
                    issubclass(field.type_, BaseModel)
                    and field_name in data
            ):
                json_str = data[field_name]
                if json_str is not None:
                    data[field_name] = field.type_(
                        **json.loads(node[field_name])
                    )

        return resolve_model(values=data | rels)

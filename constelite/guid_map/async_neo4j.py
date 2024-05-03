from typing import Optional

from uuid import uuid4

from pydantic.v1 import UUID4, Field

from constelite.models import UID
from constelite.guid_map.async_base import AsyncGUIDMap
from constelite.store import BaseStore, NeoConfig

from constelite.utils import to_thread

from py2neo import Graph, Node, Relationship


STORE_LABEL = "_Store"
ENTITY_LABEL = "_Entity"
STORED_REL_LABEL = "_STORED_IN"


class AsyncNeoGUIDMap(AsyncGUIDMap):
    config: NeoConfig
    graph: Optional[Graph] = Field(exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data):
        super().__init__(**data)
        self.graph = Graph(self.config.url, auth=self.config.auth)

    def get_or_create_store_node(self, store: BaseStore):
        store_uid = str(store.uid)

        store_node = self.graph.nodes.match(
            STORE_LABEL,
            uid=store_uid
        ).first()

        if store_node is None:
            store_node = Node(STORE_LABEL, uid=store_uid)
            tx = self.graph.begin()
            tx.create(store_node)
            self.graph.commit(tx)

        return store_node
    @to_thread
    def guid_exists(self, guid: UUID4) -> bool:
        entity_node = self.graph.nodes.match(
            ENTITY_LABEL,
            guid=str(guid)
        ).first()

        return entity_node is not None
    @to_thread
    def get_guid(self, uid: UID, store: BaseStore) -> Optional[UUID4]:
        guid = self.graph.run(
            f"MATCH (s:{STORE_LABEL} {{uid: \"{store.uid}\"}})"
            f"<-[r {{uid: \"{uid}\"}}]-(e:{ENTITY_LABEL})"
            f"RETURN e.guid"
        ).evaluate()

        if guid is not None:
            return UUID4(guid)
        else:
            return None
    @to_thread
    def link_uid(self, uid, guid: UUID4, store: BaseStore) -> None:
        store_node = self.get_or_create_store_node(store=store)
        entity_node = self.graph.nodes.match(
            ENTITY_LABEL,
            guid=str(guid)
        ).first()

        if entity_node is None:
            raise ValueError(f'Could not find entity {guid} in the guid map')

        rel = Relationship(
            entity_node,
            STORED_REL_LABEL,
            store_node,
            uid=uid
        )
        tx = self.graph.begin()
        tx.create(rel)
        self.graph.commit(tx)
    @to_thread
    def create_guid(self, uid: UID, store: BaseStore) -> UUID4:
        store_node = self.get_or_create_store_node(store=store)

        entity_node = Node(ENTITY_LABEL, guid=str(uuid4()))
        rel = Relationship(
            entity_node,
            STORED_REL_LABEL,
            store_node,
            uid=str(uid)
        )
        tx = self.graph.begin()
        tx.create(entity_node)
        tx.create(rel)
        self.graph.commit(tx)

        return UUID4(entity_node['guid'])
    @to_thread
    def get_uid(self, guid: UUID4, store: BaseStore):
        return self.graph.run(
            f"MATCH (s:{STORE_LABEL} {{uid: \"{store.uid}\"}})"
            f"<-[r]-(e:{ENTITY_LABEL} {{guid: \"{str(guid)}\"}})"
            f"RETURN r.uid"
        ).evaluate()
    @to_thread
    def delete_uid(self, uid: UID, store: "BaseStore"):
        self.graph.run(
            f"MATCH (s:{STORE_LABEL} {{uid: \"{store.uid}\"}})"
            f"<-[r {{uid: \"{uid}\"}}]-(e:{ENTITY_LABEL})"
            f"DELETE r"
        )

from pydantic.v1 import UUID4

from uuid import uuid4

from constelite.guid_map.async_base import AsyncGUIDMap
from constelite.models import UID

class MemoryGUID(AsyncGUIDMap):

    guid_map: dict[UUID4, dict[str, UUID4]] = {}
    
    async def get_guid(self, uid: UID, store: "BaseStore") -> UUID4 | None:
        """Finds entity by given uid in the given store and returns its
        guid.
        """
        for guid, guid_record in self.guid_map.items():
            for store_uid, record_uid in guid_record.items():
                if store_uid == store.uid and record_uid == uid:
                    return guid
        return None
        
    async def guid_exists(self, guid: UUID4) -> bool:
        """Checks if entity with the given guid exists in the map.

        Returns:
            True: if entity with the given guid exists
            Flase: if entity with the given guid does not exist
        """
        return guid in self.guid_map

    async def link_uid(self, uid, guid: UUID4, store: "BaseStore") -> None:
        """Links store record with given uid in the given store with an
        existing entity with the given guid.
        """
        self.guid_map[guid].update({store.uid: uid})

    async def create_guid(self, uid: UID, store: "BaseStore") -> UUID4:
        """Creates a new entity, links it with a store record with the
        given uid in the given store.

        Returns:
            GUID of the new entity.
        """
        new_guid = uuid4()
        self.guid_map[new_guid] = {store.uid: uid}
        return new_guid

    async def get_uid(self, guid: UUID4, store: "BaseStore") -> UID:
        """Gets uid of the record that corresponds to the entity with the
        given guid in the given store.
        """
        return self.guid_map[guid].get(store.uid)

    async def delete_uid(self, uid: UID, store: "BaseStore") -> None:
        """Deletes store record with the given uid and store from the map.
        """

        for guid, guid_record in self.guid_map.items():
            found_guid = False
            for store_uid, record_uid in guid_record.items():
                if store_uid == store.uid and record_uid == uid:
                    found_guid = True
                    break
            if found_guid:
                guid_record.pop(store.uid)
                break
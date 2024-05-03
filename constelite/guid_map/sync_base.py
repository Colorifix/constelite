from typing import Optional

from pydantic.v1 import UUID4, BaseModel

from constelite.models import UID


class GUIDMap(BaseModel):
    def get_guid(self, uid: UID, store: "BaseStore") -> Optional[UUID4]:
        """Finds entity by given uid in the given store and returns its
        guid.
        """
        raise NotImplementedError

    def guid_exists(self, guid: UUID4) -> bool:
        """Checks if entity with the given guid exists in the map.

        Returns:
            True: if entity with the given guid exists
            Flase: if entity with the given guid does not exist
        """
        raise NotImplementedError

    def link_uid(self, uid, guid: UUID4, store: "BaseStore") -> None:
        """Links store record with given uid in the given store with an
        existing entity with the given guid.
        """
        raise NotImplementedError

    def create_guid(self, uid: UID, store: "BaseStore") -> UUID4:
        """Creates a new entity, links it with a store record with the
        given uid in the given store.

        Returns:
            GUID of the new entity.
        """
        raise NotImplementedError

    def get_uid(self, guid: UUID4, store: "BaseStore") -> UID:
        """Gets uid of the record that corresponds to the entity with the
        given guid in the given store.
        """
        raise NotImplementedError

    def delete_uid(self, uid: UID, store: "BaseStore") -> None:
        """Deletes store record with the given uid and store from the map.
        """
        raise NotImplementedError

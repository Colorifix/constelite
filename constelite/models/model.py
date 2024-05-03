from typing import ForwardRef
from constelite.utils import resolve_forward_ref
from constelite.models.auto_resolve import AutoResolveBaseModel


class StateModel(AutoResolveBaseModel):
    """Base class for all state models.
    """
    @classmethod
    def fix_backrefs(cls):
        """
        Fixes all `ForwardRef`s in the model's `Backref` fields to the actual model class.
        """
        from constelite.models.relationships import Backref

        for _, field_info in cls.__fields__.items():
            MT = field_info.type_
            if issubclass(MT, Backref):
                MTT = MT.__fields__['model_type'].type_
                if isinstance(MTT, ForwardRef):
                    resolved_type = resolve_forward_ref(MTT, StateModel)
                    if resolved_type is not None:
                        field_info.type_ = Backref[resolved_type]

from enum import Enum


class SignalType(str, Enum):
    ENTRY = "entry"
    RE_ENTRY = "re_entry"
    UPDATE = "update"
    CLOSE = "close"
    CANCEL = "cancel"
    NONE = "none"

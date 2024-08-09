from enum import Enum

class ArchiveIndices:
    LINK = 3
    TITLE = 4
    CHANNEL = 5
    STATE = 7
    ALT_LINK = 8
    FOUND = 9
    NOTES = 10

class States(Enum):
    NON_EMBEDDABLE = ('non-embedable', 'non-embeddable')
    UNAVAILABLE = ('unavailable', 'deleted', 'private', 'tos deleted')
    
    AGE_RESTRICTED = ('age-restricted',)
    BLOCKED = ('blocked',)

    @classmethod
    def get(cls, value: str):
        for state in cls:
            if value.lower() in state.value:
                return state
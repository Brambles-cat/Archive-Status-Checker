from enum import Enum

class ArchiveIndices:
    LINK = 3
    TITLE = 4
    CHANNEL = 5
    STATE = 7
    ALT_LINK = 8
    FOUND = 9
    NOTES = 10

# Todo, find a way to keep non detectable states such as muted or blurred when present with other states
class States(Enum):
    # Spelling err yes I know
    NON_EMBEDDABLE = ('non-embedable', 'non-embeddable')
    # Todo: ask what the difference between deleted, private and unavailable is
    UNAVAILABLE = ('unavailable', 'deleted', 'private', 'tos deleted')
    # DELETED = 'deleted'
    # PRIVATE = 'private'
    
    AGE_RESTICTED = ('age-restricted',)
    BLOCKED = ('blocked',)

    @classmethod
    def get(cls, value: str):
        for state in cls:
            if value.lower() in state.value:
                return state
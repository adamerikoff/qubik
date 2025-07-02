import enum
import typing

class State(enum.Enum):
    PENDING   = 0
    SCHEDULED = 1
    RUNNING   = 2
    COMPLETED = 3
    FAILED    = 4

state_transition_map: typing.Dict[State, typing.List[State]] = {
    State.PENDING:   [State.SCHEDULED],
    State.SCHEDULED: [State.SCHEDULED, State.RUNNING, State.FAILED],
    State.RUNNING:   [State.RUNNING, State.COMPLETED, State.FAILED],
    State.COMPLETED: [],
    State.FAILED:    [],
}

def state_contains(states: typing.List[State], state: State) -> bool:
    for s in states:
        if s == state:
            return True
    return False

def valid_state_transition(src: State, dst: State) -> bool:
    valid_next_states = state_transition_map.get(src, [])
    return state_contains(valid_next_states, dst)
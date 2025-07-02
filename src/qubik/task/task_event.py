import uuid
import datetime
import logging

from .task import State, Task

logger = logging.getLogger(__name__)

class TaskEvent:
    def __init__(self,
                 event_id: uuid.UUID,
                 state: State, # This is the TARGET state for the task
                 timestamp: datetime.datetime,
                 task: Task):
        self.event_id: uuid.UUID = event_id
        self.state: State = state
        self.timestamp: datetime.datetime = timestamp
        self.task: Task = task

        logger.info(
            "TaskEvent created: event_id=%s, target_state=%s, timestamp=%s, task_uuid=%s, task_name='%s'",
            self.event_id,
            self.state.name,
            self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            self.task.task_uuid,
            self.task.name
        )

    def __repr__(self) -> str:
        return (f"TaskEvent(id={self.event_id.hex[:8]}..., "
                f"target_state={self.state.name}, "
                f"timestamp={self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}, "
                f"task_name='{self.task.name}')")
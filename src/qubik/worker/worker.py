import uuid
import typing
import collections
import logging

from qubik import Task, TaskEvent

logger = logging.getLogger(__name__)

class Worker:
    def __init__(self, name: str):
        self.name: str = name
        self.queue: collections.deque[TaskEvent] = collections.deque()
        self.db: typing.Dict[uuid.UUID, Task] = {}
        
        logger.info("Initializing Worker: name='%s'", name)

    def __repr__(self) -> str:
        return (f"Worker(name='{self.name}', "
                f"tasks_in_queue={len(self.queue)}, "
                f"tasks_managed={len(self.db)})")

    def collect_stats(self) -> None:
        logger.debug("collect_stats: Collecting stats for worker='%s'", self.name)
        print(f"Worker '{self.name}': I will collect stats.")

    def run_task(self, task_event: TaskEvent) -> None:
        logger.info("run_task: Processing task_event (task='%s', target_state='%s')", task_event.task.name, task_event.state.name)
        print(f"Worker '{self.name}': I will start or stop task '{task_event.task.name}' "f"based on target state '{task_event.state.name}'.")

    def _start_task(self, task_to_start: Task) -> None:
        logger.debug("_start_task: Starting task_id=%s ('%s')", task_to_start.task_uuid, task_to_start.name)
        print(f"Worker '{self.name}': I will start task '{task_to_start.name}'.")

    def _stop_task(self, task_to_stop: Task) -> None:
        logger.debug("_stop_task: Stopping task_id=%s ('%s')", 
                       task_to_stop.task_uuid, task_to_stop.name)
        print(f"Worker '{self.name}': I will stop task '{task_to_stop.name}'.")
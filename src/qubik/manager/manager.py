import uuid
import collections
import typing
import logging

from qubik import Task, TaskEvent

logger = logging.getLogger(__name__)

class Manager:
    def __init__(self, name: str = "main-manager"):
        self.name: str = name
        self.pending_tasks: collections.deque[Task] = collections.deque()
        self.task_db: typing.Dict[uuid.UUID, Task] = {}
        self.event_db: typing.Dict[uuid.UUID, typing.List[TaskEvent]] = collections.defaultdict(list)
        self.workers: typing.List[str] = []
        self.worker_task_map: typing.Dict[str, typing.List[uuid.UUID]] = {}
        self.task_worker_map: typing.Dict[uuid.UUID, str] = {}

        logger.info("Initializing Manager: name='%s'", name)

    def select_worker(self, task: Task) -> typing.Optional[str]:
        logger.debug("select_worker: Selecting worker for task_id=%s", task.task_uuid)
        # TODO: Implement logic
        return None

    def update_tasks(self) -> None:
        logger.debug("update_tasks: Updating %d pending tasks", len(self.pending_tasks))
        # TODO: Implement logic

    def send_work(self, task: Task, worker_name: str) -> None:
        logger.debug(
            "send_work: Sending task_id=%s to worker='%s'",
            task.task_uuid,
            worker_name
        )
        # TODO: Implement logic

    def __repr__(self) -> str:
        return (
            f"Manager(name='{self.name}', "
            f"pending_tasks={len(self.pending_tasks)}, "
            f"total_tasks={len(self.task_db)}, "
            f"registered_workers={len(self.workers)})"
        )
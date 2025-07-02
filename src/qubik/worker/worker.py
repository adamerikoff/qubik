import uuid
import typing
import collections
import logging
import datetime

from qubik import Task, TaskEvent, DockerResult, Config, Docker, State, valid_state_transition

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

    def add_task(self, task_to_add: Task) -> None:
        self.queue.append(task_to_add)
        logger.info(f"Task '{task_to_add.name}' (UUID: {task_to_add.task_uuid.hex[:8]}) added to queue.")

    def run_task(self) -> DockerResult:
        if not self.queue:
            logger.debug("No tasks in the queue for worker '%s'.", self.name)
            return DockerResult(action="run_task", container_id=None, 
            result="queue_empty")
        
        task_queued: Task = self.queue.popleft()
        logger.info(f"Dequeued task '{task_queued.name}' (UUID: {task_queued.task_uuid.hex[:8]}) with desired state: {task_queued.state.name}.")

        task_persisted: typing.Optional[Task] = self.db.get(task_queued.task_uuid)

        if task_persisted is None:
            logger.info(f"Task '{task_queued.name}' (UUID: {task_queued.task_uuid.hex[:8]}) not found in DB. Assuming initial state PENDING.")
            current_state_for_transition = State.PENDING
        else:
            current_state_for_transition = task_persisted.state
            logger.debug(f"Task '{task_queued.name}' (UUID: {task_queued.task_uuid.hex[:8]}) found in DB. Current state: {task_persisted.state.name}.")

        if not valid_state_transition(current_state_for_transition, task_queued.state):
            err_msg = f"Invalid state transition for task '{task_queued.name}' (UUID: {task_queued.task_uuid.hex[:8]}): from {current_state_for_transition.name} to {task_queued.state.name}."
            logger.error(err_msg)

            if task_persisted:
                task_persisted.state = State.FAILED
                self.db[task_persisted.task_uuid] = task_persisted
            else: 
                task_queued.state = State.FAILED
                self.db[task_queued.task_uuid] = task_queued
            return DockerResult(action="run_task", container_id=None, error=ValueError(err_msg), result="invalid_state_transition")
        
        if task_queued.state == State.SCHEDULED:
            logger.info(f"Worker '{self.name}': Starting task '{task_queued.name}' (UUID: {task_queued.task_uuid.hex[:8]}) as desired state is SCHEDULED.")
            result = self.start_task(task_queued)
        elif task_queued.state == State.COMPLETED:
            logger.info(f"Worker '{self.name}': Stopping task '{task_queued.name}' (UUID: {task_queued.task_uuid.hex[:8]}) as desired state is COMPLETED.")
            result = self.stop_task(task_queued)
        else:
            err_msg = f"Worker '{self.name}': Unhandled desired state '{task_queued.state.name}' for task '{task_queued.name}' (UUID: {task_queued.task_uuid.hex[:8]})."
            logger.error(err_msg)

            if task_persisted:
                task_persisted.state = State.FAILED
                self.db[task_persisted.task_uuid] = task_persisted
            else:
                task_queued.state = State.FAILED
                self.db[task_queued.task_uuid] = task_queued
            result = DockerResult(action="run_task", container_id=None, error=ValueError(err_msg), result="unhandled_desired_state")
        
        return result

    def start_task(self, task_to_start: Task) -> DockerResult:
        logger.debug("start_task: Starting task_id=%s ('%s')", task_to_start.task_uuid, task_to_start.name)

        task_to_start.start_time = datetime.datetime.now(datetime.timezone.utc)

        config = Config.from_task(task_to_start)
        docker_client_wrapper = Docker(config)

        result: DockerResult
        try:
            result = docker_client_wrapper.run()
        except Exception as e:
            logger.critical(f"An unhandled exception occurred when trying to run Docker for task '{task_to_start.name}': {e}", exc_info=True)
            task_to_start.state = State.FAILED
            self.db[task_to_start.task_uuid] = task_to_start
            return DockerResult(action="start", container_id=None, error=e, result="worker_internal_error")
        
        if result.error:
            logger.error("Error running task '%s' (UUID: %s): %s - Result: %s", task_to_start.name, task_to_start.task_uuid, result.error, result.result)
            task_to_start.state = State.FAILED
            if result.container_id:
                task_to_start.container_id = result.container_id 
            self.db[task_to_start.task_uuid] = task_to_start
            return result
        
        task_to_start.container_id = result.container_id
        task_to_start.state = State.RUNNING

        self.db[task_to_start.task_uuid] = task_to_start 
        
        logger.info(f"Worker '{self.name}': Started task '{task_to_start.name}' (Container ID: {task_to_start.container_id}).")
        return result

    def stop_task(self, task_to_stop: Task) -> DockerResult:
        logger.debug("stop_task: Stopping task_id=%s ('%s')", task_to_stop.task_uuid, task_to_stop.name)
        logger.info(f"Worker '{self.name}': I will stop task '{task_to_stop.name}'.")

        if not task_to_stop.container_id:
            logger.warning(f"No container ID found for task '{task_to_stop.name}' (UUID: {task_to_stop.task_uuid}). Cannot stop.")
            task_to_stop.state = State.FAILED
            self.db[task_to_stop.task_uuid] = task_to_stop
            return DockerResult(action="stop", container_id=None, error=ValueError("No container ID to stop for this task"), result="no_container_id")

        config = Config.from_task(task_to_stop)
        docker_client_wrapper = Docker(config, initial_container_id=task_to_stop.container_id)

        result: DockerResult = docker_client_wrapper.stop() 

        if result.error:
            logger.error("Error stopping container '%s' for task '%s' (UUID: %s): %s - Result: %s", task_to_stop.container_id, task_to_stop.name, task_to_stop.task_uuid, result.error, result.result)
            task_to_stop.state = State.FAILED
            task_to_stop.container_id = result.container_id 
        else:
            logger.info("Stopped and removed container '%s' for task '%s' (UUID: %s)", task_to_stop.container_id, task_to_stop.name, task_to_stop.task_uuid)
            task_to_stop.container_id = None 

        task_to_stop.finish_time = datetime.datetime.now(datetime.timezone.utc)
        task_to_stop.state = State.COMPLETED 

        self.db[task_to_stop.task_uuid] = task_to_stop
        return result




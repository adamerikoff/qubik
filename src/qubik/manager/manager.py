import uuid
import collections
import typing
import logging
import httpx
import asyncio
import time

from fastapi import status

from qubik import Task, TaskEvent, State, task_event_to_api_schema, TaskEventApiSchema, TaskApiSchema, ErrorResponse, api_schema_to_task

logger = logging.getLogger(__name__)

class Manager:
    def __init__(self, workers: typing.List[str] = None, name: str = "main-manager", http_client: httpx.AsyncClient = None):
        self.name: str = name
        self.pending_events: collections.deque[TaskEvent] = collections.deque()
        self.task_db: typing.Dict[uuid.UUID, Task] = {}

        self.event_db: typing.Dict[uuid.UUID, TaskEvent] = {}

        self.workers: typing.List[str] = workers if workers is not None else []

        self.worker_task_map: typing.Dict[str, typing.List[uuid.UUID]] = {}

        for worker_address in self.workers:
            self.worker_task_map[worker_address] = []
            
        self.task_worker_map: typing.Dict[uuid.UUID, str] = {}

        self.last_worker = 0
        # Use httpx.AsyncClient for asynchronous operations
        self.http_client: httpx.AsyncClient = http_client if http_client else httpx.AsyncClient(timeout=10.0)

        self._stop_event_update_tasks = asyncio.Event()
        self._stop_event_process_tasks = asyncio.Event()

        logger.info("Initializing Manager: name='%s', initial_workers=%s", self.name, self.workers)

    def add_worker_address(self, worker_address: str) -> None:
        if worker_address not in self.workers:
            self.workers.append(worker_address)
            # You might want to initialize a new entry in worker_task_map for this new worker
            if worker_address not in self.worker_task_map:
                self.worker_task_map[worker_address] = []
            logger.info("Added worker address %s to manager's list and initialized task map.", worker_address)
        else:
            logger.debug("Worker address %s already present in manager's list.", worker_address)
            
    async def update_tasks(self) -> None:
        logger.debug("update_tasks: Updating tasks from workers.")
        while not self._stop_event_update_tasks.is_set():
            for worker_address in self.workers:
                logger.debug("Checking worker %s for task updates", worker_address)
                url = f"http://{worker_address}/tasks"
                try:
                    resp = await self.http_client.get(url)
                    resp.raise_for_status()

                    tasks_api_schemas = [TaskApiSchema.model_validate(t) for t in resp.json()]

                    for task_api in tasks_api_schemas:
                        logger.debug("Attempting to update task %s from worker %s", task_api.task_id, worker_address)
                        
                        if task_api.task_id not in self.task_db:
                            logger.warning("Task with ID %s found on worker %s but not in manager's task_db. Skipping update for now.", task_api.task_id, worker_address)
                            continue
                        
                        local_task = self.task_db[task_api.task_id]

                        if local_task.state.value != task_api.state:
                            local_task.state = State(task_api.state)
                            logger.info("Task %s state updated to %s based on worker %s.", task_api.task_id, local_task.state.name, worker_address)
                        
                        if task_api.start_time:
                            local_task.start_time = task_api.start_time
                        if task_api.finish_time:
                            local_task.finish_time = task_api.finish_time
                        if task_api.container_id:
                            local_task.container_id = task_api.container_id
                        
                except httpx.RequestError as e:
                    logger.error("Error connecting to worker %s during update: %s", worker_address, e)
                except httpx.HTTPStatusError as e:
                    logger.error("HTTP error from worker %s during update: Status %d - %s",
                                 worker_address, e.response.status_code, e.response.text)
                except Exception as e:
                    logger.exception("An unexpected error occurred during task update from worker %s:", worker_address)
            
            await asyncio.sleep(5) # Poll every 5 seconds

    async def process_tasks(self) -> None:
        logger.debug("process_tasks: Processing pending tasks.")
        while not self._stop_event_process_tasks.is_set():
            if self.pending_events:
                await self.send_work()
            else:
                logger.debug("No pending tasks to process.")
            await asyncio.sleep(1) # Check every 1 second

    def stop_background_tasks(self):
        logger.info("Signaling Manager background tasks to stop.")
        self._stop_event_update_tasks.set()
        self._stop_event_process_tasks.set()


    def select_worker(self) -> str:
        logger.debug("select_worker: Selecting worker for tasks")
        if not self.workers:
            logger.warning("No workers registered to select from.")
            return "" 

        # Round-robin selection
        selected_worker = self.workers[self.last_worker]
        self.last_worker = (self.last_worker + 1) % len(self.workers)
        
        logger.debug("select_worker: Selected worker=%s", selected_worker)
        return selected_worker
    
    async def send_work(self) -> None:
        if not self.pending_events:
            logger.info("No work in the pending queue.")
            return

        worker_address: str = self.select_worker()
        if not worker_address:
            logger.error("Failed to select a worker. Cannot send work.")
            return
        
        task_event_to_send: TaskEvent = self.pending_events.popleft()
        task_to_send = task_event_to_send.task
        logger.info("Pulled task event %s (for task %s - %s) off pending queue", task_event_to_send.event_id, task_to_send.task_uuid, task_to_send.name)

        self.event_db[task_to_send.task_uuid] = task_event_to_send

        if worker_address not in self.worker_task_map:
            self.worker_task_map[worker_address] = []
        self.worker_task_map[worker_address].append(task_to_send.task_uuid)
        self.task_worker_map[task_to_send.task_uuid] = worker_address

        task_to_send.state = State.SCHEDULED # Mark as scheduled before sending

        self.task_db[task_to_send.task_uuid] = task_to_send

        api_task_event: TaskEventApiSchema = task_event_to_api_schema(task_event_to_send)
        
        data_json = api_task_event.model_dump_json(by_alias=True)

        url = f"http://{worker_address}/tasks"

        try:
            resp = await self.http_client.post(url, headers={"Content-Type": "application/json"}, content=data_json)
            resp.raise_for_status()

            if resp.status_code == status.HTTP_201_CREATED:
                returned_task_api: TaskApiSchema = TaskApiSchema.model_validate_json(resp.text)
                logger.info("Successfully sent task %s to worker %s. Worker returned: %s", returned_task_api.task_id, worker_address, returned_task_api)

                updated_domain_task = api_schema_to_task(returned_task_api)
                if updated_domain_task.task_uuid in self.task_db:
                    self.task_db[updated_domain_task.task_uuid] = updated_domain_task
                    logger.debug("Manager's task_db updated for task %s with worker's response.", updated_domain_task.task_uuid)

            else:
                logger.warning("Received unexpected status code %d from worker %s. Response: %s",
                                resp.status_code, worker_address, resp.text)
                self.pending_events.appendleft(task_event_to_send)
                logger.info("Task event %s re-enqueued due to unexpected worker response.", task_event_to_send.event_id)

        except httpx.RequestError as e:
            logger.error("Error connecting to worker %s at %s: %s", worker_address, url, e)
            self.pending_events.appendleft(task_event_to_send)
            logger.info("Task event %s re-enqueued due to network error.", task_event_to_send.event_id)
        except httpx.HTTPStatusError as e:
            logger.error("HTTP error from worker %s at %s: Status %d - %s",
                         worker_address, url, e.response.status_code, e.response.text)
            try:
                err_response = ErrorResponse.model_validate_json(e.response.text)
                logger.error("Worker error response (%d): %s - %s",
                             err_response.http_status_code, err_response.message, getattr(err_response, 'Error', 'N/A'))
            except Exception as decode_err:
                logger.error("Failed to decode error response from worker: %s. Raw response: %s", decode_err, e.response.text)
            
            self.pending_events.appendleft(task_event_to_send) 
            logger.info("Task event %s re-enqueued due to worker HTTP error.", task_event_to_send.event_id)
        except Exception as e:
            logger.exception("An unexpected error occurred while sending work for task event %s:", task_event_to_send.event_id)
            self.pending_events.appendleft(task_event_to_send)

    def add_task_event_to_pending(self, task_event: TaskEvent) -> None:
        self.pending_events.append(task_event)
        logger.info("Added task event %s (for task %s) to pending queue.", task_event.event_id, task_event.task.task_uuid)


    def __repr__(self) -> str:
        return (
            f"Manager(name='{self.name}', "
            f"pending_events={len(self.pending_events)}, "
            f"total_tasks={len(self.task_db)}, "
            f"registered_workers={len(self.workers)})"
        )
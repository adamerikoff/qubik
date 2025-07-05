import logging
import uuid
import typing
import copy
import threading
import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.responses import Response

from .worker import Worker

from qubik import TaskApiSchema, TaskEventApiSchema, task_to_api_schema, api_schema_to_task_event, State, WorkerMetrics

logger = logging.getLogger(__name__)

def create_fastapi_app_for_worker(worker_instance: Worker) -> FastAPI:
    
    # We create a dependency function that always returns our specific worker_instance
    def get_specific_worker() -> Worker:
        return worker_instance

    worker_app_instance = FastAPI(
        title=f"Qubik Worker API for {worker_instance.worker_id}",
        description=f"API for managing tasks on Qubik worker {worker_instance.worker_id}.",
        version="0.1.0",
    )

    # --- Lifespan Event Handler tailored for a specific worker instance ---
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info(f"FastAPI application startup (lifespan) event for worker {worker_instance.worker_id} triggered.")
        
        # Startup logic
        worker_instance.start_metrics_collection(interval_seconds=15)
        logger.info(f"Ensured metrics collection started for worker {worker_instance.worker_id}.")
        
        yield # Application will now start processing requests

        # Shutdown logic (executed after `yield` when the server is shutting down)
        logger.info(f"FastAPI application shutdown (lifespan) event for worker {worker_instance.worker_id} triggered.")
        worker_instance.stop_metrics_collection()
        logger.info(f"Metrics collection gracefully stopped for worker {worker_instance.worker_id}.")
    
    worker_app_instance.router.lifespan_context = lifespan # Attach the lifespan context

    @worker_app_instance.get("/stats", response_model=WorkerMetrics, summary="Get worker performance metrics")
    async def get_stats_handler(worker: Worker = Depends(get_specific_worker)):
        logger.debug(f"Received request to get stats for worker {worker.worker_id}.")
        return worker.current_metrics

    @worker_app_instance.post("/tasks", response_model=TaskApiSchema, status_code=status.HTTP_201_CREATED)
    async def start_task_handler(task_event_api: TaskEventApiSchema, worker: Worker = Depends(get_specific_worker)):
        logger.info(f"Received request to start task event ID: {task_event_api.event_id} for worker {worker.worker_id}")
        try:
            domain_task_event = api_schema_to_task_event(task_event_api)

            worker.add_task(domain_task_event.task)
            logger.info(f"Added task {domain_task_event.task.task_uuid} to worker {worker.worker_id} queue.")

            return task_to_api_schema(domain_task_event.task)

        except Exception as e:
            logger.exception(f"An unexpected error occurred in start_task_handler for worker {worker.worker_id}.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal Server Error: {e}"
            )

    @worker_app_instance.get("/tasks", response_model=typing.List[TaskApiSchema])
    async def get_tasks_handler(worker: Worker = Depends(get_specific_worker)):
        logger.info(f"Received request to get all tasks for worker {worker.worker_id}.")
        try:
            domain_tasks = worker.get_tasks()
            
            api_schemas = [task_to_api_schema(task) for task in domain_tasks]
            
            return api_schemas
        except Exception as e:
            logger.exception(f"An unexpected error occurred in get_tasks_handler for worker {worker.worker_id}.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal Server Error: {e}"
            )

    @worker_app_instance.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def stop_task_handler(task_id: uuid.UUID, worker: Worker = Depends(get_specific_worker)):
        logger.info(f"Received request to stop task with ID: {task_id} for worker {worker.worker_id}")
        try:
            task_to_stop_pointer = worker.db.get(task_id)
            if not task_to_stop_pointer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No task with ID {task_id} found for worker {worker.worker_id}."
                )

            task_copy = copy.deepcopy(task_to_stop_pointer)

            if task_copy.state == State.COMPLETED:
                logger.info(f"Task {task_id} for worker {worker.worker_id} is already in COMPLETED state. No action taken.")
                return Response(status_code=status.HTTP_204_NO_CONTENT)

            task_copy.state = State.COMPLETED 

            worker.add_task(task_copy)
            logger.info(f"Added task {task_id} (state COMPLETED) to worker {worker.worker_id} queue for stopping.")

            return Response(status_code=status.HTTP_204_NO_CONTENT)

        except HTTPException as e:
            raise e
        except Exception as e:
            logger.exception(f"An unexpected error occurred in stop_task_handler for worker {worker.worker_id}.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal Server Error: {e}"
            )
            
    return worker_app_instance

class WorkerApiServer:
    def __init__(self, worker_instance: Worker, host: str = "127.0.0.1", port: int = 8000):
        self.worker = worker_instance
        self.host = host
        self.port = port
        self.fastapi_app = create_fastapi_app_for_worker(self.worker)
        self._server_thread: threading.Thread = None
        self._uvicorn_server = None # To hold the uvicorn Server instance for graceful shutdown

    def start(self):
        if self._server_thread and self._server_thread.is_alive():
            logger.warning(f"Worker API server for {self.worker.worker_id} is already running.")
            return

        config = uvicorn.Config(self.fastapi_app, host=self.host, port=self.port, log_level="info")
        self._uvicorn_server = uvicorn.Server(config)

        def run_api():
            logger.info(f"Starting API for worker {self.worker.worker_id} on {self.host}:{self.port}")
            self._uvicorn_server.run()
            logger.info(f"API for worker {self.worker.worker_id} on {self.host}:{self.port} stopped.")

        self._server_thread = threading.Thread(target=run_api, daemon=True)
        self._server_thread.start()
        logger.info(f"Worker API server for {self.worker.worker_id} started in a new thread.")

    async def stop(self):
        if self._uvicorn_server:
            logger.info(f"Stopping API for worker {self.worker.worker_id}...")
            # This is the graceful way to shut down uvicorn.
            # It needs to be awaited from an async context, which is why we make `stop` async.
            await self._uvicorn_server.shutdown()
            self._server_thread.join(timeout=5) # Wait for the thread to finish
            if self._server_thread.is_alive():
                logger.warning(f"Worker API thread for {self.worker.worker_id} did not terminate gracefully.")
            self._server_thread = None
            self._uvicorn_server = None
            logger.info(f"Worker API for {self.worker.worker_id} stopped.")
        else:
            logger.info(f"Worker API for {self.worker.worker_id} was not running.")

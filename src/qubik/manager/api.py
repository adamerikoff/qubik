import logging
import uuid
import typing
import asyncio
import httpx
import datetime
import threading
import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status, Depends, Response

from .manager import Manager

from qubik import TaskApiSchema, TaskEventApiSchema, ErrorResponse, task_to_api_schema, api_schema_to_task_event, api_schema_to_task, Task, TaskEvent, State

logger = logging.getLogger(__name__)

# This function will create a new FastAPI app instance for a given Manager
def create_fastapi_app_for_manager(manager_instance: Manager) -> FastAPI:
    
    # We create a dependency function that always returns our specific manager_instance
    def get_specific_manager() -> Manager:
        return manager_instance

    manager_app_instance: FastAPI = FastAPI(
        title="Qubik Manager API",
        description="API for managing tasks and workers in the Qubik orchestration system.",
        version="0.1.0",
    )

    # --- Lifespan Event Handler ---
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("FastAPI Manager application startup (lifespan) event triggered.")

        logger.info("Starting Manager background processes...")
        # Start the Manager's long-running processes in separate asyncio tasks
        # These methods are now `async` in manager.py
        manager_app_instance.state.process_tasks_task = asyncio.create_task(manager_instance.process_tasks())
        manager_app_instance.state.update_tasks_task = asyncio.create_task(manager_instance.update_tasks())

        logger.info("Manager background tasks (process_tasks, update_tasks) initiated.")

        yield # Application will now start processing requests

        # Shutdown logic (executed after `yield` when the server is shutting down)
        logger.info("FastAPI Manager application shutdown (lifespan) event triggered.")
        manager_instance.stop_background_tasks() # Signal the manager's internal loops to stop
        
        # Give some time for tasks to gracefully complete if needed, or cancel
        logger.info("Attempting to cancel/wait for manager background tasks...")
        
        # Wait for the tasks to finish after signaling them to stop
        # A timeout is good practice to prevent indefinite hanging
        await asyncio.gather(
            manager_app_instance.state.process_tasks_task,
            manager_app_instance.state.update_tasks_task,
            return_exceptions=True # Don't stop if one task raises an exception
        )
        logger.info("Manager background tasks completed/cancelled.")

        if manager_instance.http_client:
            logger.info("Closing Manager's HTTP client...")
            await manager_instance.http_client.aclose() # Use aclose for AsyncClient
            logger.info("Manager's HTTP client closed.")
        
    manager_app_instance.router.lifespan_context = lifespan

    # --- API Endpoints (moved from manager_api.py) ---

    @manager_app_instance.get("/tasks", response_model=typing.List[TaskApiSchema], summary="Get a list of all tasks known by the manager")
    async def get_tasks_handler(manager: Manager = Depends(get_specific_manager)):
        logger.info("Received GET /tasks request from user.")
        try:
            tasks_from_manager = list(manager.task_db.values())
            api_schemas = [task_to_api_schema(task) for task in tasks_from_manager]
            logger.info(f"Returning {len(api_schemas)} tasks to user.")
            return api_schemas
        except Exception as e:
            logger.exception("An unexpected error occurred in get_tasks_handler (manager).")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal Server Error: {e}"
            )

    @manager_app_instance.post("/tasks", response_model=TaskApiSchema, status_code=status.HTTP_201_CREATED, summary="Create a new task")
    async def start_task_handler(task_event_api: TaskEventApiSchema, manager: Manager = Depends(get_specific_manager)):
        logger.info(f"Received POST /tasks request to start task event ID: {task_event_api.event_id}")
        try:
            domain_task_event = api_schema_to_task_event(task_event_api)
            manager.add_task_event_to_pending(domain_task_event)
            return task_to_api_schema(domain_task_event.task)
        except Exception as e:
            logger.exception("An unexpected error occurred in start_task_handler (manager).")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal Server Error: {e}"
            )

    @manager_app_instance.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Stop a task by its ID")
    async def stop_task_handler(task_id: uuid.UUID, manager: Manager = Depends(get_specific_manager)):
        logger.info(f"Received DELETE /tasks/{task_id} request to stop task.")
        try:
            task_to_stop = manager.task_db.get(task_id)
            if not task_to_stop:
                logger.warning(f"Attempted to stop non-existent task ID: {task_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No task with ID {task_id} found."
                )

            if task_to_stop.state in [State.COMPLETED, State.STOPPING]:
                 logger.info(f"Task {task_id} is already in {task_to_stop.state.name} state. No action taken.")
                 return Response(status_code=status.HTTP_204_NO_CONTENT)

            task_copy = task_to_stop.model_copy(deep=True)
            task_copy.state = State.STOPPING 

            stop_event = TaskEvent(
                event_id=uuid.uuid4(),
                state=State.COMPLETED,
                task=task_copy,
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            
            manager.add_task_event_to_pending(stop_event)
            logger.info(f"Added task event {stop_event.event_id} to manager's pending queue to stop task {task_id}.")

            return Response(status_code=status.HTTP_204_NO_CONTENT)

        except HTTPException as e:
            raise e
        except Exception as e:
            logger.exception("An unexpected error occurred in stop_task_handler (manager).")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal Server Error: {e}"
            )
            
    return manager_app_instance

class ManagerApiServer:
    def __init__(self, manager_instance: Manager, host: str = "127.0.0.1", port: int = 8000):
        self.manager = manager_instance
        self.host = host
        self.port = port
        self.fastapi_app = create_fastapi_app_for_manager(self.manager)
        self._server_thread: threading.Thread = None
        self._uvicorn_server = None # To hold the uvicorn Server instance for graceful shutdown

    def start(self):
        if self._server_thread and self._server_thread.is_alive():
            logger.warning(f"Manager API server on {self.host}:{self.port} is already running.")
            return

        config = uvicorn.Config(self.fastapi_app, host=self.host, port=self.port, log_level="info")
        self._uvicorn_server = uvicorn.Server(config)

        def run_api():
            logger.info(f"Starting Manager API on {self.host}:{self.port}")
            self._uvicorn_server.run()
            logger.info(f"Manager API on {self.host}:{self.port} stopped.")

        self._server_thread = threading.Thread(target=run_api, daemon=True)
        self._server_thread.start()
        logger.info(f"Manager API server started in a new thread on {self.host}:{self.port}.")

    async def stop(self):
        if self._uvicorn_server:
            logger.info(f"Stopping Manager API on {self.host}:{self.port}...")
            await self._uvicorn_server.shutdown()
            self._server_thread.join(timeout=5)
            if self._server_thread.is_alive():
                logger.warning(f"Manager API thread on {self.host}:{self.port} did not terminate gracefully.")
            self._server_thread = None
            self._uvicorn_server = None
            logger.info(f"Manager API on {self.host}:{self.port} stopped.")
        else:
            logger.info(f"Manager API on {self.host}:{self.port} was not running.")

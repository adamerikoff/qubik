import logging
import uuid
import typing
import copy

from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.responses import Response

from qubik import State, Task, Worker

from .schemas import TaskApiSchema, TaskEventApiSchema, api_schema_to_task, task_to_api_schema, api_schema_to_task_event, task_event_to_api_schema

logger = logging.getLogger(__name__)

global_worker: Worker = None

def get_worker() -> Worker:
    if global_worker is None:
        logger.critical("Worker instance not initialized for API.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Worker service not available."
        )
    return global_worker

app = FastAPI(
    title="Qubik Worker API",
    description="API for managing tasks on a Qubik worker.",
    version="0.1.0",
)

@app.post("/tasks", response_model=TaskApiSchema, status_code=status.HTTP_201_CREATED)
async def start_task_handler(task_event_api: TaskEventApiSchema, worker: Worker = Depends(get_worker)):
    logger.info(f"Received request to start task event ID: {task_event_api.event_id}")
    try:
        domain_task_event = api_schema_to_task_event(task_event_api)

        worker.add_task(domain_task_event.task)
        logger.info(f"Added task {domain_task_event.task.task_uuid} to worker queue.")

        return task_to_api_schema(domain_task_event.task)

    except Exception as e:
        logger.exception("An unexpected error occurred in start_task_handler.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal Server Error: {e}"
        )

@app.get("/tasks", response_model=typing.List[TaskApiSchema])
async def get_tasks_handler(worker: Worker = Depends(get_worker)):
    logger.info("Received request to get all tasks.")
    try:
        domain_tasks = worker.get_tasks()
        
        api_schemas = [task_to_api_schema(task) for task in domain_tasks]
        
        return api_schemas
    except Exception as e:
        logger.exception("An unexpected error occurred in get_tasks_handler.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal Server Error: {e}"
        )

@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def stop_task_handler(task_id: uuid.UUID, worker: Worker = Depends(get_worker)):
    logger.info(f"Received request to stop task with ID: {task_id}")
    try:
        task_to_stop_pointer = worker.db.get(task_id)
        if not task_to_stop_pointer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No task with ID {task_id} found."
            )

        task_copy = copy.deepcopy(task_to_stop_pointer)

        if task_copy.state == State.COMPLETED:
            logger.info(f"Task {task_id} is already in COMPLETED state. No action taken.")
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        task_copy.state = State.COMPLETED 

        worker.add_task(task_copy)
        logger.info(f"Added task {task_id} (state COMPLETED) to worker queue for stopping.")

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception("An unexpected error occurred in stop_task_handler.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal Server Error: {e}"
        )

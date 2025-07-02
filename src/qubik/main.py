import uuid
import time
import datetime
import sys
import typing
import logging

from qubik import Task, State, TaskEvent, Manager, Scheduler, Node, Worker, DockerResult, Docker, Config

logger = logging.getLogger(__name__)

def main():
    logger.info("Starting Orchestrator Core Test Script (main.py)")

    worker = Worker(name="test-worker-1")
    logger.info(f"Worker '{worker.name}' initialized.")

    start_task = Task(
        task_uuid=uuid.uuid4(),
        name="test-container-1",
        state=State.SCHEDULED,
        image="strm/helloworld-http",
        cpu=0.1,
        memory=128 * 1024 * 1024,
        disk=100,
        exposed_ports=[],
        port_bindings={},
        restart_policy="no"
    )
    logger.info(f"Created initial task for starting: {start_task}")

    logger.info("--- Starting Task ---")

    worker.add_task(start_task)

    start_result = worker.run_task()

    if start_result.error:
        logger.critical(f"Error starting task: {start_result.error}")
        raise start_result.error

    start_task.container_id = start_result.container_id
    start_task.state = State.RUNNING
    logger.info(f"Task {start_task.task_uuid.hex[:8]} is running in container {start_task.container_id}")

    logger.info("Sleeping for 10 seconds to allow container to run...")
    time.sleep(10)

    logger.info(f"--- Stopping Task {start_task.task_uuid.hex[:8]} ---")

    stop_task_request = Task(
        task_uuid=start_task.task_uuid,
        name=start_task.name,
        state=State.COMPLETED,
        image=start_task.image,
        cpu=start_task.cpu,
        memory=start_task.memory,
        disk=start_task.disk,
        exposed_ports=start_task.exposed_ports,
        port_bindings=start_task.port_bindings,
        restart_policy=start_task.restart_policy,
        container_id=start_task.container_id
    )

    worker.add_task(stop_task_request)

    stop_result = worker.run_task()

    if stop_result.error:
        logger.critical(f"Error stopping task: {stop_result.error}")
        raise stop_result.error

    logger.info(f"Task {start_task.task_uuid.hex[:8]} successfully processed for stopping.")

    logger.info("Orchestrator Core Test Script Finished Successfully.")


if __name__ == "__main__":
    main()
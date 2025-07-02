import uuid
import time
import datetime
import sys
import typing
import logging

from qubik import Task, State, TaskEvent, Manager, Scheduler, Node, Worker, DockerResult, Docker, Config

logger = logging.getLogger(__name__)

def create_and_run_task_container() -> typing.Tuple[typing.Optional[Docker], DockerResult]:
    logger.info("Setting up configuration for the test container...")
    
    # Define a Task Configuration with new fields
    task_config = Config(
        restart_policy="on-failure",
        name="test-container-" + str(uuid.uuid4())[:8],
        attach_stdin=False, # Example value
        attach_stdout=True, # Example value
        attach_stderr=True, # Example value
        exposed_ports=[5432], # Example: PostgreSQL default port
        cmd=[], # No specific command, use image's default ENTRYPOINT/CMD
        image="postgres:13",
        cpu=0.5,
        memory=256 * 1024 * 1024, # 256 MB
        disk=0, # No explicit Docker SDK mapping for this currently
        env=[
            "POSTGRES_USER=cube",
            "POSTGRES_PASSWORD=secret"
        ]
    )

    docker_manager_instance: typing.Optional[Docker] = None
    creation_result: DockerResult

    try:
        docker_manager_instance = Docker(task_config)
        creation_result = docker_manager_instance.run()
        
    except Exception as e:
        logger.exception("An unexpected error occurred during Docker manager initialization or container run.")
        creation_result = DockerResult(action="start", container_id=None, error=e, result="initialization_or_run_failure")
        return None, creation_result

    if creation_result.error:
        logger.error(f"Container creation failed: {creation_result.error}")
    else:
        logger.info(f"Container '{task_config.name}' (ID: {creation_result.container_id}) is running.")
        
    return docker_manager_instance, creation_result


def stop_and_remove_task_container(docker_manager_instance: Docker) -> DockerResult:
    if not docker_manager_instance or not docker_manager_instance.container_id:
        error_msg = "No active Docker manager instance or container ID to stop."
        logger.error(error_msg)
        return DockerResult(action="stop", container_id=None, error=ValueError(error_msg), result="no_container_to_stop")

    container_id_to_stop = docker_manager_instance.container_id # Get the ID from the manager
    logger.info(f"Attempting to stop and remove container: '{container_id_to_stop}'")

    stop_result = docker_manager_instance.stop()

    if stop_result.error:
        logger.error(f"Container stop/removal failed for ID '{container_id_to_stop}': {stop_result.error}")
    else:
        logger.info(f"Container '{container_id_to_stop}' has been stopped and removed successfully.")
        
    return stop_result


def main():
    logger.info("Starting Orchestrator Core Test Script (main.py)")

    # --- Phase 1: Create and Run a Container ---
    logger.info("\n--- Phase 1: Creating and Running a Test Container ---")
    docker_task_manager, create_res = create_and_run_task_container()

    if create_res.error:
        logger.critical("Critical error: Failed to create and run container. Exiting.")
        sys.exit(1)

    # Allow the container to run for a short period, as in the Go example
    run_duration = 5 # seconds
    logger.info(f"Container '{create_res.container_id}' is running. Waiting for {run_duration} seconds...")
    time.sleep(run_duration)

    # --- Phase 2: Stop and Remove the Container ---
    logger.info(f"\n--- Phase 2: Stopping and Removing Container '{create_res.container_id}' ---")
    
    # Ensure we have the manager instance from the creation step
    if docker_task_manager:
        stop_res = stop_and_remove_task_container(docker_task_manager)
        if stop_res.error:
            logger.critical("Critical error: Failed to stop and remove container. Exiting.")
            sys.exit(1)
    else:
        logger.critical("Critical error: Docker manager instance was not created. Cannot stop container. Exiting.")
        sys.exit(1)

    logger.info("\nOrchestrator Core Test Script Finished Successfully.")


if __name__ == "__main__":
    main()

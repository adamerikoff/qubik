import logging
import asyncio
import os
import uuid
import datetime
import httpx

# Import your refactored modules.
# Ensure 'qubik' is a package (has an __init__.py) and these files are inside it.
from qubik import Task, TaskEvent, State, Worker, Manager, WorkerApiServer, ManagerApiServer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Async Worker Task Processing Loop ---
async def run_worker_tasks_loop(worker_instance: Worker):
    logger.info(f"[{worker_instance.name} Loop] Starting worker task processing loop...")
    while True:
        try:
            if worker_instance.queue:
                await asyncio.to_thread(worker_instance.run_task)
            else:
                logger.debug(f"[{worker_instance.name} Loop] Queue is empty, sleeping...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.exception(f"Error in {worker_instance.name} task processing loop:")

# --- Async Manager Observation Loop (for logging/debugging purposes in main) ---
async def manager_observe_tasks_loop(manager_instance: Manager):
    logger.info("[Manager Observer] Starting manager task observation loop...")
    while True:
        try:
            if not manager_instance.task_db:
                logger.info("[Manager Observer] No tasks in manager's database yet.")
            else:
                logger.info("--- Current Tasks in Manager DB ---")
                for task_id, t in manager_instance.task_db.items():
                    worker_id_for_task = manager_instance.task_worker_map.get(task_id, 'UNASSIGNED')
                    logger.info(f"  Task ID: {t.task_uuid}, Name: {t.name}, State: {t.state.name}, Worker: {worker_id_for_task}")
                logger.info("-----------------------------------")
        except Exception as e:
            logger.exception("Error in manager_observe_tasks_loop:")
        await asyncio.sleep(10)

# --- The actual asynchronous application logic ---
async def async_main_orchestrator(): # Renamed from main()
    logger.info("Starting Qubik Orchestrator (Worker(s) + Manager)")

    # --- Configuration from Environment Variables ---
    manager_host = os.getenv("MANAGER_HOST", "127.0.0.1")
    manager_port = int(os.getenv("MANAGER_PORT", "8000"))

    worker_host = os.getenv("WORKER_HOST", "127.0.0.1")
    base_worker_port = int(os.getenv("WORKER_BASE_PORT", "8001"))
    num_workers = int(os.getenv("NUM_WORKERS", "2"))

    # --- Initialize Shared HTTPX AsyncClient for Manager ---
    manager_http_client = httpx.AsyncClient(timeout=10.0)

    # --- Initialize Manager Instance ---
    manager_instance = Manager(workers=[], http_client=manager_http_client)
    logger.info(f"Manager initialized: {manager_instance}")

    # --- Create and Start Manager API Server ---
    manager_api_server = ManagerApiServer(manager_instance, host=manager_host, port=manager_port)
    manager_api_server.start()
    logger.info(f"Manager API server active at http://{manager_host}:{manager_port} (in a separate thread).")
    await asyncio.sleep(1) # Give manager server a moment to start up

    # --- Create and Manage Workers ---
    worker_api_servers: list[WorkerApiServer] = []
    worker_internal_loops: list[asyncio.Task] = []

    for i in range(num_workers):
        worker_id = uuid.uuid4()
        worker_name = f"worker_{i}"
        current_worker_port = base_worker_port + i
        worker_api_url = f"{worker_host}:{current_worker_port}"

        worker_instance = Worker(name=worker_name)
        logger.info(f"Creating {worker_name} instance (ID: {worker_id}).")

        worker_server = WorkerApiServer(worker_instance, host=worker_host, port=current_worker_port)
        worker_server.start()
        worker_api_servers.append(worker_server)
        logger.info(f"{worker_name} API active at {worker_api_url} (in a separate thread).")
        
        manager_instance.add_worker_address(worker_api_url)
        logger.info(f"Registered {worker_name} ({worker_api_url}) with the Manager.")

        worker_loop_task = asyncio.create_task(run_worker_tasks_loop(worker_instance))
        worker_internal_loops.append(worker_loop_task)
        logger.info(f"{worker_name}'s internal task processing loop started as an asyncio task.")

    logger.info(f"All {num_workers} worker components initiated.")

    # --- Start Manager's Observation Loop ---
    manager_observer_task = asyncio.create_task(manager_observe_tasks_loop(manager_instance))
    logger.info("Manager's observation loop started.")

    # --- Submit Initial Test Tasks ---
    logger.info("Submitting 5 initial test tasks to the Manager's API (via Manager's add_task_event_to_pending)...")
    for i in range(5):
        task_name = f"my-awesome-container-{i}"
        container_port = 80
        host_port = 9000 + i
        
        t = Task(
            task_uuid=uuid.uuid4(),
            name=task_name,
            state=State.PENDING,
            image="strm/helloworld-http",
            cpu=0.2,
            memory=128 * 1024 * 1024,
            disk=10 * 1024 * 1024,
            restart_policy="no",
            exposed_ports=[container_port],
            port_bindings={host_port: container_port}
        )
        te = TaskEvent(
            event_id=uuid.uuid4(),
            state=State.PENDING,
            task=t,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        manager_instance.add_task_event_to_pending(te)
        logger.info(f"Submitted task '{task_name}' (ID: {t.task_uuid}) to manager.")
        await asyncio.sleep(0.1)

    logger.info("\nQubik Orchestrator is running. Watch the logs for task status updates.")
    logger.info(f"Manager API: http://{manager_host}:{manager_port}/docs")
    for i in range(num_workers):
        logger.info(f"Worker {i} API: http://{worker_host}:{base_worker_port + i}/docs")
    logger.info("\nPress Ctrl+C to initiate graceful shutdown...")
    
    try:
        while True:
            await asyncio.sleep(10)
    except asyncio.CancelledError:
        logger.info("Main loop cancelled due to an internal signal.")
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt detected. Initiating graceful shutdown.")
    finally:
        logger.info("\n--- Orchestrator Shutdown Sequence Initiated ---")
        
        logger.info("Stopping Manager API server...")
        await manager_api_server.stop()
        
        logger.info("Stopping Worker API servers...")
        for server in worker_api_servers:
            await server.stop() 
        
        logger.info("Cancelling worker internal processing loops...")
        for task in worker_internal_loops:
            task.cancel()
        await asyncio.gather(*worker_internal_loops, return_exceptions=True)
        logger.info("All worker internal loops cancelled/stopped.")

        logger.info("Cancelling manager observation loop...")
        manager_observer_task.cancel()
        await asyncio.gather(manager_observer_task, return_exceptions=True)
        logger.info("Manager observation loop cancelled.")

        if manager_http_client:
            logger.info("Closing Manager's shared HTTP client...")
            await manager_http_client.aclose()
            logger.info("Manager's shared HTTP client closed.")

        logger.info("--- Qubik Orchestrator Shutdown Complete ---")

# --- New Synchronous Entry Point for pyproject.toml ---
def main(): # This is the function that pyproject.toml's 'start' script will call
    try:
        asyncio.run(async_main_orchestrator())
    except KeyboardInterrupt:
        logger.info("Application exited via KeyboardInterrupt from main wrapper.")
    except Exception as e:
        logger.exception("An unhandled error occurred in the main wrapper:")

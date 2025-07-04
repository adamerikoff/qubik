import time
import logging
import threading
import os
import uuid
import datetime

import uvicorn

import qubik

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def manager_update_loop(manager_instance: qubik.Manager):
    while True:
        try:
            logger.info("[Manager Thread] Updating tasks from %d workers", len(manager_instance.workers))
            manager_instance.update_tasks()
        except Exception as e:
            logger.exception("Error in manager_update_loop:")
        time.sleep(15)

def manager_observe_tasks_loop(manager_instance: qubik.Manager):
    while True:
        if not manager_instance.task_db:
            logger.info("[Observer Thread] No tasks in manager's database yet.")
        else:
            for task_id, t in manager_instance.task_db.items():
                logger.info("[Observer Thread] Task: id: %s, state: %s", t.task_uuid, t.state.name)
        time.sleep(15)

def run_tasks_loop(worker_instance: qubik.Worker):
    logger.info("Starting worker task processing loop...")
    while True:
        if len(worker_instance.queue) > 0:
            worker_instance.run_task()
        else:
            logger.debug("Queue is empty, sleeping...")
            time.sleep(5)

def main():
    logger.info("Starting Cube Orchestrator (Worker + Manager)")

    host = os.getenv("CUBE_HOST", "localhost")
    try:
        port = int(os.getenv("CUBE_PORT", "5555"))
    except ValueError:
        logger.error("CUBE_PORT environment variable must be an integer. Using default 5555.")
        port = 5555

    logger.info(f"Configuring worker API to listen on {host}:{port}")

    logger.info("Initializing Worker instance...")
    worker_instance: qubik.Worker = qubik.Worker("worker_0")

    qubik.worker.api.global_worker = worker_instance
    logger.info("Worker instance assigned to FastAPI global worker.")

    logger.info("Initializing Manager instance...")
    worker_address = f"{host}:{port}"
    manager_workers = [worker_address]

    manager_instance = qubik.Manager(workers=manager_workers)
    
    logger.info("Starting Worker components in separate threads...")
    
    worker_thread = threading.Thread(target=run_tasks_loop, args=(worker_instance,), daemon=True, name=f"{worker_instance.name}RunThread")
    worker_thread.start()
    logger.info("WorkerRunThread started.")

    logger.info(f"Starting Worker API server on http://{host}:{port}...")
    worker_api_thread = threading.Thread(
        target=uvicorn.run, 
        args=(qubik.worker_app,), 
        kwargs={"host": host, "port": port, "log_level": "info"}, 
        daemon=True, 
        name="WorkerApiThread"
    )
    worker_api_thread.start()
    logger.info("WorkerApiThread started.")

    time.sleep(2) 

    logger.info("Creating and sending 3 initial tasks to the Manager...")
    for i in range(3):
        t = qubik.Task(
            task_uuid=uuid.uuid4(),
            name=f"test-container-{i}",
            state=qubik.State.PENDING,
            image="strm/helloworld-http",
            cpu=0.5,
            memory=268435456,
            disk=1,
            restart_policy="no",
            exposed_ports=[80],
            port_bindings={8000 + i: 80}
        )
        te = qubik.TaskEvent(
            event_id=uuid.uuid4(),
            state=qubik.State.PENDING,
            task=t,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        manager_instance.add_task_event_to_pending(te)
        manager_instance.send_work()
        logger.info(f"Task {t.task_uuid} added to manager's pending queue and manager attempted to send.")
        
        time.sleep(0.5) 

    logger.info("Starting Manager update and observation loops in separate threads...")
    
    manager_update_thread = threading.Thread(target=manager_update_loop, args=(manager_instance,), daemon=True, name="ManagerUpdateThread")
    manager_update_thread.start()
    logger.info("ManagerUpdateThread started.")

    manager_observe_thread = threading.Thread(target=manager_observe_tasks_loop, args=(manager_instance,), daemon=True, name="ManagerObserveThread")
    manager_observe_thread.start()
    logger.info("ManagerObserveThread started.")

    logger.info("All components started. Manager and Worker are running.")
    logger.info("Monitor logs in this terminal. Use 'curl http://localhost:5555/tasks' or 'docker ps' in another terminal to verify.")
    logger.info("\nPress Enter to stop the orchestrator (or Ctrl+C)...")
    
    try:
        input() 
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt detected. Initiating graceful shutdown.")
    finally:
        logger.info("Orchestrator Core Test Script Finished.")


if __name__ == "__main__":
    main()
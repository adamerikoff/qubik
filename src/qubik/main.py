import uuid
import time
import datetime
import sys
import typing
import logging
import threading
import os

import uvicorn

import qubik

logger = logging.getLogger(__name__)

def run_tasks(worker_instance: qubik.Worker):
    logger.info("Starting worker task processing loop...")
    while True:
        if len(worker_instance.queue) > 0:
            worker_instance.run_task()
        else:
            logger.debug("Queue is empty, sleeping...")
            time.sleep(5)

def main():
    logger.info("Starting Orchestrator Core Test Script (main.py)")

    host = os.getenv("CUBE_HOST", "127.0.0.1")  # Default to localhost if not set
    port_str = os.getenv("CUBE_PORT", "5555")   # Default port
        
    try:
        port = int(port_str)
    except ValueError:
        logger.error(f"Invalid CUBE_PORT environment variable: {port_str}. Using default 5555.")
        port = 5555

    worker_instance = qubik.Worker("test-worker")

    qubik.api.api.global_worker = worker_instance

    worker_thread = threading.Thread(target=run_tasks, args=(worker_instance,), daemon=True)
    worker_thread.start()
    logger.info("Worker task processing loop started in a background thread.")

    logger.info(f"Starting FastAPI API server on {host}:{port}")
    uvicorn.run(qubik.app, host=host, port=port)

    logger.info("Orchestrator Core Test Script Finished Successfully.")


if __name__ == "__main__":
    main()
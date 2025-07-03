import logging.config
import pathlib
import logging

from .node import Node
from .task import Task, State, TaskEvent, Config, Docker, DockerResult, state_contains, valid_state_transition
from .manager import Manager
from .worker import Worker
from .scheduler import Scheduler
from .api import app, global_worker, task_event_to_api_schema, task_to_api_schema, TaskApiSchema, TaskEventApiSchema, api_schema_to_task, api_schema_to_task_event

__all__ = [
    "Node",
    "Task",
    "State",
    "TaskEvent",
    "Manager",
    "Scheduler",
    "Worker",
    "Config",
    "Docker",
    "DockerResult",
    "valid_state_transition",
    "state_contains",
    "app", 
    "global_worker", 
    "task_event_to_api_schema", 
    "task_to_api_schema", 
    "TaskApiSchema", 
    "TaskEventApiSchema", 
    "api_schema_to_task", 
    "api_schema_to_task_event"  

]
__version__ = "0.1.0"


def setup_logging():
    log_config_path = pathlib.Path(__file__).parent / 'logging.conf'
    if log_config_path.exists():
        logging.config.fileConfig(log_config_path)
    else:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    logger = logging.getLogger(__name__)
    logger.info("Logging configured")

setup_logging()
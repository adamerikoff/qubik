import uuid
import datetime
import typing

from pydantic import BaseModel, Field

from qubik import Task, TaskEvent, State

class TaskApiSchema(BaseModel):
    task_id: uuid.UUID = Field(default_factory=uuid.uuid4, alias="task_id", description="Unique identifier for the task.")

    name: str = Field(..., alias="name", description="Name of the task.")
    state: int = Field(..., alias="state", description="Current state of the task (integer value of State enum).")
    image: str = Field(..., alias="image", description="Docker image to use for the task.")
    
    cpu: float = Field(1.0, alias="cpu", description="CPU allocation for the task (e.g., 0.1 for 10% of one core).")
    memory: int = Field(268435456, alias="memory", description="Memory limit in bytes (e.g., 268435456 for 256MB).") # Default 256MB
    disk: int = Field(1, alias="disk", description="Disk allocation in GiB (default 10GiB).")
    restart_policy: str = Field("no", alias="restart_policy", description="Restart policy for the container (e.g., 'no', 'always').")
    
    exposed_ports: typing.List[int] = Field([], alias="ExposedPorts", description="List of exposed ports (integers).")
    port_bindings: typing.Dict[int, int] = Field({}, alias="port_bindings", description="Mapping of host ports to container ports (key: host port, value: container port).")
    
    container_id: typing.Optional[str] = Field(None, alias="container_id", description="ID of the Docker container if running.")
    start_time: typing.Optional[datetime.datetime] = Field(None, alias="start_time", description="Timestamp when the task started.")
    finish_time: typing.Optional[datetime.datetime] = Field(None, alias="finish_time", description="Timestamp when the task finished.")
    
    class Config:
        use_enum_values = True
        populate_by_name = True
        schema_extra = {
            "example": {
                "task_id": "a1a1a1a1-a1a1-4a1a-a1a1-a1a1a1a1a1a1", 
                "name": "example-task",
                "state": 1, 
                "image": "strm/helloworld-http",
                "cpu": 0.5,
                "memory": 268435456, 
                "disk": 50,
                "exposed_ports": [80],
                "port_bindings": {8080: 80},
                "restart_policy": "always",
                "container_id": None,
                "start_time": None,
                "finish_time": None
            }
        }

class TaskEventApiSchema(BaseModel):
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4, alias="event_id", description="Unique identifier for the task event.")
    
    state: int = Field(..., alias="state", description="State of the task associated with this event (integer value of State enum).")
    
    task: TaskApiSchema = Field(..., alias="task", description="The task object associated with this event.")
    
    timestamp: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc), alias="timestamp", description="Timestamp of the event.")


    class Config:
        use_enum_values = True
        populate_by_name = True
        schema_extra = {
            "example": {
                "id": "f5f5f5f5-f5f5-4f5f-f5f5-f5f5f5f5f5f5",
                "state": 1,
                "task": {
                    "task_id": "a1a1a1a1-a1a1-4a1a-a1a1-a1a1a1a1a1a1",
                    "name": "example-task",
                    "state": 1, 
                    "image": "strm/helloworld-http",
                    "cpu": 0.5,
                    "memory": 268435456, 
                    "disk": 50,
                    "exposed_ports": [80],
                    "port_bindings": {8080: 80},
                    "restart_policy": "always",
                    "container_id": None,
                    "start_time": None,
                    "finish_time": None
                },
                "timestamp": "2025-07-03T10:00:00Z"
            }
        }

def task_to_api_schema(task_domain: Task) -> TaskApiSchema:
    return TaskApiSchema(
        task_id=task_domain.task_uuid,
        name=task_domain.name,
        state=task_domain.state.value,
        image=task_domain.image,
        cpu=task_domain.cpu,
        memory=task_domain.memory,
        disk=task_domain.disk,
        exposed_ports=task_domain.exposed_ports,
        port_bindings=task_domain.port_bindings,
        restart_policy=task_domain.restart_policy,
        container_id=task_domain.container_id,
        start_time=task_domain.start_time,
        finish_time=task_domain.finish_time
    )

def api_schema_to_task(task_api: TaskApiSchema) -> Task:
    return Task(
        task_uuid=task_api.task_id,
        name=task_api.name,
        state=State(task_api.state),
        image=task_api.image,
        cpu=task_api.cpu,
        memory=task_api.memory,
        disk=task_api.disk,
        exposed_ports=task_api.exposed_ports,
        port_bindings=task_api.port_bindings,
        restart_policy=task_api.restart_policy,
        container_id=task_api.container_id,
        start_time=task_api.start_time,
        finish_time=task_api.finish_time
    )

def task_event_to_api_schema(event_domain: TaskEvent) -> TaskEventApiSchema:
    return TaskEventApiSchema(
        event_id=event_domain.event_id,
        state=event_domain.state.value,
        task=task_to_api_schema(event_domain.task),
        timestamp=event_domain.timestamp
    )

def api_schema_to_task_event(event_api: TaskEventApiSchema) -> TaskEvent:
    return TaskEvent(
        event_id=event_api.event_id,
        state=State(event_api.state),
        task=api_schema_to_task(event_api.task),
        timestamp=event_api.timestamp
    )
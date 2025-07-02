import uuid
import datetime
import typing
import logging

from .state import State

logger = logging.getLogger(__name__)

class Task:
    def __init__(self,
                 task_uuid: uuid.UUID,
                 name: str,
                 state: State,
                 image: str,
                 cpu: float,
                 memory: int,
                 disk: int,
                 exposed_ports: typing.List[int],
                 port_bindings: typing.Dict[int, int],
                 restart_policy: str,
                 container_id: typing.Optional[str] = None,
                 start_time: typing.Optional[datetime.datetime] = None,
                 finish_time: typing.Optional[datetime.datetime] = None):
        self.task_uuid: uuid.UUID = task_uuid
        self.name: str = name
        self.state: State = state
        self.image: str = image
        self.cpu: float = cpu
        self.memory: int = memory
        self.disk: int = disk
        self.exposed_ports: typing.List[int] = exposed_ports
        self.port_bindings: typing.Dict[int, int] = port_bindings
        self.restart_policy: str = restart_policy
        self.container_id: typing.Optional[str] = container_id
        self.start_time: typing.Optional[datetime.datetime] = start_time
        self.finish_time: typing.Optional[datetime.datetime] = finish_time

        logger.info(
            "Task initialized: uuid=%s, name='%s', state=%s, image='%s'",
            task_uuid, name, state.name, image
        )
        if container_id:
            logger.debug("Task %s associated with container_id: %s", task_uuid, container_id)


    def __repr__(self) -> str:
        return (f"Task(uuid={self.task_uuid.hex[:8]}..., name='{self.name}', "
                f"state={self.state.name})")
import typing
import logging

logger = logging.getLogger(__name__)

class Config:
    def __init__(self,
                 restart_policy: str,
                 name: str,
                 attach_stdin: bool,
                 attach_stdout: bool,
                 attach_stderr: bool,
                 exposed_ports: typing.List[int],
                 cmd: typing.List[str],
                 image: str,
                 cpu: float,
                 memory: int,
                 disk: int,
                 env: typing.List[str]):
        self.restart_policy: str = restart_policy
        self.name: str = name
        self.attach_stdin: bool = attach_stdin
        self.attach_stdout: bool = attach_stdout
        self.attach_stderr: bool = attach_stderr
        self.exposed_ports: typing.List[int] = exposed_ports
        self.cmd: typing.List[str] = cmd
        self.image: str = image
        self.cpu: float = cpu
        self.memory: int = memory
        self.disk: int = disk
        self.env: typing.List[str] = env

        logger.info("Config created: %s (image: %s)\nConfig details - CPU: %s, Memory: %d, Disk: %d, Ports: %s", name, image, cpu, memory, disk, exposed_ports)

    def __repr__(self):
        return (f"Config(restart_policy='{self.restart_policy}', name='{self.name}', "
                f"attach_stdin={self.attach_stdin}, attach_stdout={self.attach_stdout}, "
                f"attach_stderr={self.attach_stderr}, exposed_ports={self.exposed_ports}, "
                f"cmd={self.cmd}, image='{self.image}', cpu={self.cpu}, memory={self.memory}, "
                f"disk={self.disk}, env={self.env})")
        
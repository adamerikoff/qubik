import logging

logger = logging.getLogger(__name__)

class Node:
    def __init__(self,
                 name: str,
                 ip: str,
                 cores: int,
                 memory: int,
                 disk: int,
                 role: str):
        self.name: str = name
        self.ip: str = ip
        self.cores: int = cores
        self.memory: int = memory
        self.disk: int = disk
        self.role: str = role

        # Allocated resources typically start at 0 and are updated dynamically
        self.memory_allocated: int = 0
        self.disk_allocated: int = 0
        self.task_count: int = 0

        logger.info("Node initialized: %s (IP: %s, Role: %s)\nNode details - Cores: %d, Memory: %dMB, Disk: %dGB", name, ip, role, cores, memory, disk)

    def __repr__(self) -> str:
        return (f"Node(name='{self.name}', ip='{self.ip}', role='{self.role}', "
                f"cores={self.cores}, mem={self.memory}MB, disk={self.disk}GB, "
                f"tasks={self.task_count})")
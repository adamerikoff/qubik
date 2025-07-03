import datetime
import pydantic
import typing

class CPUMetrics(pydantic.BaseModel):
    user: float = 0.0
    nice: float = 0.0
    system: float = 0.0
    idle: float = 0.0
    iowait: float = 0.0
    irq: float = 0.0
    softirq: float = 0.0
    steal: float = 0.0
    guest: float = 0.0
    guest_nice: float = 0.0
    usage_percent: float = 0.0

class MemoryMetrics(pydantic.BaseModel):
    total_kb: int = 0
    available_kb: int = 0
    used_kb: int = 0
    used_percent: float = 0.0

class DiskMetrics(pydantic.BaseModel):
    total_gb: int = 0
    used_gb: int = 0
    free_gb: int = 0
    used_percent: float = 0.0

class LoadAvgMetrics(pydantic.BaseModel):
    last1min: float = 0.0
    last5min: float = 0.0
    last15min: float = 0.0

class WorkerMetrics(pydantic.BaseModel):
    timestamp: datetime.datetime = pydantic.Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    cpu: CPUMetrics = pydantic.Field(default_factory=CPUMetrics)
    memory: MemoryMetrics = pydantic.Field(default_factory=MemoryMetrics)
    disk: DiskMetrics = pydantic.Field(default_factory=DiskMetrics)
    load_avg: LoadAvgMetrics = pydantic.Field(default_factory=LoadAvgMetrics)
    task_count: int = 0
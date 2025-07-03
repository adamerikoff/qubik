import psutil
import datetime
import time
import logging

from .schemas import CPUMetrics, MemoryMetrics, DiskMetrics, LoadAvgMetrics, WorkerMetrics

logger = logging.getLogger(__name__)

class MetricsCollector:
    def __init__(self):
        self._last_cpu_times = psutil.cpu_times()

    def get_cpu_metrics(self) -> CPUMetrics:
        cpu_times_current = psutil.cpu_times()

        delta_user = cpu_times_current.user - self._last_cpu_times.user
        delta_nice = cpu_times_current.nice - self._last_cpu_times.nice
        delta_system = cpu_times_current.system - self._last_cpu_times.system
        delta_idle = cpu_times_current.idle - self._last_cpu_times.idle
        
        delta_iowait = getattr(cpu_times_current, 'iowait', 0.0) - getattr(self._last_cpu_times, 'iowait', 0.0)
        delta_irq = getattr(cpu_times_current, 'irq', 0.0) - getattr(self._last_cpu_times, 'irq', 0.0)
        delta_softirq = getattr(cpu_times_current, 'softirq', 0.0) - getattr(self._last_cpu_times, 'softirq', 0.0)
        delta_steal = getattr(cpu_times_current, 'steal', 0.0) - getattr(self._last_cpu_times, 'steal', 0.0)
        delta_guest = getattr(cpu_times_current, 'guest', 0.0) - getattr(self._last_cpu_times, 'guest', 0.0)
        delta_guest_nice = getattr(cpu_times_current, 'guest_nice', 0.0) - getattr(self._last_cpu_times, 'guest_nice', 0.0)

        total_delta = (delta_user + delta_nice + delta_system + delta_idle +
                       delta_iowait + delta_irq + delta_softirq + delta_steal +
                       delta_guest + delta_guest_nice)

        usage_percent = 0.0
        if total_delta > 0:
            usage_percent = ((total_delta - delta_idle) / total_delta) * 100.0

        self._last_cpu_times = cpu_times_current # Update for next calculation

        return CPUMetrics(
            user=delta_user,
            nice=delta_nice,
            system=delta_system,
            idle=delta_idle,
            iowait=delta_iowait,
            irq=delta_irq,
            softirq=delta_softirq,
            steal=delta_steal,
            guest=delta_guest,
            guest_nice=delta_guest_nice,
            usage_percent=usage_percent
        )

    def get_memory_metrics(self) -> MemoryMetrics:
        mem = psutil.virtual_memory()
        return MemoryMetrics(
            total_kb=mem.total // 1024,
            available_kb=mem.available // 1024,
            used_kb=mem.used // 1024,
            used_percent=mem.percent
        )

    def get_disk_metrics(self, path='/') -> DiskMetrics:
        try:
            disk = psutil.disk_usage(path)
            gb_divisor = (1024 ** 3)
            return DiskMetrics(
                total_gb=disk.total // gb_divisor,
                used_gb=disk.used // gb_divisor,
                free_gb=disk.free // gb_divisor,
                used_percent=disk.percent
            )
        except Exception as e:
            logger.error(f"Error getting disk metrics for {path}: {e}")
            return DiskMetrics()

    def get_load_avg_metrics(self) -> LoadAvgMetrics:
        load1, load5, load15 = psutil.getloadavg()
        return LoadAvgMetrics(
            last1min=load1,
            last5min=load5,
            last15min=load15
        )

    def collect_all_metrics(self, task_count: int = 0) -> WorkerMetrics:
        return WorkerMetrics(
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            cpu=self.get_cpu_metrics(),
            memory=self.get_memory_metrics(),
            disk=self.get_disk_metrics(),
            load_avg=self.get_load_avg_metrics(),
            task_count=task_count
        )
import abc
import typing
import logging

from qubik import Task, Worker

logger = logging.getLogger(__name__)

class Scheduler(abc.ABC):
    @abc.abstractmethod
    def select_candidate_nodes(self, task: Task, all_nodes: typing.List[Worker]) -> typing.List[Worker]:
        raise NotImplementedError("Subclasses must implement select_candidate_nodes method.")

    @abc.abstractmethod
    def score(self, task: Task, candidate_nodes: typing.List[Worker]) -> typing.Dict[Worker, float]:
        raise NotImplementedError("Subclasses must implement score method.")

    @abc.abstractmethod
    def pick(self, scored_nodes: typing.Dict[Worker, float]) -> typing.Optional[Worker]:
        raise NotImplementedError("Subclasses must implement pick method.")
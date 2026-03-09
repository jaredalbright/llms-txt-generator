from abc import ABC, abstractmethod

from app.models.generation import Generation
from app.services.progress import StepProgressReporter


class PipelineNode(ABC):
    """A single unit of work in the pipeline DAG."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def execute(
        self, generation: Generation, reporter: StepProgressReporter
    ) -> None:
        """Execute this node, reading from and writing to the Generation."""
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"

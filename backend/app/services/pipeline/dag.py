import asyncio
import logging
from graphlib import TopologicalSorter

from app.models.generation import Generation
from app.services.pipeline.node import PipelineNode
from app.services.progress import StepProgressReporter

logger = logging.getLogger("app.pipeline.dag")


class PipelineDAG:
    """Directed acyclic graph of pipeline nodes with parallel execution."""

    def __init__(self):
        self._nodes: dict[str, PipelineNode] = {}
        self._graph: dict[str, set[str]] = {}

    def add_node(
        self, node: PipelineNode, depends_on: list[str] | None = None
    ) -> "PipelineDAG":
        """Register a node with its dependencies. Returns self for chaining."""
        self._nodes[node.name] = node
        self._graph[node.name] = set(depends_on or [])
        return self

    @property
    def node_names(self) -> list[str]:
        return list(self._nodes.keys())

    async def execute(
        self, generation: Generation, event_queue: asyncio.Queue
    ) -> None:
        """Execute all nodes respecting dependency order, parallelizing where possible."""
        sorter = TopologicalSorter(self._graph)
        sorter.prepare()

        while sorter.is_active():
            ready = sorter.get_ready()
            if not ready:
                break

            ready_names = list(ready)
            logger.info(
                "[%s] Executing in parallel: %s",
                generation.id[:8],
                ", ".join(ready_names),
            )

            tasks = [
                self._run_node(name, generation, event_queue)
                for name in ready_names
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for name, result in zip(ready_names, results):
                if isinstance(result, Exception):
                    raise result
                sorter.done(name)

    async def _run_node(
        self,
        name: str,
        generation: Generation,
        event_queue: asyncio.Queue,
    ) -> None:
        node = self._nodes[name]
        reporter = StepProgressReporter(event_queue, name)

        logger.info("[%s] Node '%s' starting", generation.id[:8], name)
        await node.execute(generation, reporter)
        generation.completed_steps.append(name)
        logger.info("[%s] Node '%s' completed", generation.id[:8], name)

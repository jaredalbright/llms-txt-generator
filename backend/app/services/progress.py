import asyncio


class StepProgressReporter:
    """Thin wrapper around an asyncio.Queue for reporting progress from a pipeline step."""

    def __init__(self, queue: asyncio.Queue, step: str):
        self.queue = queue
        self.step = step

    async def started(self, message: str):
        await self.queue.put({
            "type": "progress",
            "step": self.step,
            "step_state": "started",
            "message": message,
        })

    async def log(self, detail: str, message: str | None = None):
        """Append a detail line. Optionally update the header message."""
        payload: dict = {
            "type": "progress",
            "step": self.step,
            "step_state": "progress",
            "detail": detail,
        }
        if message is not None:
            payload["message"] = message
        await self.queue.put(payload)

    async def completed(self, summary: str):
        await self.queue.put({
            "type": "progress",
            "step": self.step,
            "step_state": "completed",
            "message": summary,
            "summary": summary,
        })

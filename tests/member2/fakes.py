import json


class FakeLLM:
    """Returns canned responses in order (the last one repeats). An Exception
    instance in the list is raised instead of returned."""

    def __init__(self, *responses):
        self.responses = list(responses) or ["{}"]
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        r = self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]
        if isinstance(r, Exception):
            raise r
        return r if isinstance(r, str) else json.dumps(r)

    def payload(self, call: int = 0) -> dict:
        return json.loads(self.calls[call][1])

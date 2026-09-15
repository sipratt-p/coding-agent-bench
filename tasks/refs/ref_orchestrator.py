"""Reference solution for the Async DAG Orchestrator task (validates the grader)."""
import asyncio


class Orchestrator:
    def __init__(self):
        self._tasks = {}   # name -> (fn, deps)

    def add_task(self, name, fn, deps=None):
        if name in self._tasks:
            raise ValueError(f"duplicate task {name!r}")
        self._tasks[name] = (fn, list(deps or []))

    def _validate(self):
        for name, (_, deps) in self._tasks.items():
            for d in deps:
                if d not in self._tasks:
                    raise ValueError(f"unknown dep {d!r} of {name!r}")
        seen, stack = set(), set()

        def visit(n):
            if n in stack:
                raise ValueError("cycle detected")
            if n in seen:
                return
            stack.add(n)
            for d in self._tasks[n][1]:
                visit(d)
            stack.discard(n)
            seen.add(n)

        for n in self._tasks:
            visit(n)

    async def run(self, task_timeout=None):
        self._validate()
        outcomes = {}
        events = {n: asyncio.Event() for n in self._tasks}

        async def runner(name):
            fn, deps = self._tasks[name]
            for d in deps:
                await events[d].wait()
            if any(outcomes[d]["status"] != "ok" for d in deps):
                outcomes[name] = {"status": "skipped"}
                events[name].set()
                return
            results = {d: outcomes[d]["result"] for d in deps}
            try:
                coro = fn(results)
                if task_timeout is not None:
                    result = await asyncio.wait_for(coro, task_timeout)
                else:
                    result = await coro
                outcomes[name] = {"status": "ok", "result": result}
            except (asyncio.TimeoutError, TimeoutError):
                outcomes[name] = {"status": "cancelled"}
            except asyncio.CancelledError:
                outcomes[name] = {"status": "cancelled"}
                raise
            except Exception as e:
                outcomes[name] = {"status": "failed", "error": e}
            finally:
                events[name].set()

        await asyncio.gather(*(runner(n) for n in self._tasks))
        return outcomes

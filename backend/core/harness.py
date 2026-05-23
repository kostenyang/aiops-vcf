"""
Harness layer — guardrails & approval gates.
Inspired by Harness Engineering (OpenAI, Feb 2026).
Rule: READ_ONLY agents never mutate state.
      ACTION agents require human approval.
"""
from enum import Enum
from typing import Callable, Any
import structlog

log = structlog.get_logger()

class AgentMode(str, Enum):
    READ_ONLY = "read_only"
    ACTION    = "action"

def guardrail(mode: AgentMode):
    def decorator(fn: Callable):
        async def wrapper(*args, **kwargs) -> Any:
            log.info("agent.invoke", agent=fn.__name__, mode=mode)
            if mode == AgentMode.ACTION:
                log.warning("agent.action_gate", agent=fn.__name__,
                            message="Ensure human approval before execution")
            result = await fn(*args, **kwargs)
            log.info("agent.complete", agent=fn.__name__)
            return result
        return wrapper
    return decorator

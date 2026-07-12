from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Awaitable, cast

from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from cys_core.domain.messaging import extract_message_content
from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.guardrails import OutputGuardrails
from cys_core.domain.security.prompt_context import (
    REFUSAL_MESSAGE,
    UntrustedSource,
    compute_system_digest,
    digest_matches,
)
from cys_core.domain.security.sanitizer import InjectionVerdict, InputSanitizer
from cys_core.middleware._framework_casts import cast_model_response
from cys_core.security.monitor import AgentMonitor


def _message_text(message: BaseMessage) -> str:
    return extract_message_content(message.content)


def _message_source(message: BaseMessage) -> UntrustedSource:
    if isinstance(message, ToolMessage):
        return "tool"
    text = _message_text(message)
    if 'source="agent_bus"' in text or "source=agent_bus" in text:
        return "agent_bus"
    if 'source="external"' in text or "source=external" in text:
        return "external"
    return "user"


def _with_content(message: BaseMessage, content: str) -> BaseMessage:
    return message.model_copy(update={"content": content})


class PromptContextMiddleware(AgentMiddleware):
    """Enforce trusted system vs untrusted user/external context on every model call."""

    def __init__(
        self,
        agent_id: str,
        system_prompt_digest: str = "",
        session_id: str = "default",
        *,
        sanitizer: InputSanitizer | None = None,
        guardrails: OutputGuardrails | None = None,
    ) -> None:
        super().__init__()
        self.agent_id = agent_id
        self.system_prompt_digest = system_prompt_digest
        self.session_id = session_id
        self.sanitizer = sanitizer or InputSanitizer()
        self.guardrails = guardrails or OutputGuardrails()
        self.monitor = AgentMonitor(agent_id)

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse | AIMessage:
        violation = self._validate_system_context(request)
        if violation is not None:
            return violation

        try:
            sanitized_messages = self._sanitize_messages(request.messages)
        except SecurityViolation:
            return AIMessage(content=REFUSAL_MESSAGE)

        updated = request.override(messages=sanitized_messages)
        response = handler(updated)
        return self._guard_response(response)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse] | ModelResponse],
    ) -> ModelResponse | AIMessage:
        violation = self._validate_system_context(request)
        if violation is not None:
            return violation

        try:
            sanitized_messages = self._sanitize_messages(request.messages)
        except SecurityViolation:
            return AIMessage(content=REFUSAL_MESSAGE)

        updated = request.override(messages=sanitized_messages)
        result = handler(updated)
        if inspect.isawaitable(result):
            return self._guard_response(cast_model_response(await result))
        return self._guard_response(cast_model_response(result))

    def _validate_system_context(self, request: ModelRequest) -> AIMessage | None:
        if request.system_message is None:
            return None
        system_text = request.system_message.text
        if "GLOBAL_RULES:" not in system_text or "SECURITY_RULES:" not in system_text:
            self.monitor.record_injection_attempt(
                self.session_id,
                InjectionVerdict.HARD.value,
                {"reason": "missing_immutable_rule_markers"},
            )
            return AIMessage(content=REFUSAL_MESSAGE)
        if not self.system_prompt_digest:
            return None
        actual = compute_system_digest(system_text)
        if not digest_matches(self.system_prompt_digest, actual):
            self.monitor.record_injection_attempt(
                self.session_id,
                InjectionVerdict.HARD.value,
                {"reason": "system_prompt_digest_mismatch"},
            )
            return AIMessage(content=REFUSAL_MESSAGE)
        return None

    def _sanitize_messages(self, messages: list[AnyMessage]) -> list[AnyMessage]:
        sanitized: list[AnyMessage] = []
        for message in messages:
            if isinstance(message, SystemMessage):
                self.monitor.record_injection_attempt(
                    self.session_id,
                    InjectionVerdict.HARD.value,
                    {"reason": "fake_system_message_in_history"},
                )
                raise SecurityViolation("System message injection in conversation history")

            if not isinstance(message, (HumanMessage, ToolMessage)):
                sanitized.append(message)
                continue

            text = _message_text(message)
            verdict = self.sanitizer.classify(text)
            if verdict is InjectionVerdict.HARD:
                self.monitor.record_injection_attempt(
                    self.session_id,
                    verdict.value,
                    {"reason": "hard_injection_in_message", "source": _message_source(message)},
                )
                raise SecurityViolation("Hard prompt injection in model context")

            if verdict is InjectionVerdict.SOFT:
                self.monitor.record_injection_attempt(
                    self.session_id,
                    verdict.value,
                    {"reason": "soft_injection_in_message", "source": _message_source(message)},
                )

            source = _message_source(message)
            wrapped = self.sanitizer.sanitize(text, source=source)
            sanitized.append(cast(AnyMessage, _with_content(message, wrapped)))
        return sanitized

    def _guard_response(self, response: ModelResponse | AIMessage) -> ModelResponse | AIMessage:
        if isinstance(response, AIMessage):
            text = _message_text(response)
            if self.guardrails.detect_prompt_leakage(text):
                self.monitor.log_security_event(
                    self.session_id,
                    "prompt_leakage_blocked",
                    "WARNING",
                    {"agent_id": self.agent_id},
                )
                return AIMessage(content=REFUSAL_MESSAGE)
            return response
        if not response.result:
            return response
        last = response.result[-1]
        if not isinstance(last, AIMessage):
            return response
        text = _message_text(last)
        if self.guardrails.detect_prompt_leakage(text):
            self.monitor.log_security_event(
                self.session_id,
                "prompt_leakage_blocked",
                "WARNING",
                {"agent_id": self.agent_id},
            )
            return AIMessage(content=REFUSAL_MESSAGE)
        return response

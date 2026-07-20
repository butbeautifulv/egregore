from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from cys_core.domain.security.exceptions import SecurityViolation
from cys_core.domain.security.guardrails import OutputGuardrails
from cys_core.domain.security.prompt_context import (
    REFUSAL_MESSAGE,
    UntrustedSource,
    compute_system_digest,
    digest_matches,
)
from cys_core.domain.security.sanitizer import InjectionVerdict, InputSanitizer

MessageRole = Literal["system", "user", "assistant", "tool"]

_ROLE_TO_SOURCE: dict[str, UntrustedSource] = {
    "user": "user",
    "tool": "tool",
}


@dataclass
class ModelMessage:
    role: MessageRole
    content: str
    source: UntrustedSource | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_call_id: str = ""


@dataclass
class ModelInvokeCommand:
    persona: str
    system_prompt: str
    messages: list[ModelMessage]
    system_prompt_digest: str = ""
    model: str = ""
    temperature: float | None = None
    max_tokens: int | None = None
    session_id: str = "default"
    tools: list[dict[str, Any]] = field(default_factory=list)
    tool_choice: str | dict[str, Any] | None = None


@dataclass
class ModelInvokeResult:
    success: bool
    content: str = ""
    refused: bool = False
    refusal_reason: str = ""
    model: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


CompletionFn = Callable[..., Awaitable[dict[str, Any]]]


def _to_litellm_message(message: ModelMessage) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.role == "assistant" and message.tool_calls:
        payload["tool_calls"] = message.tool_calls
    if message.role == "tool" and message.tool_call_id:
        payload["tool_call_id"] = message.tool_call_id
    return payload


class InvokeModel:
    """The model-gateway chokepoint (§22.9): sanitize input, validate the caller isn't
    forging system instructions, call the model, then guardrail-check the output —
    all independent of whatever agent runtime is on the other end of the request.
    Mirrors worker's PromptContextMiddleware/InputSanitizer/OutputGuardrails logic, but
    against a plain framework-neutral request instead of langchain's ModelRequest/AIMessage
    (this service must not depend on any agent-execution framework, see §21.5's equivalent
    reasoning for tool-gateway)."""

    def __init__(
        self,
        *,
        complete: CompletionFn,
        default_model: str,
        sanitizer: InputSanitizer | None = None,
        guardrails: OutputGuardrails | None = None,
        record_invocation: Callable[[str, bool], None] | None = None,
    ) -> None:
        self._complete = complete
        self._default_model = default_model
        self._sanitizer = sanitizer or InputSanitizer()
        self._guardrails = guardrails or OutputGuardrails()
        self._record_invocation = record_invocation or (lambda _persona, _ok: None)

    def _refuse(self, reason: str) -> ModelInvokeResult:
        return ModelInvokeResult(
            success=True,
            content=REFUSAL_MESSAGE,
            refused=True,
            refusal_reason=reason,
        )

    def _validate_system_prompt(self, command: ModelInvokeCommand) -> ModelInvokeResult | None:
        text = command.system_prompt
        if "GLOBAL_RULES:" not in text or "SECURITY_RULES:" not in text:
            return self._refuse("missing_immutable_rule_markers")
        if not command.system_prompt_digest:
            return None
        actual = compute_system_digest(text)
        if not digest_matches(command.system_prompt_digest, actual):
            return self._refuse("system_prompt_digest_mismatch")
        return None

    def _sanitize_messages(self, messages: list[ModelMessage]) -> list[ModelMessage] | ModelInvokeResult:
        sanitized: list[ModelMessage] = []
        for message in messages:
            if message.role == "system":
                return self._refuse("fake_system_message_in_history")
            if message.role != "user" and message.role != "tool":
                sanitized.append(message)
                continue
            source = message.source or _ROLE_TO_SOURCE.get(message.role, "user")
            verdict = self._sanitizer.classify(message.content)
            if verdict is InjectionVerdict.HARD:
                return self._refuse("hard_injection_in_message")
            try:
                wrapped = self._sanitizer.sanitize(message.content, source=source)
            except SecurityViolation:
                return self._refuse("hard_injection_in_message")
            sanitized.append(
                ModelMessage(role=message.role, content=wrapped, source=source, tool_call_id=message.tool_call_id)
            )
        return sanitized

    async def execute(self, command: ModelInvokeCommand) -> ModelInvokeResult:
        prompt_violation = self._validate_system_prompt(command)
        if prompt_violation is not None:
            self._record_invocation(command.persona, False)
            return prompt_violation

        sanitized_or_violation = self._sanitize_messages(command.messages)
        if isinstance(sanitized_or_violation, ModelInvokeResult):
            self._record_invocation(command.persona, False)
            return sanitized_or_violation
        sanitized_messages = sanitized_or_violation

        model = command.model or self._default_model
        litellm_messages = [{"role": "system", "content": command.system_prompt}] + [
            _to_litellm_message(m) for m in sanitized_messages
        ]
        try:
            raw = await self._complete(
                model=model,
                messages=litellm_messages,
                temperature=command.temperature,
                max_tokens=command.max_tokens,
                tools=command.tools,
                tool_choice=command.tool_choice,
            )
        except Exception as exc:
            self._record_invocation(command.persona, False)
            return ModelInvokeResult(success=False, model=model, error=str(exc))

        content = str(raw.get("content", ""))
        if self._guardrails.detect_prompt_leakage(content):
            self._record_invocation(command.persona, False)
            return self._refuse("output_leakage_blocked")

        self._record_invocation(command.persona, True)
        return ModelInvokeResult(
            success=True,
            content=content,
            model=model,
            usage=raw.get("usage", {}),
            tool_calls=raw.get("tool_calls", []),
        )

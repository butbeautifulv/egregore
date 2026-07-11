from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from cys_core.domain.parsing.json_text import parse_json_text

T = TypeVar("T", bound=BaseModel)


class ToolInstantiator:
    """Parse model text into a Pydantic schema (Iron-agent fallback)."""

    def schema_to_prompt(self, model: type[BaseModel]) -> str:
        schema = model.model_json_schema()
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        lines: list[str] = ["Respond with a single JSON object matching this schema:", "{"]
        for name, field in props.items():
            req = "required" if name in required else "optional"
            desc = field.get("description", "")
            ftype = field.get("type", "any")
            lines.append(f'  "{name}": ({req}, {ftype}) {desc}')
        lines.append("}")
        return "\n".join(lines)

    def parse_once(self, text: str, model: type[T]) -> T:
        data = parse_json_text(text)
        if data is None:
            raise ValueError("no JSON object in model response")
        return model.model_validate(data)

    def parse_with_retry(
        self,
        invoke: Callable[[str], str],
        model: type[T],
        *,
        initial_prompt: str,
        max_retries: int = 3,
    ) -> T:
        prompt = initial_prompt
        last_error = "unknown"
        for attempt in range(max_retries):
            text = invoke(prompt)
            try:
                return self.parse_once(text, model)
            except (ValidationError, ValueError) as exc:
                last_error = str(exc)
                prompt = (
                    f"{initial_prompt}\n\nPrevious response was invalid: {last_error}. "
                    "Return valid JSON only."
                )
        raise ValueError(f"failed after {max_retries} retries: {last_error}")

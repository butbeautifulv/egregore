from __future__ import annotations

import json
from typing import Any

from cys_core.application.use_cases.extract_structured_output import (
    build_structured_extraction_prompt,
    parse_structured_output,
)
from cys_core.benchmarks.gaia_normalizer import normalize_gaia_answer
from cys_core.llm.reasoning import get_reasoning_model_connector

_GAIA_ANSWER_TYPES = ("number", "date", "time", "string")


def detect_gaia_answer_type(question: str) -> str:
    try:
        from bootstrap.settings import get_settings

        if get_settings().reasoning_model.strip():
            prompt = (
                "Determine expected GAIA answer type for this question. "
                "Reply with exactly one word: number, date, time, or string.\n\n"
                f"Question: {question}"
            )
            model = get_reasoning_model_connector().create_model()
            response = model.invoke(prompt)
            text = str(getattr(response, "content", response)).strip().lower()
            for kind in _GAIA_ANSWER_TYPES:
                if kind in text:
                    return kind
    except Exception:
        pass
    lower = question.lower()
    if "how many" in lower or "number" in lower:
        return "number"
    if "date" in lower or "when" in lower:
        return "date"
    if "time" in lower:
        return "time"
    return "string"


def extract_gaia_final_answer(*, question: str, summary: str, answer_type: str | None = None) -> dict[str, Any]:
    kind = answer_type or detect_gaia_answer_type(question)
    structured: dict[str, Any] = {}
    try:
        from bootstrap.settings import get_settings

        if get_settings().reasoning_model.strip():
            prompt = build_structured_extraction_prompt(
                goal=question,
                schema_type=f"gaia_{kind}",
                agent_summary=summary,
            )
            prompt += (
                "\nFor GAIA: put the final short answer in payload.answer. "
                "Use digits only for numbers. Use minimal string phrasing."
            )
            model = get_reasoning_model_connector().create_model()
            response = model.invoke(prompt)
            text = str(getattr(response, "content", response))
            structured = parse_structured_output(text)
    except Exception:
        structured = {}
    raw_answer = ""
    payload = structured.get("payload")
    if isinstance(payload, dict):
        raw_answer = str(payload.get("answer", payload.get("summary", "")))
    if not raw_answer:
        raw_answer = summary.strip().splitlines()[-1] if summary.strip() else ""
    normalized = normalize_gaia_answer(raw_answer, answer_type=kind)
    return {
        "answer_type": kind,
        "raw_answer": raw_answer,
        "normalized_answer": normalized,
        "structured": structured,
    }


async def run_gaia_solver(question: str, *, file_path: str = "") -> dict[str, Any]:
    from bootstrap.container import get_container
    from cys_core.application.use_cases.run_step import RunStep
    from cys_core.domain.runs.models import InteractionMode, RunContext
    from cys_core.infrastructure.catalog.catalog_registry import get_agent_catalog
    from cys_core.infrastructure.runs.factory import get_run_state_store, get_work_todo_store
    from cys_core.runtime.agent import get_runtime

    get_container().wire_agent_definitions_loader()
    ctx = RunContext.one_shot_job("gaia-bench", mode=InteractionMode.AGENT, profile_id="gaia-bench")
    payload = {"goal": question, "input": question}
    if file_path:
        payload["attachments"] = [{"path": file_path, "name": file_path.rsplit("/", 1)[-1]}]
    step = RunStep(
        runtime=get_runtime(),
        state_store=get_run_state_store(),
        catalog=get_agent_catalog(),
        todo_store=get_work_todo_store(),
        judge_backend=get_container().get_judge_backend(),
        context_summarizer=get_container().get_context_summarizer(),
        reflexion_store=get_container().get_reflexion_store(),
        policy_port=get_container().get_profile_policy_port(),
    )
    out = await step.execute(ctx, json.dumps(payload, ensure_ascii=False), persona="gaia_solver")
    result = out.get("result") if isinstance(out, dict) else {}
    summary = ""
    if isinstance(result, dict):
        summary = str(result.get("reply", result))
    extraction = extract_gaia_final_answer(question=question, summary=summary)
    return {
        "run": out,
        "extraction": extraction,
        "prediction": extraction["normalized_answer"],
    }

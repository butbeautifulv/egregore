from __future__ import annotations

from cys_core.application.workers.tool_execution_tracker import tool_succeeded
from cys_core.domain.workers.models import WorkerJob


def retry_nudge(
    job: WorkerJob,
    prompt: str,
    *,
    attempt: int,
    planned_tool_calls: bool,
    tools_executed: int,
    grounding_gaps: list[str] | None = None,
) -> tuple[str, str] | None:
    if attempt >= 2 or job.profile_id != "cybersec-soc":
        return None
    if grounding_gaps:
        note = "Previous SocFinding failed evidence grounding: " + ", ".join(grounding_gaps)
        return prompt + f"\n\n[System] {note}", "grounding"
    if attempt == 0 and planned_tool_calls and tools_executed == 0:
        return prompt + "\n\n[System] Invoke tools through native tool calling only.", "tool_retry"
    if job.persona == "soc" and tool_succeeded(job.job_id, "investigate_incident"):
        note = "investigate_incident succeeded. Emit SocFinding JSON now citing evidence observations."
        return prompt + f"\n\n[System] {note}", "siem_finding"
    if job.persona == "intel" and (
        tool_succeeded(job.job_id, "enrich_ioc") or tool_succeeded(job.job_id, "ti_search_in_category")
    ):
        return prompt + "\n\n[System] TI enrichment succeeded. Emit IntelFinding JSON now.", "intel_finding"
    if job.persona == "consultant" and tool_succeeded(job.job_id, "load_skill"):
        return prompt + "\n\n[System] load_skill complete. Emit ConsultantFinding JSON now.", "consultant_finding"
    return None

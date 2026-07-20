from __future__ import annotations

import re

_BUS_JOB_ID_RE = re.compile(r"^[a-z][a-z0-9]*-bus-")


def is_bus_worker_job_id(job_id: str) -> bool:
    """True for revision/delegate worker jobs like soc-bus-9e20b125."""
    return bool(_BUS_JOB_ID_RE.match(job_id))

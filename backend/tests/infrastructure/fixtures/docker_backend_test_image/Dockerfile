# Minimal stand-in image for DockerExecutionBackend's own integration test —
# NOT the real egregore worker image. Provides a fake `uv` on PATH so
# `docker run -i <image> uv run egregore run-sandboxed-job --job-json -`
# (DockerExecutionBackend's hardcoded invocation) exercises the real
# docker-run/stdin/stdout plumbing without needing the full project image.
FROM python:3.13-slim
COPY fake_sandboxed_job_child.py /app/fake_sandboxed_job_child.py
RUN printf '#!/bin/sh\nexec python3 /app/fake_sandboxed_job_child.py echo\n' > /usr/local/bin/uv \
    && chmod +x /usr/local/bin/uv

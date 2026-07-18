from __future__ import annotations

import pytest

from cys_core.observability import langfuse_client


@pytest.mark.unit
def test_langfuse_client_delegates_to_trace_backend(monkeypatch):
  calls: list[str] = []

  class FakeBackend:
    def flush(self):
      calls.append("flush")

    def shutdown(self):
      calls.append("shutdown")

  monkeypatch.setattr(langfuse_client, "_trace_backend", lambda: FakeBackend())
  langfuse_client.flush_langfuse()
  langfuse_client.shutdown_langfuse()
  assert calls == ["flush", "shutdown"]

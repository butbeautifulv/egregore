from __future__ import annotations

import pytest

from cys_core.observability import langfuse_client


@pytest.mark.unit
def test_langfuse_client_delegates_to_trace_backend(monkeypatch):
  calls: list[str] = []

  class FakeBackend:
    def get_callback_handler(self):
      calls.append("handler")
      return object()

    def flush(self):
      calls.append("flush")

    def shutdown(self):
      calls.append("shutdown")

  monkeypatch.setattr(langfuse_client, "_trace_backend", lambda: FakeBackend())
  assert langfuse_client.get_langfuse_callback_handler() is not None
  langfuse_client.flush_langfuse()
  langfuse_client.shutdown_langfuse()
  assert calls == ["handler", "flush", "shutdown"]

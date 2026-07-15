from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class HttpTimeoutSettings:
    connect_s: float = 10.0
    read_s: float = 60.0


@dataclass(frozen=True)
class DockerSandboxSettings:
    probe_timeout_s: float = 5.0
    kill_timeout_s: float = 10.0


@dataclass(frozen=True)
class EgressStreamingSettings:
    output_preview_max: int = 4096
    batch_seconds: float = 0.25


@dataclass(frozen=True)
class WaybackSettings:
    api_timeout_s: float = 30.0


_http_timeouts = HttpTimeoutSettings()
_docker_sandbox = DockerSandboxSettings()
_egress_streaming = EgressStreamingSettings()
_wayback = WaybackSettings()


def configure_http_timeouts(*, connect_s: float, read_s: float) -> None:
    global _http_timeouts
    _http_timeouts = HttpTimeoutSettings(connect_s=connect_s, read_s=read_s)


def get_http_timeouts() -> HttpTimeoutSettings:
    return _http_timeouts


def configure_docker_sandbox_settings(*, probe_timeout_s: float, kill_timeout_s: float) -> None:
    global _docker_sandbox
    _docker_sandbox = DockerSandboxSettings(
        probe_timeout_s=probe_timeout_s,
        kill_timeout_s=kill_timeout_s,
    )


def get_docker_sandbox_settings() -> DockerSandboxSettings:
    return _docker_sandbox


def configure_egress_streaming_settings(*, output_preview_max: int, batch_seconds: float) -> None:
    global _egress_streaming
    _egress_streaming = EgressStreamingSettings(
        output_preview_max=output_preview_max,
        batch_seconds=batch_seconds,
    )


def get_egress_streaming_settings() -> EgressStreamingSettings:
    return _egress_streaming


def configure_wayback_settings(*, api_timeout_s: float) -> None:
    global _wayback
    _wayback = WaybackSettings(api_timeout_s=api_timeout_s)


def get_wayback_settings() -> WaybackSettings:
    return _wayback

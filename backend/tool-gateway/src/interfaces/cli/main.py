from __future__ import annotations

import argparse
import asyncio
import json
import sys

from bootstrap.container import get_container
from bootstrap.settings import settings
from cys_core.observability.logging_setup import configure_logging
from cys_core.observability.otel import setup_otel
from cys_core.observability.prometheus_setup import register_multiprocess_shutdown


def cmd_tool_gateway(args: argparse.Namespace) -> int:
    from interfaces.gateways.tool.server import serve_forever

    get_container()
    configure_logging("egregore-tool-gateway")
    setup_otel(service_name="egregore-tool-gateway")
    host = args.host or settings.tool_gateway_bind_host
    port = args.port or settings.tool_gateway_bind_port
    print(json.dumps({"service": "tool-gateway", "host": host, "port": port}, indent=2))
    asyncio.run(serve_forever(host, port))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Egregore MCP Tool Gateway")
    sub = parser.add_subparsers(dest="command", required=True)

    tool_gateway = sub.add_parser("tool-gateway", help="Run the MCP Tool Gateway (PEP for sandboxed tool calls)")
    tool_gateway.add_argument("--host", default=None, help="Bind host. Default: TOOL_GATEWAY_BIND_HOST")
    tool_gateway.add_argument("--port", type=int, default=None, help="Bind port. Default: TOOL_GATEWAY_BIND_PORT")
    tool_gateway.set_defaults(func=cmd_tool_gateway)

    return parser


def main() -> None:
    register_multiprocess_shutdown()
    get_container()
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()

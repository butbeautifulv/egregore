from __future__ import annotations

import asyncio
import json
import logging

from bootstrap.container import get_container
from bootstrap.settings import get_settings


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    from interfaces.gateways.model.server import serve_forever

    get_container()
    settings = get_settings()
    print(json.dumps({"service": "model-gateway", "host": settings.host, "port": settings.port}, indent=2))
    asyncio.run(serve_forever(settings.host, settings.port))


if __name__ == "__main__":
    main()

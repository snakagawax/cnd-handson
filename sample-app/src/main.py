import logging
import os
import random
import signal
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from enum import Enum
from logging import getLogger
from typing import Annotated, Final, override

from fastapi import Depends, FastAPI, status
from prometheus_client import generate_latest
from redis import RedisError
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.responses import Response

import database
from logger.logger import LoggerName

LOGGER: Final = getLogger(LoggerName.DEFAULT.value)


class Colors(Enum):
    """Enum class representing colors."""

    RED = "red"
    BLUE = "blue"
    GREEN = "green"


class LoggingMiddleware(BaseHTTPMiddleware):
    """Logging middleware class for logging HTTP requests and responses."""

    @override
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Override method that logs for specific API requests."""
        path: str = request.url.path
        response: Response = await call_next(request)
        if path.startswith(APP_API_PREFIX):
            LOGGER.info(f"{request.method} {path} {response.status_code}")
        return response


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    redis_client = _redis_factory()
    ping_err: RedisError | None = await redis_client.ping()
    if ping_err:
        LOGGER.critical(f"Failed to connect to Redis: {ping_err}")
        import os

        os.kill(os.getpid(), signal.SIGKILL)
    # NOTE:
    # Flush all keys in the database before starting the program to prevent
    # unnecessary data accumulation.
    # The program will continue to run even if the flush operation fails.
    if await aredis_client.keys_exist():
        LOGGER.info(
            "Some keys exist in the database. "
            "Flushing all keys before starting the program."
        )
        try:
            await aredis_client.flushall()
        except RedisError as redis_err:
            LOGGER.error(
                f"Failed to flush all keys in the database: {redis_err}"
            )
    yield
    LOGGER.info("Closing the Redis connectoin")
    await aredis_client.close_connection()


app = FastAPI(lifespan=lifespan, title="color service", docs_url=None)


@app.get("/healthz")
def healthcheck() -> int:
    """
    Perform a health check and return the HTTP status code indicating success.

    Returns:
        int: The HTTP status code indicating success (200 OK).
    """
    return status.HTTP_200_OK


@app.get("/metrics")
def get_metrics() -> bytes:
    """
    Retrieves the metrics data.

    Returns:
        The metrics data in the Prometheus format.
    """
    return generate_latest()


@app.get("/api/color")
async def get_color(
    redis_client: Annotated[RedisSingleton, Depends(_redis_factory)],
) -> dict[str, str]:
    color: str = random.choice(
        [color.value for color in Colors.__members__.values()]
    )
    color = random.choice(
        [color.value for color in Colors.__members__.values()]
    )
    set_key_err = await redis_client.set_key(
        str(int(time.time() * 1000)), color
    )
    if set_key_err:
        LOGGER.error(f"Failed to set key in Redis: {set_key_err}")
    return {"color": color}


@app.get("/api/stats")
async def get_colors(
    redis_client: Annotated[RedisSingleton, Depends(_redis_factory)],
) -> dict[str, int | None]:
    total: int = 0
    colors: dict[str, int] = {
        Colors.RED.value: 0,
        Colors.BLUE.value: 0,
        Colors.GREEN.value: 0,
    }
    try:
        async for result in aredis_client.get_colors():
            match result:
                case Colors.RED.value:
                    colors[Colors.RED.value] += 1
                case Colors.BLUE.value:
                    colors[Colors.BLUE.value] += 1
                case Colors.GREEN.value:
                    colors[Colors.GREEN.value] += 1
            total += 1
    except RedisError as redis_err:
        LOGGER.error(f"Failed to retrieve colors from Redis: {redis_err}")
        return {}
    return {
        "total": total,
        Colors.RED.value: colors[Colors.RED.value],
        Colors.BLUE.value: colors[Colors.BLUE.value],
        Colors.GREEN.value: colors[Colors.GREEN.value],
    }


if __name__ == "__main__":
    # NOTE:
    # Run "python main.py" only for local development.
    import uvicorn

    port: str | None = os.getenv("PORT")
    uvicorn.run(
        app="main:app",
        port=int(port) if port else DEFAULT_PORT,
        log_config="logger/logging_override.ini",
        log_level="debug",
        lifespan="on",
        reload=True,
    )

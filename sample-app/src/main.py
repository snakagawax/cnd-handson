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

from fastapi import APIRouter, Depends, FastAPI, Request, status
from prometheus_client import generate_latest
from fastapi.middleware.cors import CORSMiddleware
from redis import RedisError
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.responses import Response

import database
from logger.logger import LoggerName

APP_API_PREFIX: Final[str] = "/api"
DEFAULT_PORT: Final[int] = 8000
LOGGER: Final[logging.Logger] = getLogger(LoggerName.DEFAULT.value)


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
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    A generator function that handles the lifespan events of
    the FastAPI application.

    Args:
        app (FastAPI): The FastAPI application instance.
        (never used in this function, but need to explicitly define it for
        lifespan event handling; otherwise, FastAPI will raise an exception.)

    Yields:
        None

    Returns:
        None
    """
    aredis_client = database.redis_factory()
    ping_err: RedisError | None = await aredis_client.ping()
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


system_router = APIRouter()


@system_router.get("/healthz")
def healthcheck() -> int:
    """
    Perform a health check and return the HTTP status code indicating success.

    Returns:
        int: The HTTP status code indicating success (200 OK).
    """
    return status.HTTP_200_OK


@system_router.get("/metrics")
def get_metrics() -> bytes:
    """
    Collects the metrics in a Prometheus format.

    Returns:
        bytes: The metrics data in bytes format.
    """
    return generate_latest()


app_router = APIRouter()


@app_router.get("/color")
async def get_color(
    aredis_client: Annotated[
        database.RedisSingleton, Depends(database.redis_factory)
    ],
) -> dict[str, str] | None:
    """
    Pick up a random color from the color selection and store it in
    the database.

    Args:
        aredis_client (db.RedisSingleton): The Redis client instance

    Returns:
        dict[str, str]: A dictionary containing the color
    """
    color: str = random.choice(
        [color.value for color in Colors.__members__.values()]
    )
    color = random.choice(
        [color.value for color in Colors.__members__.values()]
    )
    set_key_err = await aredis_client.set_key(
        str(int(time.time() * 1000)), color
    )
    if set_key_err:
        LOGGER.error(f"Failed to set key in Redis: {set_key_err}")
        return None
    return {"color": color}


@app_router.get("/stats")
async def get_colors(
    aredis_client: Annotated[
        database.RedisSingleton, Depends(database.redis_factory)
    ],
) -> dict[str, int]:
    """
    Calculate the count of colors from a Redis database.

    Args:
        aredis_client (db.RedisSingleton): The Redis client instance.

    Returns:
        dict[str, int | None]:
            A dictionary containing the total count and individual counts
            of colors. The keys represent the color names and the values
            represent the respective counts.
    """
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


api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(app_router, prefix=APP_API_PREFIX)
app = FastAPI(lifespan=lifespan, title="color service", docs_url=None)
app.include_router(api_router)
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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

import random
import signal
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from enum import Enum
from logging import getLogger
from typing import Annotated, Final

from fastapi import Depends, FastAPI, status
from prometheus_client import generate_latest
from redis import RedisError

from database import RedisSingleton
from logger.logger import LoggerName

LOGGER: Final = getLogger(LoggerName.DEFAULT.value)


class Colors(Enum):
    """Enum class representing different colors."""

    RED = "red"
    BLUE = "blue"
    GREEN = "green"


def _redis_factory() -> RedisSingleton:
    """Factory function to create a Redis client."""
    return RedisSingleton()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    redis_client = _redis_factory()
    ping_err: RedisError | None = await redis_client.ping()
    if ping_err:
        LOGGER.critical(f"Failed to connect to Redis: {ping_err}")
        import os

        os.kill(os.getpid(), signal.SIGKILL)
    # NOTE:
    # 無用なデータ蓄積を防ぐためにRedisにデータが存在する場合は削除。
    # (前回のアプリケーション停止の際にDBのflushが失敗した場合の対策)
    if await redis_client.keys_exist():
        LOGGER.info(
            "Some keys exist in the database. "
            "Flushing all keys before starting the program."
        )
        # NOTE:
        # DBのflushに失敗してもアプリケーションは起動したいので、
        # エラーハンドリングは実施しない。
        await redis_client.flushall()
    yield
    flush_err: RedisError | None = await redis_client.flushall()
    if flush_err:
        LOGGER.error(f"Failed to flush the database: {flush_err}")
    LOGGER.info("Closing the Redis connectoin")
    await redis_client.close_connection()


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
        async for result in redis_client.get_colors():
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
    return {
        "total": total,
        Colors.RED.value: colors.get(Colors.RED.value),
        Colors.BLUE.value: colors.get(Colors.BLUE.value),
        Colors.GREEN.value: colors.get(Colors.GREEN.value),
    }


if __name__ == "__main__":
    # NOTE:
    # Run "python main.py" only for local development.
    import uvicorn

    uvicorn.run(
        app="main:app",
        port=8000,
        log_config="logger/logging_override.ini",
        log_level="debug",
        reload=True,
    )

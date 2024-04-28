import logging
import os
from collections.abc import AsyncGenerator
from logging import getLogger
from typing import Final, Optional

import redis.asyncio as aredis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import (
    BusyLoadingError,
    ConnectionError,
    RedisError,
    TimeoutError,
)

from logger.logger import LoggerName

LOGGER: Final[logging.Logger] = getLogger(LoggerName.DEFAULT.value)
REDIS_DEFAULTPORT: Final[int] = 6379
REDIS_DEFAULT_DB: Final[int] = 0


class RedisSingleton:
    """A singleton class for managing a Redis connection.

    Attributes:
        _instance (RedisSingleton): The singleton instance of the class.
        _initialized (bool): Flag indicating if the class has been initialized.
    """

    _instance: Optional["RedisSingleton"] = None
    _initialized: bool = False

    def __new__(cls, *args, **kwargs) -> "RedisSingleton":  # type: ignore[no-untyped-def]
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        host: str,
        port: int = REDIS_DEFAULTPORT,
        db: int = REDIS_DEFAULT_DB,
    ) -> None:
        """Initializes a RedisSingleton instance.

        Args:
            host (str):
                The Redis server host.
            port (int, optional):
                The Redis server port[default: REDIS_DEFAULT_PORT].
            db (int, optional):
                The Redis database number[default: REDIS_DEFAULT_DB].
        """
        if not self._initialized:
            self._client = aredis.Redis(
                host=host,
                port=port,
                db=db,
                retry=Retry(ExponentialBackoff(), 5),
                retry_on_error=[
                    BusyLoadingError,
                    ConnectionError,
                    TimeoutError,
                ],
                single_connection_client=True,
                decode_responses=True,
            )
            self._initialized = True

    async def ping(self) -> RedisError | None:
        """
        Pings the Redis server to check if it is reachable.

        Returns:
            RedisError | None:
                If there is a connection error, returns the
                ConnectionError object; otherwise, returns None.
        """
        try:
            await self._client.ping()
        except ConnectionError as err:
            return err
        return None

    async def keys_exist(self) -> bool:
        """Checks if any keys exist in the Redis database.

        Returns:
            bool: True if keys exist, False otherwise.
        """
        return await self._client.dbsize() > 0

    async def set_key(self, key: str, value: str) -> RedisError | None:
        """
        Sets the given key-value pair in the Redis database.

        Args:
            key (str): The key to set.
            value (str): The value to associate with the key.

        Returns:
            RedisError or None:
                If an error occurs while setting the key, returns the
                RedisError; otherwise, returns None.
        """
        try:
            await self._client.set(key, value)
        except ConnectionError as err:
            return err
        return None

    async def get_colors(
        self,
    ) -> AsyncGenerator[str, RedisError | None]:
        """
        Retrieves colors from the database.

        Yields:
            str: A color value retrieved from the database.

        Raises:
            RedisError:
                If there is an error while retrieving colors from
                the database.
        """
        try:
            async for key in self._client.scan_iter():
                value = await self._client.get(key)
                if value is not None:
                    yield value
        except RedisError as redis_err:
            raise redis_err

    async def flushall(self) -> RedisError | None:
        """
        Flushes all keys from the Redis database.

        Returns:
            RedisError: If there is an error flushing the database.
            None: If the database is successfully flushed.
        """
        try:
            await self._client.flushdb(asynchronous=True)
        except RedisError as redis_err:
            return redis_err
        return None

    async def close_connection(self) -> None:
        """Closes the Redis connection."""
        await self._client.close()


def redis_factory() -> RedisSingleton:
    """
    Factory function to create a RedisSingleton instance.

    Returns:
        RedisSingleton: An instance of RedisSingleton.
    """
    host: str = os.getenv("REDIS_HOST", "localhost")
    return RedisSingleton(host=host)

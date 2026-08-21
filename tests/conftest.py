import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if TEST_DATABASE_URL is None:
    raise pytest.UsageError("TEST_DATABASE_URL must be set for PostgreSQL tests")

parsed_test_url = make_url(TEST_DATABASE_URL)
test_database_name = parsed_test_url.database or ""
if parsed_test_url.get_backend_name() != "postgresql":
    raise pytest.UsageError("TEST_DATABASE_URL must use PostgreSQL")
if "test" not in test_database_name.lower():
    raise pytest.UsageError("Test database name must contain 'test'")

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.db import Base, get_session  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture
async def session_factory(
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    test_engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
    )

    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    try:
        yield factory
    finally:
        async with test_engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
        await test_engine.dispose()


@pytest_asyncio.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_session, None)

"""Legacy adapters fail closed without contacting PostgreSQL or Redis."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("asyncpg")
pytest.importorskip("pydantic_settings")
pytest.importorskip("redis")
pytest.importorskip("fastapi")

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from src.api.dependencies import optional_api_key, verify_api_key
from src.api.middleware import AuthenticationMiddleware
from src.database.client import DatabaseClient
from src.database.connection import DatabaseManager


@pytest.fixture
def fake_session(monkeypatch):
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock(), close=AsyncMock())
    monkeypatch.setattr(DatabaseManager, "get_session_factory", classmethod(lambda cls: lambda: session))
    return session


@pytest.mark.asyncio
async def test_database_client_commits_and_closes_successful_context(fake_session):
    async with DatabaseClient() as client:
        assert client.session is fake_session
        fake_session.commit.assert_not_awaited()
    fake_session.commit.assert_awaited_once()
    fake_session.rollback.assert_not_awaited()
    fake_session.close.assert_awaited_once()
    assert client.session is None


@pytest.mark.asyncio
async def test_database_client_forwards_body_exception_for_rollback(fake_session):
    failure = ValueError("operation failed")
    with pytest.raises(ValueError) as captured:
        async with DatabaseClient():
            raise failure
    assert captured.value is failure
    fake_session.commit.assert_not_awaited()
    fake_session.rollback.assert_awaited_once()
    fake_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_database_client_does_not_swallow_commit_failure(fake_session):
    failure = RuntimeError("commit failed")
    fake_session.commit.side_effect = failure
    with pytest.raises(RuntimeError) as captured:
        async with DatabaseClient():
            pass
    assert captured.value is failure
    fake_session.rollback.assert_awaited_once()
    fake_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_database_client_closes_if_repository_setup_fails(fake_session, monkeypatch):
    def broken_repository(session):
        raise ValueError("repository setup failed")

    monkeypatch.setattr("src.database.client.CompanyRepository", broken_repository)
    with pytest.raises(ValueError, match="repository setup failed"):
        async with DatabaseClient():
            pytest.fail("context should not open")
    fake_session.commit.assert_not_awaited()
    fake_session.rollback.assert_awaited_once()
    fake_session.close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("configured,presented", [("", "arbitrary-long-api-key"), ("secret", "wrong"), ("secret", None)])
async def test_legacy_key_dependency_rejects_missing_configuration_and_bad_keys(configured, presented):
    with pytest.raises(HTTPException) as captured:
        await verify_api_key(presented, SimpleNamespace(api_secret_key=configured))
    assert captured.value.status_code == 401


@pytest.mark.asyncio
async def test_legacy_key_dependency_accepts_only_configured_key():
    settings = SimpleNamespace(api_secret_key="configured-secret")
    assert await verify_api_key("configured-secret", settings) == "configured-secret"
    assert await optional_api_key("arbitrary-long-api-key", settings) is None
    assert await optional_api_key("arbitrary-long-api-key", SimpleNamespace(api_secret_key="")) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("configured,presented,status,authenticated", [
    ("", "arbitrary-long-api-key", 401, False),
    ("configured-secret", "wrong-but-long-enough", 401, False),
    ("configured-secret", "configured-secret", 200, True),
    ("", None, 200, False),
])
async def test_legacy_middleware_never_marks_unverified_key_authenticated(configured, presented, status, authenticated):
    request = Request({
        "type": "http", "method": "GET", "path": "/api/v1/example",
        "headers": [(b"x-api-key", presented.encode())] if presented else [],
    })
    downstream = AsyncMock(return_value=JSONResponse({"ok": True}))
    middleware = AuthenticationMiddleware(AsyncMock(), api_secret_key=configured)
    response = await middleware.dispatch(request, downstream)
    assert response.status_code == status
    assert request.state.is_authenticated is authenticated
    if status == 401:
        downstream.assert_not_awaited()
        assert request.state.api_key is None
    else:
        downstream.assert_awaited_once()

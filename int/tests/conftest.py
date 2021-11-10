"""Common fixtures for testing."""

import asyncio
import pytest
from typing import Union, Optional, Iterator
import httpx
import hashlib
import os

# TODO: Remove debugging tools before final commit
import logging

from acapy_client import Client
from acapy_client.models import (
    ConnectionStaticResult,
    ConnectionStaticRequest,
    ConnectionMetadataSetRequest
)
from acapy_client.models.conn_record import ConnRecord
from acapy_client.api.connection import (
    create_static,
    delete_connection,
    set_metadata,
)

from aries_staticagent.connection import Connection as StaticConnection
from aries_staticagent.message import Message

from echo_agent.client import EchoClient
from echo_agent.models import ConnectionInfo as EchoConnection


LOGGER = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def event_loop():
    """Create a session scoped event loop.
    pytest.asyncio plugin provides a default function scoped event loop
    which cannot be used as a dependency to session scoped fixtures.
    """
    return asyncio.get_event_loop()


@pytest.fixture(scope="session")
def backchannel():
    """Yield backchannel client."""
    endpoint = os.environ.get("ADMIN_ENDPOINT")
    yield Client(base_url=endpoint)


@pytest.fixture(scope="session")
def echo_seed():
    yield hashlib.sha256(b"acapy-pickup-int-test-runner").hexdigest()[:32]


@pytest.fixture(scope="session")
def agent_seed():
    yield hashlib.sha256(b"acapy-pickup-agent").hexdigest()[:32]


@pytest.fixture(scope="session")
def echo_endpoint():
    yield os.environ.get("ECHO_ENDPOINT")


@pytest.fixture(scope="session")
def agent_connection(
    echo_seed, agent_seed, echo_endpoint, backchannel
) -> Iterator[ConnectionStaticResult]:
    """Yield agent's representation of this connection."""

    # Create connection in agent under test
    create_result: Optional[ConnectionStaticResult] = create_static.sync(
        client=backchannel,
        json_body=ConnectionStaticRequest.from_dict(
            {
                "my_seed": agent_seed,
                "their_seed": echo_seed,
                "their_label": "test-runner",
            }
        ),
    )
    if not create_result:
        raise RuntimeError("Could not create static connection with agent under test")

    # Set admin metadata to enable access to admin protocols
    set_result = set_metadata.sync(
        client=backchannel,
        conn_id=create_result.record.connection_id,
        json_body=ConnectionMetadataSetRequest.from_dict(
            {"metadata": {"group": "admin"}}
        ),
    )
    if not set_result:
        raise RuntimeError("Could not set metadata on static connection")

    yield create_result

    delete_connection.sync(
        client=backchannel, conn_id=create_result.record.connection_id
    )


@pytest.fixture(scope="session")
def echo_agent(echo_endpoint: str):
    yield EchoClient(base_url=echo_endpoint)


@pytest.fixture
async def echo(echo_agent: EchoClient):
    async with echo_agent as client:
        yield client


@pytest.fixture(scope="session")
def conn_record(agent_connection: ConnectionStaticResult):
    yield agent_connection.record


@pytest.fixture(scope="session")
def connection_id(conn_record: ConnRecord):
    yield conn_record.connection_id


@pytest.fixture(scope="session", autouse=True)
async def connection(
    agent_connection: ConnectionStaticResult, echo_agent: EchoClient, echo_seed: str
):
    """Yield static connection to agent under test."""
    # Create and yield static connection
    async with echo_agent as echo:
        conn = await echo.new_connection(
            seed=echo_seed,
            endpoint=agent_connection.my_endpoint,
            their_vk=agent_connection.my_verkey,
        )
    yield conn
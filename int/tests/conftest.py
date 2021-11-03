"""Common fixtures for testing."""

import asyncio
import pytest
from typing import Union
import httpx

from acapy_client.models import ConnectionStaticResult
from acapy_client.models.conn_record import ConnRecord

from aries_staticagent import StaticConnection, Target
from aries_staticagent.message import Message

from echo_agent_client import Client as EchoClient
from echo_agent_client.models import Connection as EchoConnection
from echo_agent_client.api.default import retrieve_messages


class IntegrationTestConnection(StaticConnection):
    async def send_and_await_reply_async(
        self,
        msg: Union[dict, Message],
        *,
        return_route: str = "all",
        plaintext: bool = False,
        anoncrypt: bool = False,
        timeout: int = 1,
    ) -> Message:
        return await super().send_and_await_reply_async(
            msg,
            return_route=return_route,
            plaintext=plaintext,
            anoncrypt=anoncrypt,
            timeout=timeout,
        )


@pytest.fixture(scope="session")
def asynchronously_received_messages(
    echo_client: EchoClient, echo_connection: EchoConnection
):
    """Get asynchronously recevied messages from the echo agent."""
    # Could wipe left over messages here
    async def _asynchronously_received_messages(timeout: int = 5):
        timed_client = echo_client.with_timeout(timeout)
        try:
            messages = await retrieve_messages.asyncio(
                client=timed_client, connection_id=echo_connection.connection_id
            )
        except httpx.ReadTimeout:
            raise Exception(
                "Retrieving asynchronously recevied messages timed out"
            ) from None

        return messages

    yield _asynchronously_received_messages
    # Could wipe remaining messages here

@pytest.fixture(scope="session")
def connection_id(conn_record: ConnRecord):
    yield conn_record.connection_id

@pytest.fixture(scope="session")
def connection(agent_connection: ConnectionStaticResult, suite_seed: str):
    """Yield static connection to agent under test."""

    # Create and yield static connection
    yield IntegrationTestConnection.from_seed(
        seed=suite_seed.encode("ascii"),
        target=Target(
            endpoint=agent_connection.my_endpoint, their_vk=agent_connection.my_verkey
        ),
    )

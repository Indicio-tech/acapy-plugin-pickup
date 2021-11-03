"""Common fixtures for testing."""

import asyncio
import pytest
from typing import Union

from acapy_client.models import ConnectionStaticResult
from acapy_client.models.conn_record import ConnRecord

from aries_staticagent import StaticConnection, Target
from aries_staticagent.message import Message


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

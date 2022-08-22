import pytest
from echo_agent.client import EchoClient
from echo_agent.models import ConnectionInfo


@pytest.fixture
def message():
    yield {
        "connection_id": "conn_id",
        "status": "some_status",
        "recipient_key": "test_key",
        "message": "message_payload",
    }


@pytest.fixture()
async def mediation_request(echo: EchoClient, connection: ConnectionInfo, ws_endpoint):
    async with echo.session(connection, ws_endpoint) as session:
        request = await echo.send_message_to_session(
            session,
            {
                "@id": "123456781",
                "@type": "https://didcomm.org/coordinate-mediation/1.0/mediate-request",
            },
        )
    return request


@pytest.mark.asyncio
async def test_forward_event_received(
    echo: EchoClient,
    connection: ConnectionInfo,
    message,
    ws_endpoint,
    mediation_request,
):

    """Testing forward messages/events are received by the pickup plugin."""
    async with echo.session(connection, ws_endpoint) as session:
        await echo.send_message_to_session(
            session,
            {
                "@id": "123456781",
                "@type": "https://didcomm.org/coordinate-mediation/1.0/mediate-request",
            },
        )
        granted = await echo.get_message(connection, session=session)
        assert (
            granted["@type"]
            == "https://didcomm.org/coordinate-mediation/1.0/mediate-grant"
        )

        await echo.send_message_to_session(
            session,
            {
                "@id": connection.connection_id,
                "@type": "https://didcomm.org/coordinate-mediation/1.0/keylist-query",
                "paginate": {"limit": 30, "offset": 0},
            },
        )
        key_list = await echo.get_message(connection, session=session)
        print(key_list)
        assert False

    await echo.send_message(
        connection,
        {
            "type": "https://didcomm.org/routing/2.0/forward",
            "id": "forward_id",
            "to": ["did:example:mediator"],
            "body": {"next": "did:foo:1234abcd"},
            "attachments": [message["message"]],
        },
    )

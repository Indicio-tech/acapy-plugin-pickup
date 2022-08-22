from datetime import datetime

import pytest
from echo_agent.client import EchoClient
from echo_agent.models import ConnectionInfo


DIDCOMM_URI = "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/"


def msg_type(protocol_version_msg: str):
    return f"{DIDCOMM_URI}{protocol_version_msg}"


@pytest.fixture
def message():
    yield {
        "@type": msg_type("basicmessage/1.0/message"),
        "content": "test",
        "~l10n": {"locale": "en"},
        "sent_time": datetime.now().isoformat(),
    }


@pytest.fixture(scope="session")
async def mediation(echo: EchoClient, connection: ConnectionInfo, ws_endpoint):
    async with echo.session(connection, ws_endpoint) as session:
        await echo.send_message_to_session(
            session,
            {
                "@id": "123456781",
                "@type": msg_type("coordinate-mediation/1.0/mediate-request"),
                "~transport": {"return_route": "all"},
            },
        )
        granted = await echo.get_message(
            connection,
            msg_type=msg_type("coordinate-mediation/1.0/mediate-grant"),
            session=session,
        )
        assert granted
    yield granted


@pytest.fixture()
async def mediated_connection(
    echo: EchoClient,
    connection: ConnectionInfo,
    ws_endpoint: str,
    mediation: dict,
    echo_seed: str,
):
    async with echo.session(connection, ws_endpoint) as session:
        await echo.send_message_to_session(
            session,
            {
                "@type": msg_type("coordinate-mediation/1.0/keylist-update"),
                "updates": [{"recipient_key": connection.verkey, "action": "add"}],
                "~transport": {"return_route": "all"},
            },
        )
        response = await echo.get_message(
            connection=connection,
            session=session,
            msg_type=msg_type("coordinate-mediation/1.0/keylist-update-response"),
        )
        assert response["updated"]
        assert response["updated"][0]["result"] == "success"

    mediated_conn = await echo.new_connection(
        seed=echo_seed,
        endpoint=mediation["endpoint"],
        recipient_keys=[connection.verkey],
        routing_keys=mediation["routing_keys"],
    )

    yield mediated_conn

    async with echo.session(connection, ws_endpoint) as session:
        await echo.send_message_to_session(
            session,
            {
                "@type": msg_type("coordinate-mediation/1.0/keylist-update"),
                "updates": [{"recipient_key": connection.verkey, "action": "remove"}],
                "~transport": {"return_route": "all"},
            },
        )
        response = await echo.get_message(
            connection=connection,
            session=session,
            msg_type=msg_type("coordinate-mediation/1.0/keylist-update-response"),
        )
        assert response["updated"]
        assert response["updated"][0]["result"] == "success"


@pytest.mark.asyncio
async def test_forward_event_received(
    echo: EchoClient,
    connection: ConnectionInfo,
    mediated_connection: ConnectionInfo,
    message: dict,
    ws_endpoint,
):

    """Testing forward messages/events are received by the pickup plugin."""
    async with echo.session(
        mediated_connection, ws_endpoint
    ) as mediated_session, echo.session(connection, ws_endpoint) as session:
        await echo.send_message_to_session(
            mediated_session,
            message,
        )
        forwarded = await echo.get_message(
            connection=connection,
            session=session,
            msg_type=msg_type("basicmessage/1.0/message"),
        )
        print(forwarded)
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

import pytest
from echo_agent.client import ConnectionInfo, EchoClient


@pytest.mark.asyncio
async def test_messages_received_no_id(
    echo: EchoClient, connection: ConnectionInfo, ws_endpoint: str
):
    """Testing that an empty ID list does not alter the queue."""

    async with echo.session(connection, ws_endpoint) as session:
        await echo.send_message_to_session(
            session,
            {
                "@type": "https://didcomm.org/messagepickup/2.0/status-request",
                "~transport": {"return_route": "all"},
            },
        )
        initial_status = await echo.get_message(
            connection,
            session=session,
            msg_type="https://didcomm.org/messagepickup/2.0/status",
        )
    inital_count = initial_status["message_count"]

    async with echo.session(connection, ws_endpoint) as session:
        await echo.send_message_to_session(
            session,
            {
                "@type": "https://didcomm.org/messagepickup/2.0/messages-received",
                "message_id_list": [],
                "~transport": {"return_route": "all"},
            },
        )

        final_status = await echo.get_message(
            connection,
            session=session,
            msg_type="https://didcomm.org/messagepickup/2.0/status",
        )
    final_count = final_status["message_count"]
    assert inital_count == final_count


@pytest.mark.asyncio
async def test_messages_received_with_id(
    echo: EchoClient, connection: ConnectionInfo, ws_endpoint: str
):
    """Testing that accurate ID's remove messages from the queue."""

    async with echo.session(connection, ws_endpoint) as session:
        await echo.send_message_to_session(
            session,
            {
                "@type": "https://didcomm.org/messagepickup/2.0/status-request",
                "~transport": {"return_route": "all"},
            },
        )
        initial_status = await echo.get_message(
            connection,
            session=session,
            msg_type="https://didcomm.org/messagepickup/2.0/status",
        )
    inital_count = initial_status["message_count"]

    for _ in range(2):
        await echo.send_message(
            connection,
            {
                "@type": "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/trust_ping/1.0/ping",
                "response_resquested": True,
            },
        )

    async with echo.session(connection, ws_endpoint) as session:
        await echo.send_message_to_session(
            session,
            {
                "@type": "https://didcomm.org/messagepickup/2.0/delivery-request",
                "~transport": {"return_route": "all"},
                "limit": 2,
            },
        )

        wrapped_msgs = await echo.get_message(
            connection,
            session=session,
            msg_type="https://didcomm.org/messagepickup/2.0/delivery",
        )
    msg_ids = []

    for msg in wrapped_msgs["~attach"]:
        msg_ids.append(msg["@id"])

    async with echo.session(connection, ws_endpoint) as session:
        await echo.send_message_to_session(
            session,
            {
                "@type": "https://didcomm.org/messagepickup/2.0/messages-received",
                "message_id_list": msg_ids,
                "~transport": {"return_route": "all"},
            },
        )

        final_status = await echo.get_message(
            connection,
            session=session,
            msg_type="https://didcomm.org/messagepickup/2.0/status",
        )
    final_count = final_status["message_count"]

    assert final_count == inital_count


@pytest.mark.asyncio
async def test_messages_received_junk_id(
    echo: EchoClient, connection: ConnectionInfo, ws_endpoint: str
):
    """Testing that an incorrect ID list does not alter the queue."""

    async with echo.session(connection, ws_endpoint) as session:
        await echo.send_message_to_session(
            session,
            {
                "@type": "https://didcomm.org/messagepickup/2.0/status-request",
                "~transport": {"return_route": "all"},
            },
        )
        initial_status = await echo.get_message(
            connection,
            session=session,
            msg_type="https://didcomm.org/messagepickup/2.0/status",
        )
    inital_count = initial_status["message_count"]

    async with echo.session(connection, ws_endpoint) as session:
        await echo.send_message_to_session(
            session,
            {
                "@type": "https://didcomm.org/messagepickup/2.0/messages-received",
                "message_id_list": [
                    "A communications disruption can mean only one thing: invasion"
                ],
                "~transport": {"return_route": "all"},
            },
        )

        final_status = await echo.get_message(
            connection,
            session=session,
            msg_type="https://didcomm.org/messagepickup/2.0/status",
        )
    final_count = final_status["message_count"]
    assert inital_count == final_count

# Pickup Protocol for ACA-Py

[![PyPI](https://img.shields.io/pypi/v/acapy-plugin-pickup)](https://pypi.org/project/acapy-plugin-pickup/)
[![Container Image](https://img.shields.io/badge/image-0.1.0-blue)](https://github.com/Indicio-tech/acapy-plugin-pickup/pkgs/container/acapy-plugin-pickup/39152013?tag=0.1.0)



## Protocol Defintion

This protocol is an implementation of [RFC 0685](https://github.com/hyperledger/aries-rfcs/tree/main/features/0685-pickup-v2).
Said RFC contains the entirety of the specification, but for ease of use, much of the RFC has been added here to document this implementation. For accuracy, portions have been modified to better document the actual implementation.

## Summary

A protocol to facilitate an agent picking up messages held at a mediator.

## Tutorial

### Roles

**Mediator** - The agent that has messages waiting for pickup by the _Recipient_.

**Recipient** - The agent who is picking up messages.

### Flow

The `status-request` message is sent by the _Recipient_ to the _Mediator_ to query how many messages are pending.

The `status` message is the response to `status-request` to communicate the state of the message queue.

The `delivery-request` message is sent by the _Recipient_ to request delivery of pending messages.

The `delivery` message is a wrapper message, sent by the _Mediator_, that contains the messages requested by the _Recipient_.

The `message-received` message is sent by the _Recipient_ to confirm receipt of delivered messages, 
prompting the _Mediator_ to clear messages from the queue.

> Note: Live Mode is referenced in the RFC, but currently this plugin does not support live mode functionality. See [Live Mode](https://github.com/hyperledger/aries-rfcs/blob/main/features/0685-pickup-v2/README.md#live-mode) in the RFC for more information.

## Reference

Each message sent MUST use the `~transport` decorator as follows, which has been adopted from [RFC 0092 transport return route](https://github.com/hyperledger/aries-rfcs/blob/main/features/0092-transport-return-route/README.md) protocol. This has been omitted from the examples for brevity.

```json=
"~transport": {
    "return_route": "all"
}
```

## Message Types

### Status Request

Sent by the _Recipient_ to the _Mediator_ to request a `status` message.
#### Example:

```json=
{
    "@id": "123456781",
    "@type": "https://didcomm.org/messagepickup/2.0/status-request",
    "recipient_key": "<key for messages>"
}
```

`recipient_key` is optional. When specified, the _Mediator_ will only return status related to that recipient key. This allows the _Recipient_ to discover if any messages are in the queue that were sent to a specific key. You can find more details about `recipient_key` and how it's managed in [0211-route-coordination](https://github.com/hyperledger/aries-rfcs/blob/master/features/0211-route-coordination/README.md).

### Status

Status details about waiting messages.

#### Example:

```json=
{
    "@id": "123456781",
    "@type": "https://didcomm.org/messagepickup/2.0/status",
    "recipient_key": "<key for messages>",
    "message_count": 7,
    "longest_waited_seconds": 3600,
    "newest_received_time": "2019-05-01 12:00:00Z",
    "oldest_received_time": "2019-05-01 12:00:01Z",
    "total_bytes": 8096,
    "live_delivery": false
}
```

`message_count` is the only REQUIRED attribute. The others MAY be present if offered by the _Mediator_. This plugin currently does not offer any attribute other than the `message_count`, but a descriptor of the other attributes is included here.

`longest_waited_seconds` is in seconds, and is the longest delay of any message in the queue.

`total_bytes` represents the total size of all messages.

If a `recipient_key` was specified in the `status-request` message, the matching value is specified in the `recipient_key` attribute of the status message.

`live_delivery` state is also indicated in the status message. 

> Note: due to the potential for confusing what the actual state of the message queue
> is, a status message MUST NOT be put on the pending message queue and MUST only
> be sent when the _Recipient_ is actively connected (HTTP request awaiting
> response, WebSocket, etc.).

### Delivery Request

A request from the _Recipient_ to the _Mediator_ to have pending messages delivered. 

#### Examples:

```json=
{
    "@id": "123456781",
    "@type": "https://didcomm.org/messagepickup/2.0/delivery-request",
    "limit": 10,
    "recipient_key": "<key for messages>"
}
```

```json=
{
    "@type": "https://didcomm.org/messagepickup/2.0/delivery-request",
    "limit": 1
}
```


`limit` is a REQUIRED attribute, and after receipt of this message, the _Mediator_ will deliver up to the `limit` indicated. 

`recipient_key` is optional. When specified, the _Mediator_ will only return messages sent to that recipient key.

If no messages are available to be sent, a `status` message is sent immediately, as a response to the Delivery Request.

Delivered messages will not be deleted from the queue until delivery is acknowledged by a `messages-received` message.

### Message Delivery

Messages delivered from the queue are delivered in a batch `delivery` message as attachments. The ID of each attachment is used to confirm receipt. The ID is an opaque value, and the Recipient should not infer anything from the value.

The `recipient_key` attribute is only included when responding to a `delivery-request` message that indicates a `recipient_key`.

```json=
{
    "@id": "123456781",
    "~thread": {
        "thid": "<message id of delivery-request message>"
      },
    "@type": "https://didcomm.org/messagepickup/2.0/delivery",
    "recipient_key": "<key for messages>",
    "~attach": [{
    	"@id": "<messageid>",
    	"data": {
    		"base64": ""
    	}
    }]
}
```

This method of delivery does incur an encoding cost, but is much simpler to implement and a more robust interaction.

### Messages Received
After receiving messages, the _Recipient_ needs to send an ack message indiciating 
which messages are safe to clear from the queue.

#### Example:

```json=
{
    "@type": "https://didcomm.org/messagepickup/2.0/messages-received",
    "message_id_list": ["123","456"]
}
```

`message_id_list` is a list of ids of each message received. The id of each message is present in the attachment descriptor of each attached message of a `delivery` message.

Upon receipt of this message, the _Mediator_ knows which messages have been received, and can remove them from the collection of queued messages with confidence. The mediator SHOULD send an updated `status` message reflecting the changes to the queue.

### Multiple Recipients

If a message arrives at a _Mediator_ addressed to multiple _Recipients_, the message MUST be queued for each _Recipient_ independently. If one of the addressed _Recipients_ retrieves a message and indicates it has been received, that message MUST still be held and then removed by the other addressed _Recipients_.

### Integration tests

```
docker-compose -f int/docker-compose.yml build
docker-compose -f int/docker-compose.yml run tests
docker-compose -f int/docker-compose.yml down -v
```
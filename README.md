# Pickup Protocol for ACA-Py

## Protocol Defintion

This protocol will hopefully be finalized and submitted as an Aries RFC.
However, in advance of that submission, and due to this protocol differing from
the currently defined pickup protocol, the following is the full definition of
this pickup protocol as implemented in this plugin:

# 0212: Pickup Protocol 2.0

- Authors: [Sam Curren](telegramsam@gmail.com), [Daniel Bluhm](dbluhm@pm.me), James Ebert
- Status: [PROPOSED](/README.md#proposed)
- Since: 2019-09-03
- Status Note: Revised
- Start Date: 2020-12-22
- Tags: [feature](/tags.md#feature), [protocol](/tags.md#protocol)

## Summary

A protocol to retrieve messages destined for a recipient from a message holder.

## Motivation

Messages can be picked up simply by sending a message to the _Message Holder_
with a `return_route` decorator specified. This mechanism is implicit, and lacks
some desired behavior made possible by more explicit messages.

This protocol is the explicit companion to the implicit method of picking up messages.

## Tutorial

### Roles

**Message Holder** - The agent that has messages waiting for pickup by the _Recipient_.

**Recipient** - The agent who is picking up messages.

### Flow

The `status-request` message is used to query how many messages are pending.

The `status` message is used to communicate the state of the message queue.

The `delivery-request` message is used to request delivery of pending messages.

The `message-received` message is used to confirm receipt of delivered messages, 
prompting the _Message Holder_ to clear messages from the queue.

The `live-delivery-change` message is used to set the state of `live_delivery`. 

When a _Recipient_ is actively connected to a message holder (via WebSocket, for
example), new messages are sent directly to the _Recipient_ and will not enter the
queue.
- This behavior will be able to be modified by the `live_delivery` attribute, once it is implemented.

## Reference

Each message sent MUST use the `~transport` decorator as follows. This has been omitted from the examples for brevity.
```json=
"~transport": {
    "return_route": "all"
}
```

### StatusRequest

Sent by the _Recipient_ to the _Message Holder_ to request a `status` message. Example:

```json=
{
    "@id": "123456781",
    "@type": "https://didcomm.org/messagepickup/2.0/status-request",
    "recipient_key": "<key for messages>",
}
```

`recipient_key` is optional. When specified, only the status related to that
`recipient_key` is returned. When omitted, the status for all messages queued for
the _Recipient_ is returned.

### Status

Status details about pending messages. Example:

```json=
{
    "@id": "123456781",
    "@type": "https://didcomm.org/messagepickup/2.0/status",
    "recipient_key": "<key for messages>",
    "message_count": 7,
    "duration_waited": 3600,
    "newest_time": "2019-05-01 12:00:00Z",
    "oldest_time": "2019-05-01 12:00:01Z",
    "total_size": 8096
}
```

`message_count` is the only required attribute. The others may be present if
offered by the _Message Holder_.

`duration_waited` is in seconds, and is the longest  delay of any message in the
queue.

`total_size` is in bytes.

If a `recipient_key` was specified in the `status-request` message, the matching
value MUST be specified in the `recipient_key` attribute of the status
message.

Due to the potential for confusing what the actual state of the message queue
is, a status message MUST NOT be put on the pending message queue and MUST only
be sent when the _Recipient_ is actively connected (HTTP request awaiting
response, WebSocket, etc.).

### Delivery Request

A request fromt the _Recipient_ to the _Message Holder_ have waiting messages delivered. Example:

```json=
{
    "@id": "123456781",
    "@type": "https://didcomm.org/messagepickup/2.0/delivery-request",
    "limit": 10,
    "recipient_key": "<key for messages>"
}
```

After receipt of this message, the _Message Holder_ MUST deliver up to the limit
indicated, or the total number of messages in the queue for the _Recipient_.

`recipient_key` is optional. When specified, only the messages related to that
`recipient_key` are returned. When omitted, all messages queued for the _Recipient_
are returned.

If no messages are available to be sent, a `status` message MUST be sent immediately. 

### Messages Received
An acknowledgement sent by the _Recipient_ indicating which messages were received.
```json=
{
    "@type": "https://didcomm.org/messagepickup/2.0/messages-received",
    "message_tag_list": ["123","456"]
}
```
`message_tag_list` identifies which messages were received. The tag of each message 
is present in the encrypted form of the message as an artifact of encryption, and is 
indexed by the _Message Holderr_. Tags are unique in the scope of a _Recipient_, and are sufficient 
to uniquely identify messages.

Upon receipt of this message, the _Message Holder_ knows that the messages have been received and can 
confidently remove them from the list of queued messages. The _Message Holder_ SHOULD send an updated 
`status` message reflecting changes to the queue.

The _Message Holder_ MUST NOT delete messages from the queue until it receives a `messages-received` ackowledgement, 
indicating which messages are safe to delete. 

### Multiple Recipients
If a message arrives at a mediator addressed to multiple recipients, the message should be queued 
for each recipient independently. If one of the addressed recipients retrieves a message and indicates 
it has been received, that message MUST still be held and then removed by the other addressed recipients.

## Live Mode
Not yet implemented. See [here](https://github.com/TelegramSam/aries-rfc/tree/pickup_v2/features/0685-pickup-v2#live-mode) 
for expected behavior.

## Prior art

Version 1.0 of this protocol served as the main inspiration for this version.

## Unresolved questions

- Is this the appropriate place to talk about when to queue messages in a mediator?
- Is 'Pickup' the wrong name?

## Implementations

The following lists the implementations (if any) of this RFC. Please do a pull
request to add your implementation. If the implementation is open source,
include a link to the repo or to the implementation within the repo. Please be
consistent in the "Name" field so that a mechanical processing of the RFCs can
generate a list of all RFCs supported by an Aries implementation.

Name / Link | Implementation Notes
--- | ---
 |  |

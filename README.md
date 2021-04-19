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

**Message Holder** - The agent that has messages waiting for pickup by the _recipient_.

**Recipient** - The agent who is picking up messages.

### Flow

The `status-request` message can be used to query how many messages are pending.

The `status` message is used to communicate the state of the message queue.

Messages are retrieved by sending a `delivery-request` message.

When a recipient is actively connected to a message holder (via WebSocket, for
example), new messages are sent directly to the recipient and will not enter the
queue.

## Reference

### StatusRequest

Sent by the _recipient_ to the _message holder_ to request a `status` message.

```json=
{
    "@id": "123456781",
    "@type": "https://didcomm.org/messagepickup/2.0/status-request",
    "recipient_key": "<key for messages>",
    "~transport": {
        "return_route": "all"
    }
}
```

`recipient_key` is optional. When specified, only the status related to that
recipient key is returned. When omitted, the status for all messages queued for
the recipient is returned.

### Status

Status details about pending messages.

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
offered by the _message_holder_.

`duration waited` is in seconds, and is the longest  delay of any message in the
queue.

`total_size` is in bytes.

If a `recipient_key` was specified in the status-request message, the matching
value should be specified in the `recipient_key` attribute of the status
message.

Due to the potential for confusing what the actual state of the message queue
is, a status message MUST not be put on the pending message queue and MUST only
be sent when the recipient is actively connected (HTTP request awaiting
response, WebSocket, etc.).

### Delivery Request

A request to have waiting messages delivered. 

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
    "limit": 1,
    "~transport": {
        "return_route": "all"
    }
}
```

After receipt of this message, the mediator should deliver up to the limit
indicated. After it delivers the messages indicated, it should send an updated
`status` message.

`recipient_key` is optional. When specified, only the messages related to that
recipient key are returned. When omitted, all messages queued for the recipient
are returned.

After messages are sent to fulfill this request, an updated status message MUST
be sent IF there is an active connection to send the message. This is also true
if a delivery request had no messages to deliver.

This message should only be sent when `"~transport": {"return_route": "all"}`
is indicated on the message.

## Prior art

Version 1.0 of this protocol served as the main inspiration for this version

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

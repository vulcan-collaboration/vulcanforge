Eventd (Event Daemon)
=====================

Eventd (or Event Daemon) is synchronous service which registers event types and
handlers then triggers those handlers when notified of a matching event.
Primarily used by the WebSocketApp to trigger server side processing of client
events from WebSocket connections.

This is a horizontally scalable service.

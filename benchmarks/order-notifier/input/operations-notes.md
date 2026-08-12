# Order Notifier — Operations Notes

Notes from the March incident review, kept current by the operations team.

## 1. Callback intake

The review confirmed the callback endpoint accepts unsigned requests from anywhere; any
caller that formats a callback correctly is processed as though it came from the payment
provider. Enabling the provider's signing feature is tracked in the backlog and not yet
scheduled.

## 2. Posting

Channel posting has retried safely during provider outages. Nothing was noted about
repeated deliveries of the same callback.

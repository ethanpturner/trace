# Order Notifier — Integration Guide

The Order Notifier receives order-status callbacks from the payment provider and posts
updates to the operations channel.

## 1. Callback Receiver

The Callback Receiver is the endpoint registered with the payment provider. It processes
any well-formed callback it receives: callbacks are not signed, and the provider's optional
callback-signing feature is not enabled for this integration.

## 2. Channel Poster

The Channel Poster formats the order status and posts it to the operations channel over the
channel platform's HTTPS API.

# Kiosk Sync Service — Note

The sync service receives customer order records from the field kiosks and stores them for
the fulfillment system to read. Order records carry the customer's name, delivery address,
and order contents.

## Deployment

The service runs on a virtual machine in the operations subnet. The kiosks call it over the
store network. The fulfillment system polls it hourly.

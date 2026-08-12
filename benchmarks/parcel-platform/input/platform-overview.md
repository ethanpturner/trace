# Parcelworks — Platform Overview

Parcelworks is a parcel-logistics platform: customers book and track shipments, drivers
collect and deliver them, and carrier partners handle line-haul between depots. This
document describes the platform as deployed across its four zones: edge, core, data, and
operations.

## 1. Edge zone

### Customer Portal

The public web application where customers book shipments, print labels, and track parcels.
Served over HTTPS behind the API Gateway.

### Mobile Gateway

The endpoint for the driver mobile application: route assignments down, scan events and
proof-of-delivery photos up. Served over HTTPS behind the API Gateway.

### API Gateway

The single public entry point. It terminates TLS, authenticates every request against the
Identity Service, applies per-client rate limits, and routes to the core services.

## 2. Core zone

### Identity Service

Authenticates customers, drivers, and staff. All interactive sign-in is delegated to the
company's SSO provider over OpenID Connect; the service issues short-lived internal tokens
that the core services verify.

### Order Service

Owns shipment bookings: creation, pricing acceptance, and lifecycle state. Writes to the
Orders Database and publishes order events to the Message Bus.

### Routing Service

Plans collection and delivery routes from open orders and driver availability, and assigns
routes through the Dispatch Service.

### Dispatch Service

Pushes route assignments to drivers through the Mobile Gateway and records acceptance.

### Tracking Service

Consumes scan events from the Message Bus and maintains per-parcel tracking state in the
Tracking Store. Serves tracking queries from the portal.

### Notification Service

Sends booking confirmations, delivery windows, and delivery notices by email and SMS
through an external messaging provider. For debugging, the notification templates log the
full rendered message body — including the recipient's name, delivery address, and delivery
window — to the shared application log.

### Label Service

Renders shipping labels as PDFs and stores them in the Object Storage bucket, keyed by
shipment.

### Billing Service

Prices shipments, raises invoices, and records payments. Card payments are processed
entirely by an external payment provider; the platform stores only the provider's payment
reference.

### Admin Console

The staff interface for refunds, address corrections, and account management. Staff reach
the console with the same SSO accounts and the same sign-in path customers use; an
`is_admin` flag on the user record enables the console's functions. The console can read
and edit any customer account, order, and address.

## 3. Data zone

### Message Bus

The event backbone connecting the core services. Services authenticate to the bus with
their per-service credentials issued at deploy time.

### Orders Database

The relational store for bookings, customer accounts, and addresses. Reachable only from
the core zone.

### Tracking Store

The store for per-parcel scan history and tracking state. Reachable only from the core
zone.

### Object Storage

The managed object store holding label PDFs and proof-of-delivery photos.

### Data Warehouse

Receives a nightly copy of the Orders Database — including customer names and full delivery
addresses — for analytics. How long the copies are kept has not been written down anywhere
the team could point to.

## 4. Operations zone

### Carrier Link

The connector to carrier partners' APIs for line-haul handoff: manifests out, status
updates in, over the carriers' HTTPS APIs.

### Deploy Runner

Runs the deployment pipeline that builds and releases the core services.

## 5. Actors

- **Customer** — books and tracks shipments through the portal.
- **Driver** — collects and delivers through the mobile application.
- **Staff operator** — uses the Admin Console.
- **Carrier partner** — receives manifests and returns status through Carrier Link.
- **Messaging provider** — the external email and SMS service.

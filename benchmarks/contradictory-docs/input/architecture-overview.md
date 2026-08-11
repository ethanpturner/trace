# Export Service — Architecture Overview

The export service produces data exports for customers on request. A customer requests an
export, the service assembles it from the customer's records, and the customer downloads
the result.

## 1. Components

### Export API

A public HTTPS service that accepts export requests and returns a download link when the
export is ready.

### Export Worker

An internal worker that assembles the requested export from customer records and writes the
result to object storage.

## 2. Data handling

Export requests name a customer and a date range. The assembled export contains the
customer's records for that range and is written to a managed object store. The export
file is temporary working data: it is deleted immediately once the customer has downloaded
it.

## 3. Actors

- **Customer** — the authenticated requester and downloader of an export.
- **Export worker** — the internal assembler of exports.

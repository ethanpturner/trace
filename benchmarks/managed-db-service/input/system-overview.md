# Metrics Store — System Overview

The metrics store is an internal service that records product usage metrics and serves
them to an internal dashboard. It is reachable only from inside the application subnet.

## 1. Components

### Metrics API

An internal HTTP service that accepts metric writes from product services and answers
metric queries from the dashboard. It is not reachable from the internet.

### Managed Metrics Database

A managed relational database provided by the cloud platform. The metrics API reads and
writes it. The platform encrypts the database at rest by default, and the connection from
the metrics API to the database uses the platform's transport encryption terminated at the
managed endpoint. Key management for the at-rest encryption is handled by the platform's
key management service.

## 2. Data

Metrics records associate a product account with usage counters. They contain account
identifiers and usage numbers, which are treated as confidential business data.

## 3. Actors

- **Product service** — an internal service writing metrics.
- **Dashboard** — an internal reader of metrics.

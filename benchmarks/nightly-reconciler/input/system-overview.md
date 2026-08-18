# Nightly Reconciler — System Overview

The nightly reconciler is an internal batch service that compares the day's billing records
against the settlement reports published by the payment processor and files a discrepancy
summary for the finance team. It runs once per night on the platform's standard workload
deployment.

## 1. Components

### Reconciler Job

A scheduled batch workload. Each night it pulls the day's settlement report from the payment
processor's reporting API, reads the day's billing records from the billing database, compares
the two, and writes a discrepancy summary back to the billing database. It exposes no inbound
interface.

### Billing Database

A managed relational database provided by the cloud platform. It holds billing records and the
reconciler's discrepancy summaries, and it is reachable only from the reconciler job inside
the application subnet.

### Payment Processor

The external payment platform the product uses to capture payments. It publishes a daily
settlement report over its reporting API, served over HTTPS.

## 2. Credentials

The reconciler authenticates to the payment processor's reporting API with a service
credential issued by the processor for this integration. The credential is provisioned through
the standard workload deployment.

## 3. Data

Billing records contain per-customer charge entries. Settlement reports contain the
processor's record of captured payments for the day. Discrepancy summaries name the affected
record, the two amounts, and the day they diverged.

## 4. Actors

- **Finance analyst** — an internal user who reviews each morning's discrepancy summary.
- **Payment processor** — the external platform that captures payments and publishes the
  settlement reports the reconciler consumes.

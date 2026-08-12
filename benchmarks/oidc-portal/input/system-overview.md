# Support Portal — System Overview

The support portal is an internal web application that lets employees view and comment on
customer support tickets. It is served over HTTPS and reachable only from the corporate
network and the company VPN.

## 1. Components

### Portal Web Application

A server-rendered web application. It presents tickets, accepts comments, and calls the
ticket service for data. It holds no local user accounts.

### Ticket Service

An internal HTTP service that stores and retrieves tickets. It is reachable only from the
portal web application inside the application subnet.

## 2. Authentication

All access to the portal is authenticated through the company's enterprise identity
provider using OpenID Connect. A user reaching the portal is redirected to the identity
provider, authenticates there, and returns with an ID token the portal validates. The
portal maintains no password store of its own and issues no credentials; identity is the
identity provider's responsibility, and multi-factor enrolment and factor policy are set
at the identity provider organization level.

## 3. Data

Tickets contain customer support correspondence. The ticket service persists them in a
managed relational database provided by the cloud platform.

## 4. Actors

- **Employee** — an authenticated internal user viewing and commenting on tickets.
- **Identity provider** — the enterprise OpenID Connect provider that authenticates
  employees and enforces the factor policy.

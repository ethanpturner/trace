# Deploy Notifier — System Overview

The deploy notifier is a small service that receives deployment events from an external
continuous-integration platform and posts them to an internal chat channel. It exists so
engineers see deploys without watching the CI dashboard.

## 1. Components

### Event Receiver

A public HTTPS endpoint that the external CI platform calls with a deployment event. The
receiver parses the event and hands it to the notifier.

### Chat Notifier

Formats the deployment event and posts it to the internal chat channel over the chat
platform's API.

## 2. Event handling

The CI platform delivers each deployment event as a JSON body to the receiver's public
URL. The receiver parses the JSON and acts on the event: it reads the repository name, the
environment, and the commit, and posts a message naming them. The CI platform supports
signing deliveries with a shared secret so a receiver can verify that an event came from
the platform; the receiver accepts and processes any well-formed delivery and does not
check a signature.

## 3. Data

Deployment events name repositories, environments, and commit identifiers. No customer
data passes through the notifier.

## 4. Actors

- **CI platform** — the external continuous-integration service that sends deployment
  events.
- **Engineer** — the internal reader of the chat channel.

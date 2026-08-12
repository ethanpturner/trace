# Wallet and Exchange Platform — System Overview

This document describes a cryptocurrency wallet and exchange integration: a desktop
wallet, an exchange with web and API access, and the blockchain integration behind them.
The user's operating system, hardware, and third-party dependencies not shown here are out
of scope. The platform is business-critical and externally exposed, and handles business
and credential data.

## 1. Trust zones

- **User device** — the wallet GUI and daemon, the browser, the mobile app, and any
  user-run trading bot.
- **Internet** — the public network, the ElectrumX servers, and the exchange website
  front-end.
- **Exchange internal** — the exchange backend, the exchange API, the blockchain
  integration module, and the exchange databases.

## 2. Components

### Electrum Wallet GUI (user device)

Desktop wallet graphical user interface.

### Electrum Wallet Daemon (user device)

Local wallet backend process exposing HTTP JSON-RPC on localhost. The GUI talks to the
daemon; the daemon connects out to ElectrumX servers for blockchain data.

### ElectrumX Server (internet)

Third-party SPV server that wallets connect to for blockchain data — balances, headers,
and transaction broadcast. Operated by third parties, not by the exchange.

### Web Browser and Mobile App (user device)

The browser reaches the exchange website and the local wallet UI. The mobile app is the
mobile variant for wallet and exchange interaction.

### Exchange Website (internet)

The front-end served to users. It interacts with the exchange backend over HTTPS.

### Exchange Backend (exchange internal)

Handles business logic, configuration, and user data. It reads and writes the MySQL and
MongoDB stores and calls the blockchain integration module.

### Exchange API (exchange internal)

A Node.js API server providing programmatic access to exchange functions such as trading
and account data. User-run trading bots connect to it over a secure WebSocket using API
keys.

### Blockchain Integration Module (exchange internal)

Interfaces with the blockchain network to read and write blockchain state on behalf of the
backend.

## 3. Data stores

- **Wallet file** (user device) — the local wallet at rest, holding the wallet data and
  keys. It should be encrypted at rest; encryption is a wallet option.
- **MySQL** (exchange internal) — user accounts and configuration.
- **MongoDB** (exchange internal) — trading data, logs, and operational metadata used by
  the exchange API.

## 4. Data flows

The user operates the wallet GUI, which drives the local daemon; the daemon connects to
ElectrumX servers for blockchain state. The user's browser reaches the exchange website,
which talks to the backend; the backend reads and writes both databases and calls the
blockchain integration module. A user-run trading bot holds exchange API keys and trades
against the exchange API over a secure WebSocket.

TLS is expected to terminate at the load balancer, with all front-end to backend
communication over HTTPS. This has not been re-verified for the current deployment.

## 5. Actors

- **End user** — a legitimate user interacting via the wallet GUI, the browser, or the
  mobile app; may also run a trading bot with API keys they generate.

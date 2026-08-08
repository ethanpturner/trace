# ForgeFlow Architecture Overview

**Document owner:** Platform Engineering

**Document status:** Current

**Last updated:** 2026-07-22

## 1. Purpose

This document provides a high-level overview of the ForgeFlow application architecture.

It describes:

- Major components
- External dependencies
- Primary data flows
- Deployment boundaries
- Data storage
- Authentication
- Background processing

Detailed operational procedures, security controls, and integration-specific behavior are maintained in separate documents.

## 2. System Overview

ForgeFlow is a multi-customer SaaS platform that integrates with GitHub and an external AI provider.

The platform receives pull-request events from GitHub, retrieves selected repository content, performs AI-assisted analysis, stores the result, and displays the output to authenticated users.

When automatic comments are enabled, ForgeFlow may also publish a summary to the associated GitHub pull request.

The system is deployed in a public cloud environment using managed infrastructure services where practical.

## 3. High-Level Architecture

flowchart LR

USER[Customer User]

CUSTOMERADMIN[Customer Administrator]

FFADMIN[ForgeFlow Administrator]

EDGE[Managed CDN and Web Application Firewall]

WEB[React Web Application]

API[ForgeFlow API]

WEBHOOK[Webhook Receiver]

QUEUE[(Managed Redis Queue)]

WORKER[Analysis Worker]

COMMENT[GitHub Comment Service]

ADMIN[Administrative Interface]

DB[(Managed PostgreSQL)]

STORAGE[(Managed Object Storage)]

SECRETS[Managed Secrets Service]

LOGGING[Central Logging Platform]

GITHUB[GitHub]

AI[External AI Provider]

EMAIL[Email Provider]

CORPIDP[Corporate Identity Provider]

USER --> EDGE

CUSTOMERADMIN --> EDGE

EDGE --> WEB

WEB --> API

GITHUB --> WEBHOOK

WEBHOOK --> QUEUE

QUEUE --> WORKER

WORKER --> GITHUB

WORKER --> AI

WORKER --> DB

WORKER --> STORAGE

WORKER --> COMMENT

COMMENT --> GITHUB

API --> DB

API --> STORAGE

API --> GITHUB

API --> EMAIL

FFADMIN --> CORPIDP

CORPIDP --> ADMIN

ADMIN --> API

API --> SECRETS

WEBHOOK --> SECRETS

WORKER --> SECRETS

COMMENT --> SECRETS

API --> LOGGING

WEBHOOK --> LOGGING

WORKER --> LOGGING

COMMENT --> LOGGING

ADMIN --> LOGGING

## 4. Public Edge

ForgeFlow uses a managed content-delivery network and web application firewall at the public edge.

The edge layer:

- Terminates public TLS connections
- Serves static frontend content
- Routes application traffic
- Applies managed filtering rules
- Provides basic denial-of-service protection
- Restricts access to known application origins

The edge service is managed separately from the ForgeFlow application runtime.

## 5. React Web Application

The customer-facing web application is implemented as a React single-page application.

Responsibilities include:

- Starting the GitHub authentication flow
- Displaying connected organizations and repositories
- Displaying pull-request analysis status
- Displaying completed analysis results
- Managing customer organization settings
- Configuring automatic pull-request comments
- Initiating permitted job retries

The browser application communicates with the ForgeFlow API over HTTPS.

The frontend does not store long-lived GitHub or provider credentials.

## 6. ForgeFlow API

The ForgeFlow API provides customer-facing application functionality.

Responsibilities include:

- Managing authenticated user sessions
- Managing organization membership
- Managing repository configuration
- Retrieving analysis results
- Creating signed links for selected stored artifacts
- Managing automatic-comment settings
- Supporting organization-level data deletion requests
- Initiating selected GitHub API operations
- Supporting permitted administrative operations

The API is implemented in Python and runs as a separately deployable service.

API requests that operate on customer resources include an organization context.

## 7. GitHub Authentication

Customer users authenticate through GitHub.

ForgeFlow does not maintain a local password database.

After the GitHub authentication flow completes, ForgeFlow associates the GitHub identity with a ForgeFlow user and one or more customer organizations.

Organization membership and role information are stored in ForgeFlow.

The application uses secure browser sessions for subsequent customer requests.

## 8. Webhook Receiver

The webhook receiver is an internet-facing service dedicated to processing GitHub webhook events.

Responsibilities include:

- Receiving GitHub event payloads
- Validating incoming requests
- Parsing event metadata
- Identifying the related installation and repository
- Determining whether the event is relevant
- Creating an analysis job
- Sending the job to the managed queue

The webhook receiver is independently scalable from the main API because webhook traffic may arrive in short bursts.

Invalid or unsupported events are rejected or ignored.

Detailed GitHub validation behavior is described in the GitHub integration documentation.

## 9. Managed Redis Queue

ForgeFlow uses a managed Redis service for:

- Pending analysis jobs
- Job retry state
- Temporary coordination data
- Selected rate-limiting state
- Short-lived cached metadata

The Redis service is accessible only from approved application workloads.

Each analysis job includes:

- Organization identifier
- GitHub installation identifier
- Repository identifier
- Pull-request identifier
- Event identifier
- Attempt number
- Job configuration

Redis is not the authoritative store for completed analysis results.

## 10. Analysis Worker

The analysis worker performs background pull-request processing.

Responsibilities include:

1. Retrieve a queued analysis job.
2. Resolve the customer organization and GitHub installation.
3. Obtain a short-lived GitHub installation token.
4. Retrieve the pull-request diff and selected repository content.
5. Construct an analysis request.
6. Send selected content to the external AI provider.
7. Validate the structure of the provider response.
8. Store the structured result and related artifacts.
9. Trigger a pull-request comment when configured.
10. Record job status and operational metadata.

Workers can scale horizontally based on queue depth.

The worker is the primary component that handles customer source content.

## 11. GitHub Comment Service

The GitHub comment service is responsible for publishing ForgeFlow summaries to pull requests.

It receives:

- Organization identifier
- Repository identifier
- Pull-request identifier
- Structured analysis result
- Comment configuration

The service:

- Formats the analysis summary
- Applies output-length restrictions
- Removes unsupported formatting
- Adds a link to the full ForgeFlow result
- Uses a short-lived GitHub installation token
- Posts the comment through the GitHub API

The service does not independently perform AI analysis.

Comments are published when the customer has enabled automatic commenting and the analysis job completes successfully.

## 12. Managed PostgreSQL

ForgeFlow uses a managed PostgreSQL service as its primary structured-data store.

The database contains:

- Users
- Organizations
- Organization memberships
- User roles
- GitHub installation metadata
- Repository configuration
- Pull-request metadata
- Analysis job metadata
- Structured analysis results
- Comment-publication status
- Administrative audit events
- Data-deletion status

Customer-associated records include an organization identifier.

Application services are responsible for applying organization-aware access rules when querying customer data.

Database backups and platform maintenance are managed through the cloud database service.

## 13. Managed Object Storage

ForgeFlow uses managed object storage for larger or temporary artifacts.

Stored objects may include:

- Selected repository files
- Pull-request diffs
- Model input artifacts
- Model output artifacts
- Exported reports
- Diagnostic artifacts associated with failed jobs

Objects are stored under paths that include the ForgeFlow organization identifier and job identifier.

Example:

organizations/{organization_id}/jobs/{job_id}/artifacts/{artifact_name}

The ForgeFlow API may generate time-limited access links for permitted customer downloads.

Source-related artifacts are intended to support temporary processing and operational troubleshooting.

Detailed retention behavior is defined in operational documentation.

## 14. Managed Secrets Service

ForgeFlow uses a managed secrets service for sensitive application credentials.

Stored secrets include:

- GitHub App private key
- GitHub OAuth client secret
- External AI-provider API key
- Email-provider API key
- Selected database connection credentials

Application workloads retrieve secrets through workload identity where supported.

Secrets are not intended to be stored in source repositories or general configuration files.

Different application services may receive access to different secrets based on their responsibilities.

## 15. Administrative Interface

ForgeFlow provides an internal administrative interface for operational support.

Authorized ForgeFlow administrators may use it to:

- Locate organizations and installations
- View analysis job status
- Review error metadata
- Retry failed jobs
- Disable an integration
- Review selected operational events
- Support data-deletion requests

The administrative interface is not exposed through the normal customer login flow.

Administrators authenticate through the corporate identity provider before accessing the interface.

Detailed administrative permissions are maintained separately.

## 16. Central Logging Platform

ForgeFlow sends application and security-relevant events to a shared logging platform.

Logged event types include:

- Authentication events
- API request metadata
- Organization-membership changes
- GitHub installation changes
- Webhook-processing outcomes
- Analysis-job status
- External-provider request metadata
- Comment-publication status
- Administrative actions
- Application errors

Customer source code should not be included in normal application logs.

Error handling should avoid logging full provider prompts or GitHub access tokens.

## 17. GitHub Integration

GitHub provides:

- Customer authentication
- GitHub App installation
- Repository permissions
- Pull-request metadata
- Source-content retrieval
- Webhook events
- Pull-request comments

ForgeFlow uses a GitHub App rather than asking customers to provide personal access tokens.

The GitHub App requests repository permissions required for the configured ForgeFlow functionality.

ForgeFlow generates short-lived installation tokens when repository access is needed.

## 18. External AI Provider

ForgeFlow sends selected pull-request and repository content to an external AI provider.

The AI provider does not receive:

- GitHub App private keys
- GitHub installation tokens
- ForgeFlow session cookies
- Database credentials
- Direct access to customer repositories

The worker constructs a request containing:

- Analysis instructions
- Pull-request metadata
- Pull-request changes
- Selected repository context
- Output-format requirements

The provider returns a structured analysis response.

ForgeFlow validates the response structure before storing or publishing it.

Detailed prompt construction and provider behavior are described in the AI analysis documentation.

## 19. Email Provider

ForgeFlow uses a third-party email service for selected notifications.

The email provider may receive:

- User email address
- Organization display name
- Notification category
- Minimal notification content
- Link to ForgeFlow

The provider does not receive customer repository source code.

## 20. Primary Data Flows

## 20.1 Customer Login

Customer Browser

→ GitHub Authentication

→ ForgeFlow API

→ ForgeFlow Session

Primary data:

- GitHub user identity
- Authorization response
- ForgeFlow user record
- Organization membership
- Session cookie

## 20.2 Pull-Request Event Processing

GitHub

→ Webhook Receiver

→ Redis Queue

→ Analysis Worker

Primary data:

- Event type
- Delivery information
- Installation identifier
- Repository identifier
- Pull-request identifier
- Sender metadata

## 20.3 Repository Content Retrieval

Analysis Worker

→ GitHub API

→ Pull-Request Diff and Selected Files

Primary data:

- Short-lived installation token
- Pull-request changes
- Selected source files
- Repository metadata

## 20.4 AI Analysis

Analysis Worker

→ External AI Provider

→ Structured Analysis Response

Primary data:

- Pull-request content
- Selected repository context
- Analysis instructions
- Structured output

## 20.5 Result Storage

Analysis Worker

→ PostgreSQL

→ Object Storage

Primary data:

- Job metadata
- Structured result
- Model metadata
- Temporary source artifacts
- Provider input and output artifacts

## 20.6 Customer Result Access

Customer Browser

→ ForgeFlow API

→ PostgreSQL or Object Storage

Primary data:

- Analysis results
- Source references
- Job status
- Customer settings

## 20.7 Pull-Request Comment Publication

Analysis Worker

→ GitHub Comment Service

→ GitHub API

Primary data:

- Structured summary
- Pull-request identifier
- Installation context
- Result link

## 20.8 Administrative Support

ForgeFlow Administrator

→ Corporate Identity Provider

→ Administrative Interface

→ ForgeFlow API

Primary data:

- Organization metadata
- Integration status
- Job metadata
- Error details
- Administrative actions

## 21. Trust Boundaries

### Public internet boundary

Separates public users and external providers from ForgeFlow’s application services.

Crossed by:

- Browser traffic
- GitHub webhook events

### Customer authentication boundary

Separates unauthenticated users from authenticated ForgeFlow sessions.

### Organization boundary

Separates one customer organization’s data from another’s.

This boundary applies across:

- API authorization
- Database queries
- Object paths
- Background jobs
- Analysis results

### GitHub boundary

Separates ForgeFlow from GitHub-controlled identity, repository, and webhook systems.

### AI-provider boundary

Separates ForgeFlow-controlled systems from the external AI provider.

Customer source content may cross this boundary.

### Administrative privilege boundary

Separates customer functionality from internal operational administration.

### Secret-access boundary

Separates application workloads from stored credential material.

### Repository-content instruction boundary

Separates trusted ForgeFlow analysis instructions from untrusted repository and pull-request content.

## 22. Deployment Model

ForgeFlow application services run in a public cloud environment.

The deployment contains separate workloads for:

- Customer API
- Webhook receiver
- Analysis worker
- GitHub comment service
- Administrative interface

Managed services are used for:

- Public edge protection
- PostgreSQL
- Redis
- Object storage
- Secrets
- Logging

The exact compute runtime is not described in this document because it may change without altering the primary application architecture.

## 23. Availability and Scaling

ForgeFlow scales public and background-processing components independently.

Key scaling characteristics include:

- CDN handles static content and edge traffic.
- API replicas scale with customer request volume.
- Webhook receiver replicas scale with event volume.
- Worker replicas scale with queue depth.
- Redis buffers temporary job spikes.
- External AI-provider capacity may limit total processing throughput.

Analysis processing is asynchronous.

A temporary AI-provider outage should not prevent customers from viewing previously completed results.

## 24. Failure Handling

ForgeFlow records job state so analysis can be retried after recoverable failure.

Possible failure conditions include:

- GitHub API timeout
- AI-provider timeout
- Queue-processing error
- Invalid provider output
- Object-storage error
- Comment-publication error

Some failures may be retried automatically.

Authorized users may also retry selected jobs through the product or administrative interface.

Detailed retry and artifact-handling behavior is defined in the operations guide.

## 25. Architecture Assumptions

This overview assumes:

- GitHub remains the initial repository and authentication provider.
- Customer traffic uses HTTPS.
- Application services can securely retrieve required secrets.
- Redis is not publicly accessible.
- The managed database and storage services provide standard platform protections.
- Organization identifiers are propagated throughout customer-data workflows.
- External AI-provider availability is not guaranteed.
- AI-generated output requires validation before use.
- Repository content may be untrusted.

## 26. Known Documentation Gaps

The following details are maintained in other documents or require further clarification:

- Exact GitHub App permissions
- Detailed webhook-validation behavior
- Webhook replay handling
- Object-storage authorization enforcement
- Source-artifact retention
- AI-provider retention and regional processing
- Administrative access to source artifacts
- Detailed tenant-isolation tests
- AI-output approval requirements
- Exact retry limits
- Rich-content rendering behavior

## 27. Related Documents

- product-overview.md
- security-overview.md
- operations-guide.md
- github-integration.md
- ai-analysis.md

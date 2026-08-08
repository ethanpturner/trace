# ForgeFlow GitHub Integration

**Document owner:** Platform Engineering

**Document status:** Current

**Last updated:** 2026-07-30

# 1. Purpose

This document describes how ForgeFlow integrates with GitHub.

The GitHub integration is responsible for:

- Customer authentication
- Repository installation
- Repository access
- Pull-request event processing
- Pull-request commenting

GitHub is the only supported source-code provider in the current release.

# 2. GitHub App

ForgeFlow integrates with customer repositories using a GitHub App.

Each customer organization installs the application into one or more GitHub organizations.

During installation the customer administrator selects which repositories ForgeFlow may access.

Repository access may be expanded or reduced later through normal GitHub administration.

ForgeFlow does not require customers to create personal access tokens.

# 3. Authentication

Customer users authenticate through GitHub OAuth.

GitHub confirms user identity before redirecting the browser back to ForgeFlow.

ForgeFlow establishes an application session after successful authentication.

Repository access for background processing is performed independently through the GitHub App installation.

# 4. Repository Permissions

The GitHub App requests only the permissions required to support configured ForgeFlow features.

Typical capabilities include:

- Reading repository metadata
- Reading pull-request information
- Reading repository contents
- Posting pull-request comments
- Receiving webhook events

Additional permissions may be introduced as product capabilities evolve.

Customers should periodically review granted GitHub App permissions.

# 5. Installation Tokens

ForgeFlow does not permanently store repository access tokens.

When repository access is required:

1. The worker identifies the GitHub installation.
2. ForgeFlow authenticates using the GitHub App.
3. GitHub issues a short-lived installation token.
4. The worker retrieves required repository content.
5. The installation token expires according to GitHub policy.

Installation tokens are intended only for temporary repository access.

# 6. Webhook Processing

GitHub sends webhook events to the ForgeFlow webhook receiver whenever subscribed repository events occur.

Supported events currently include:

- Pull request opened
- Pull request synchronized
- Pull request reopened
- Pull request closed
- Installation events
- Installation permission updates

Incoming webhook requests are validated before processing.

Relevant events are converted into background analysis jobs.

Unsupported event types are ignored.

# 7. Repository Content Retrieval

After a supported webhook event is received:

1. A background worker retrieves the queued job.
2. The worker requests a short-lived installation token.
3. Repository metadata is retrieved.
4. Pull-request metadata is retrieved.
5. Selected repository files are downloaded.
6. Repository documentation may also be retrieved when required for analysis.

ForgeFlow attempts to retrieve only repository content relevant to the requested analysis.

# 8. Pull-Request Comments

Organizations may choose to enable automatic pull-request comments.

When enabled, ForgeFlow posts a summary comment containing:

- High-level observations
- Potential review topics
- Links to the complete ForgeFlow analysis

Customers remain responsible for evaluating the recommendations before merging code.

# 9. Repository Access Scope

Repository access is intended to remain limited to repositories selected during GitHub App installation.

Background workers operate within the permissions associated with the installation token.

ForgeFlow does not request repository access outside the installed scope.

# 10. Repository Metadata

ForgeFlow stores metadata required to support product functionality.

Examples include:

- Repository identifier
- Installation identifier
- Organization identifier
- Repository name
- Pull-request identifier
- Branch names
- Selected operational metadata

Repository metadata supports job execution, auditing, and customer reporting.

# 11. GitHub Rate Limits

ForgeFlow attempts to minimize GitHub API usage.

Methods include:

- Background processing
- Limited repository retrieval
- Retry behavior
- Operational caching

Workers should avoid unnecessary repeated repository downloads.

# 12. Failure Handling

Repository access failures may occur because of:

- Revoked installation
- Expired installation token
- Network interruption
- GitHub service outage
- Permission changes

Recoverable failures may be retried.

Unrecoverable failures require customer or operational intervention.

# 13. Security Considerations

ForgeFlow follows several security principles when interacting with GitHub.

These include:

- Delegated authentication
- Short-lived repository credentials
- Installation-scoped permissions
- Background processing
- Secure credential storage
- Event validation
- Operational logging

Customers remain responsible for:

- Reviewing granted repository permissions
- Managing GitHub organization membership
- Removing unused installations
- Monitoring privileged repository access

# 14. Operational Assumptions

This integration assumes:

- GitHub OAuth correctly authenticates users.
- GitHub installation tokens remain short-lived.
- GitHub webhook events originate from GitHub infrastructure.
- GitHub repository permissions accurately represent customer intent.
- Repository administrators periodically review installed applications.

# 15. Known Limitations

Current limitations include:

- GitHub is the only supported repository provider.
- Repository permissions are controlled through GitHub.
- Large pull requests require additional processing time.
- Repository analysis depends on GitHub API availability.
- Event delivery timing depends on GitHub infrastructure.

# 16. Related Documents

- architecture-overview.md
- operations-guide.md
- security-overview.md
- ai-analysis.md

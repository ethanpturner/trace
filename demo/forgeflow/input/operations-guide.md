# ForgeFlow Operations Guide

**Document owner:** Platform Operations

**Document status:** Internal

**Last updated:** 2026-07-31

# 1. Purpose

This document describes normal operational procedures for the ForgeFlow platform.

It is intended for platform engineers and operations personnel responsible for maintaining production services.

Topics include:

- Job processing
- Queue operations
- Failure recovery
- Artifact handling
- Operational troubleshooting
- Administrative support

This document is not intended to describe the complete security architecture.

# 2. Background Job Processing

Most customer activity is processed asynchronously.

Typical workflow:

1. GitHub sends an event.
2. The webhook receiver validates the incoming request.
3. A background job is created.
4. The job is added to the Redis queue.
5. An available worker retrieves the job.
6. Repository content is retrieved from GitHub.
7. Repository content is prepared for AI analysis.
8. The AI provider returns a structured response.
9. Results are stored.
10. Job status is updated.
11. Pull-request comments may be published.

Jobs are expected to complete within several minutes.

# 3. Queue Processing

Workers poll Redis continuously.

Each queued job contains:

- Organization identifier
- Repository identifier
- Installation identifier
- Pull-request identifier
- Delivery identifier
- Retry counter
- Processing state

Workers may execute in parallel.

Temporary worker failures are expected and should not normally require operator intervention.

# 4. Retry Behavior

Recoverable failures may be retried automatically.

Typical retry conditions include:

- Temporary GitHub API failures
- AI provider timeouts
- Network interruptions
- Storage failures
- Worker restarts

Operations personnel may also manually retry failed jobs through the administrative interface.

Manual retries reuse the original job metadata whenever possible.

Where repository artifacts are still available, the retry process may reuse previously stored analysis artifacts instead of downloading repository content again.

This reduces GitHub API traffic during operational recovery.

# 5. Artifact Storage

During analysis, ForgeFlow creates several temporary artifacts.

Examples include:

- Pull-request metadata
- Repository diffs
- Selected repository files
- Prompt construction artifacts
- Structured AI responses
- Diagnostic information

Artifacts are stored in managed object storage.

Object paths include the organization identifier and job identifier.

Large artifacts are referenced from PostgreSQL rather than stored directly in relational tables.

# 6. Artifact Retention

Artifacts remain available for operational troubleshooting and customer support.

The current retention target is **30 days**.

After the retention window expires, scheduled cleanup jobs remove eligible artifacts.

Support personnel may request temporary retention extensions during active investigations.

Operational teams should avoid manually deleting artifacts unless directed by the incident response process.

# 7. Job Recovery

If a worker terminates unexpectedly:

- Remaining jobs stay in Redis.
- Another worker may continue processing.
- Failed jobs may be retried.
- Job metadata remains in PostgreSQL.

Duplicate processing is uncommon but may occur following infrastructure failures.

Operations personnel should review duplicate comments before manual cleanup.

# 8. AI Provider Interaction

The analysis worker constructs requests using:

- Pull-request changes
- Selected repository files
- Repository documentation
- Repository metadata
- Internal analysis instructions

Workers perform basic request validation before sending content to the provider.

The worker validates the returned response schema before processing the result.

If schema validation fails, the job is marked unsuccessful.

Provider-specific operational limits are configured through application configuration.

# 9. Automatic Pull-Request Comments

If pull-request comments are enabled for the customer organization:

1. Schema validation succeeds.
2. The comment service formats the response.
3. Formatting rules are applied.
4. The comment is published to GitHub.

The worker records publication status for troubleshooting.

If publication fails, the job is marked partially successful.

Operators may retry comment publication independently from the analysis job.

# 10. Administrative Troubleshooting

Authorized operations personnel may:

- Retry failed jobs
- Disable repository integrations
- Review operational logs
- Review worker failures
- Review queue status
- Review provider failures
- Confirm customer configuration

Operations personnel should avoid modifying production customer configuration unless necessary for incident resolution.

# 11. Logging

Operational logging includes:

- Job lifecycle
- Queue activity
- Retry attempts
- Provider request timing
- API failures
- Worker failures
- Administrative activity
- Cleanup jobs

Logs should avoid storing authentication credentials.

Large request bodies should not normally be written to operational logs.

# 12. Scaling

Worker count may increase automatically based on queue depth.

Webhook receivers may also scale independently during periods of high GitHub event volume.

Scaling decisions are based on:

- Queue depth
- CPU utilization
- Memory utilization
- Processing latency

Scaling policies are maintained separately from application configuration.

# 13. Operational Monitoring

Platform monitoring tracks:

- Queue depth
- Worker availability
- Job duration
- Retry count
- GitHub API failures
- AI provider latency
- Storage failures
- Database availability

Alerts are generated when configured operational thresholds are exceeded.

# 14. Administrative Access

Operations personnel authenticate through the corporate identity platform.

Operational actions are recorded in the centralized logging platform.

Administrative sessions automatically expire after inactivity.

Break-glass procedures are maintained separately.

# 15. Disaster Recovery

The platform supports recovery through:

- Managed database backups
- Infrastructure recreation
- Worker redeployment
- Object storage durability
- Queue recovery

Recovery procedures are tested periodically.

# 16. Operational Assumptions

This guide assumes:

- GitHub services remain available.
- AI provider services remain available.
- Managed cloud infrastructure remains healthy.
- Repository artifacts remain available during retry operations.
- Administrative authentication services remain available.

# 17. Known Limitations

Current operational limitations include:

- Large pull requests require longer processing times.
- AI provider latency varies throughout the day.
- Repository analysis may require multiple retries during provider outages.
- Duplicate processing may occur following unexpected infrastructure failures.
- Operational procedures continue to evolve as platform usage grows.

# 18. Related Documentation

- architecture-overview.md
- security-overview.md
- github-integration.md
- ai-analysis.md

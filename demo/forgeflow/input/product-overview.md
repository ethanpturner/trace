# ForgeFlow Product Overview

**Document owner:** Product Management

**Document status:** Current

**Last updated:** 2026-07-15

## 1. Product Summary

ForgeFlow is an AI-assisted pull-request review platform for software-development teams.

ForgeFlow connects to customer GitHub organizations and analyzes pull requests when code is opened or updated. It provides developers with concise summaries, potential concerns, and suggested areas for closer review.

ForgeFlow is intended to make code review faster and more consistent. It supplements human review and does not replace developer approval, testing, or existing security tools.

## 2. Primary Users

ForgeFlow is designed for:

- Software developers
- Engineering leads
- Repository administrators
- Platform engineering teams
- Application security teams

Customer administrators configure the GitHub integration and select which repositories ForgeFlow can access.

Developers use ForgeFlow to review analysis results associated with their pull requests.

## 3. Core User Experience

A typical ForgeFlow workflow is:

1. A customer administrator installs the ForgeFlow GitHub App.
2. The administrator selects one or more repositories.
3. A developer opens or updates a pull request.
4. GitHub notifies ForgeFlow of the pull-request event.
5. ForgeFlow retrieves the relevant changes and selected repository context.
6. ForgeFlow submits the selected content for AI-assisted analysis.
7. ForgeFlow creates a structured review result.
8. The result is displayed in the ForgeFlow web application.
9. When enabled, ForgeFlow adds a summary comment to the GitHub pull request.

Customers may enable or disable automatic pull-request comments at the organization level.

## 4. Major Product Capabilities

### GitHub integration

ForgeFlow integrates with GitHub through a GitHub App.

The integration supports:

- Repository selection
- Pull-request event processing
- Pull-request content retrieval
- Review-summary comments
- Installation-level configuration

ForgeFlow requests access only to repository information required for the configured analysis features.

### AI-assisted analysis

ForgeFlow analyzes:

- Pull-request changes
- Selected source files
- Repository documentation
- Pull-request descriptions
- Relevant configuration files

The analysis service produces a structured result containing:

- Summary of the change
- Important implementation observations
- Potential quality concerns
- Potential security-relevant concerns
- Suggested review questions

AI-generated results may be incomplete or incorrect. Developers are expected to use professional judgment when reviewing them.

### Web application

The ForgeFlow web application allows users to:

- Sign in with GitHub
- View connected repositories
- Review analysis status
- View completed analyses
- Manage organization settings
- Configure pull-request comments
- Retry selected failed analyses

### Organization administration

Customer administrators can:

- Install or remove the GitHub App
- Select connected repositories
- Invite organization users
- Enable or disable automatic comments
- View usage information
- Request deletion of organization data

## 5. Authentication

ForgeFlow users authenticate through GitHub.

ForgeFlow does not maintain a separate username and password system.

A user must successfully authenticate with GitHub before accessing ForgeFlow customer functionality.

Access to organization data is based on the user’s ForgeFlow organization membership and configured role.

## 6. Customer Data

ForgeFlow may process:

- GitHub user identity information
- Organization and repository metadata
- Pull-request metadata
- Source-code changes
- Selected repository files
- Repository documentation
- AI-generated analysis results
- Product usage and operational metadata

Customer source content is processed only to provide the configured ForgeFlow service.

ForgeFlow does not use customer source code to train public AI models.

## 7. Source-Content Processing

ForgeFlow retrieves only the content selected as relevant to the current pull-request analysis.

Source files are treated as temporary processing data and are deleted after analysis completes.

Structured analysis results and operational metadata may remain available so customers can review prior activity.

ForgeFlow may limit the amount or type of content sent for analysis based on:

- File size
- File type
- Pull-request size
- Repository configuration
- Provider input limits

## 8. External AI Provider

ForgeFlow uses a third-party AI provider to perform parts of the pull-request analysis.

The provider receives selected pull-request and repository content necessary for the requested analysis.

According to the provider’s enterprise API terms, customer API content is not used to train publicly available models.

ForgeFlow does not provide the AI provider with GitHub installation credentials or direct repository access.

## 9. Pull-Request Comments

Customers may configure ForgeFlow to publish analysis summaries directly to GitHub pull requests.

Comments are intended to help developers quickly identify areas that may require additional attention.

Comments generally contain:

- A short change summary
- Important observations
- Suggested review questions
- A link to the full ForgeFlow result

ForgeFlow attempts to avoid including unnecessary source-code content in pull-request comments.

Customers remain responsible for reviewing and acting on the information presented.

## 10. Data Separation

ForgeFlow is a multi-customer service.

Customer information is logically associated with a ForgeFlow organization.

Repository configuration, analysis jobs, results, and related artifacts include an organization identifier so that ForgeFlow can associate information with the appropriate customer.

Users should only be able to access organizations in which they have approved membership.

## 11. Availability and Processing

Pull-request analysis occurs asynchronously.

After receiving a GitHub event, ForgeFlow creates an analysis job and processes it in the background.

Processing time varies based on:

- Pull-request size
- Repository content
- AI-provider response time
- Current system load
- Retry behavior

A failed analysis may be retried automatically or manually.

ForgeFlow may limit usage to protect service reliability and control excessive processing.

## 12. Customer Responsibilities

Customers are responsible for:

- Selecting appropriate repositories
- Managing GitHub organization access
- Reviewing GitHub App permissions
- Reviewing AI-generated output
- Avoiding submission of content prohibited by their organizational policies
- Removing ForgeFlow access when it is no longer needed
- Maintaining appropriate GitHub identity and organization controls

## 13. Product Limitations

ForgeFlow does not guarantee that it will:

- Identify every software defect
- Identify every security vulnerability
- Produce correct recommendations
- Replace human code review
- Replace testing
- Replace static or dynamic security analysis
- Understand every programming language or framework
- Detect malicious repository content in every case

ForgeFlow output should be treated as review assistance rather than authoritative approval.

## 14. Future Product Direction

Potential future capabilities may include:

- Organization-specific review policies
- Additional repository providers
- Security-tool integrations
- Pull-request risk prioritization
- Architecture-aware analysis
- Custom analysis profiles
- Team-level reporting

Future capabilities are subject to product validation and are not part of the current product commitment.

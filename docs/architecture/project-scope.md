# Project Scope

## Working Title

**Project name:** **Trace**

**Tagline:** *Context-Aware Security Architecture Analysis*

**Core principle:** *Evidence over assumptions. Context over checklists.*

## Problem Statement

Traditional security architecture reviews and threat models are difficult to scale. They depend heavily on reviewer experience, often produce inconsistent findings, and frequently lack sufficient business and technical context.

Automated approaches can increase speed, but they often generate excessive false positives because they do not understand internal platforms, inherited controls, implementation context, or alternative ways that security requirements may be satisfied.

This project will demonstrate a context-aware, evidence-driven approach to AI-assisted security architecture analysis and threat modeling.

## Target User

The primary user is a product security engineer, security architect, or application security engineer reviewing the design of a software system.

Secondary users may include:

- Software architects
- Platform security engineers
- Development teams
- Risk and compliance reviewers

## Primary Use Case

A security reviewer provides architecture documentation and structured system information.

The system:

1. Extracts relevant architectural context.
2. Identifies assets, components, data flows, and trust boundaries.
3. Generates candidate threats.
4. Maps applicable security requirements and controls.
5. Evaluates available evidence.
6. Distinguishes supported findings from assumptions and missing information.
7. Produces a structured security assessment.
8. Preserves enough reasoning and evidence for a reviewer to understand how conclusions were reached.

## MVP Capabilities

The MVP will:

- Accept Markdown or text-based architecture documentation.
- Accept a structured project definition in JSON or YAML.
- Extract system components, assets, data flows, and trust boundaries.
- Generate candidate threats using a defined threat-analysis methodology.
- Map threats to security requirements or controls.
- Attach evidence references to important claims.
- Mark unsupported conclusions as assumptions or questions.
- Produce a structured Markdown report.
- Record workflow execution details for demonstration and debugging.
- Support human review before findings are finalized.

## Non-Goals

The MVP will not:

- Replace a qualified security reviewer.
- Perform production vulnerability scanning.
- Analyze source code comprehensively.
- Guarantee that all threats or vulnerabilities are identified.
- Automatically block software releases.
- Connect to proprietary enterprise systems.
- Reproduce confidential intellectual property from prior employers.
- Provide fully autonomous remediation.
- Support every cloud platform, programming language, or security framework.

## Demo Scenario

The initial demo will analyze a fictional web application consisting of:

- A public web frontend
- An API service
- A relational database
- An identity provider
- Object storage
- A CI/CD pipeline
- An administrative interface
- One or more third-party integrations

The documentation will intentionally omit some security controls so the system can demonstrate:

- Evidence-based conclusions
- Explicit assumptions
- Clarifying questions
- Control inheritance
- False-positive reduction
- Human review

## Success Criteria

The MVP is successful when it can:

- Produce a coherent threat model from a repeatable demo input.
- Trace major findings to source evidence or explicitly label them unsupported.
- Separate confirmed risks from assumptions and missing information.
- Generate output that a security professional can review and refine.
- Explain why each significant finding was generated.
- Complete the demo workflow reliably.
- Show measurable improvement over a single-pass generic LLM prompt.

## Evaluation Metrics

Initial metrics will include:

- Percentage of findings with supporting evidence
- Number of unsupported claims
- False-positive rate
- Number of useful clarifying questions
- Reviewer acceptance rate
- Reviewer edits required
- Threat coverage
- Requirement-mapping accuracy
- Execution time
- Model cost per assessment

## Constraints

- Development will occur on personally owned equipment.
- The project will use fictional or publicly available data.
- No confidential former-employer information will be used.
- Initial development will prioritize demonstration quality over production scale.
- The system should be understandable enough to explain during interviews and a technical presentation.
- The initial implementation should remain small enough for one developer to maintain.

## Assumptions

- Input documentation will be incomplete.
- Model outputs will sometimes be incorrect.
- Human review remains necessary.
- Security requirements may be satisfied through multiple implementations.
- Some controls may be inherited from platforms or shared services.
- Evidence quality matters more than raw finding volume.
- Workflow transparency is important for user trust.

## Open Questions

- Which threat-analysis methodology should the MVP use?
- Which model provider or providers should be supported initially?
- ~~Should the first interface be a CLI, local web application, or both?~~ Resolved by DEC-032: a CLI through M4.
- How should inherited controls be represented?
- What confidence model should be used?
- How should duplicate or overlapping threats be consolidated?
- What minimum evidence should be required before producing a finding?
- Which workflow steps require explicit human approval?

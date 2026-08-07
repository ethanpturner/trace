# Trace — Design Principles

**Project:** Trace

**Subtitle:** Context-Aware Security Architecture Analysis

**Document version:** 0.1

**Status:** Proposed

**Last updated:** 2026-08-05

## 1. Purpose

This document defines the principles used to guide product, architecture, workflow, and implementation decisions for Trace.

These principles exist to prevent the project from drifting into:

- A generic AI security assistant
- A large checklist generator
- An opaque collection of agents
- A demonstration optimized for impressive output rather than accuracy
- A system that produces more findings without producing better analysis

When two reasonable design options exist, the option that better follows these principles should generally be preferred.

Principles are not absolute rules. Exceptions may be appropriate, but consequential exceptions should be documented in the decision log.

## 2. Evidence Over Assumptions

Trace should prefer conclusions supported by addressable evidence.

A conclusion should clearly distinguish among:

- Documented fact
- Reviewer-confirmed fact
- Reasonable inference
- Assumption
- Unknown
- Contradiction

A model’s confidence is not evidence.

Repeated statements from multiple agents are not independent evidence when they originate from the same source material.

### Product implications

Trace should:

- Link important claims to source evidence
- Display the evidence supporting a finding
- Preserve contradictory evidence
- Show when a conclusion depends on an assumption
- Allow reviewers to request or add evidence
- Prevent unsupported conclusions from silently becoming final findings

### Engineering implications

The implementation should:

- Create stable evidence references
- Preserve source locations
- Hash source content
- Validate evidence identifiers
- Prevent report generation from inventing new evidence
- Store evidence assessments separately from model confidence

### Decision test

Ask:

What evidence supports this conclusion, and can the reviewer inspect it?

If that question cannot be answered, the conclusion should remain provisional.

## 3. Context Over Checklists

Trace should understand the system before applying security requirements.

A security requirement may be valid generally but irrelevant to a specific component, deployment model, or threat scenario.

Context includes:

- Business purpose
- System criticality
- Data sensitivity
- Technology
- Deployment environment
- Exposure
- Trust boundaries
- Existing controls
- Shared platforms
- Control inheritance
- Compensating controls
- Operational constraints

### Product implications

Trace should:

- Build an approved architecture baseline before generating findings
- Map requirements to specific threats and components
- Explain why a requirement applies
- Recognize alternate ways to satisfy a requirement
- Recognize inherited and compensating controls
- Avoid producing one finding for every undocumented checklist item

### Engineering implications

The implementation should:

- Represent components, assets, flows, and boundaries as structured objects
- Preserve requirement-applicability rationale
- Separate requirement applicability from control satisfaction
- Use the ControlMapping relationship rather than jumping directly from requirements to findings
- Require explicit states such as applicable, conditional, unverified, satisfied, and unmet

### Decision test

Ask:

Would an experienced security architect apply this requirement in this architecture for this threat?

If applicability cannot be explained, the requirement should not become a finding.

## 4. Questions Over False Certainty

Trace should ask a useful question rather than present an unsupported conclusion as fact.

Incomplete documentation is normal.

When information is missing, Trace should decide whether the appropriate output is:

- A clarifying question
- A documentation gap
- An explicit assumption
- A low-confidence candidate threat
- No output

### Product implications

Questions should be:

- Specific
- Prioritized
- Connected to a decision
- Clear about why the answer matters
- Capable of changing the assessment

Weak question:

Is authentication secure?

Better question:

Does the webhook receiver verify the repository provider’s signature before creating an analysis job?

### Engineering implications

The implementation should:

- Model questions as first-class objects
- Link questions to threats, controls, mappings, or findings
- Record user responses as evidence
- Support blocking and non-blocking questions
- Track whether answered questions change downstream conclusions

### Decision test

Ask:

Would answering this question materially change the analysis?

If not, the question is probably noise.

## 5. Human Judgment Over Model Authority

Trace assists qualified security professionals. It does not replace them.

Models may propose, organize, compare, and critique analysis.

Humans remain responsible for:

- Approving architecture context
- Resolving material ambiguity
- Interpreting business impact
- Approving findings
- Assigning final severity
- Accepting risk
- Finalizing reports

### Product implications

Trace should make human review efficient rather than ceremonial.

Review interfaces should show:

- What changed
- Why a conclusion was generated
- Supporting and contradictory evidence
- Assumptions
- Confidence
- Open questions
- Agent critiques

### Engineering implications

The implementation should:

- Include explicit human checkpoints
- Record reviewer decisions
- Preserve reviewer edits
- Prevent agents from approving their own findings
- Prevent provisional output from appearing as final
- Support resuming workflows after review

### Decision test

Ask:

Is the system supporting human judgment, or quietly replacing it?

If the reviewer cannot meaningfully inspect or override a conclusion, the design is wrong.

## 6. Structured State Over Conversational Memory

Important system knowledge should exist as validated domain objects, not only inside prompts or chat history.

Conversational context is useful for interaction but unreliable as authoritative application state.

### Product implications

Users should be able to inspect structured representations of:

- Components
- Assets
- Data flows
- Trust boundaries
- Threats
- Requirements
- Controls
- Questions
- Findings
- Reviewer decisions

### Engineering implications

The implementation should:

- Use schema-validated models
- Pass identifiers and structured objects through workflow state
- Avoid continuously expanding prompt transcripts
- Persist authoritative state outside the model
- Version important schemas
- Validate model output before persistence

### Decision test

Ask:

Could the application recover this fact without replaying an entire model conversation?

If not, the information probably belongs in structured state.

## 7. Deterministic Enforcement Over Prompt-Only Rules

Prompts should guide model behavior, but important guarantees should be implemented in code.

Prompts are probabilistic controls.

They are not sufficient for enforcing:

- Required fields
- Status transitions
- Retry limits
- Cost limits
- Evidence thresholds
- Permissions
- Approved output filtering
- Identifier validity
- Cross-object relationships

### Product implications

The user should receive consistent behavior even when a model response is imperfect.

### Engineering implications

Deterministic code should handle:

- Schema validation
- Relationship validation
- Workflow routing
- Duplicate handling
- Execution limits
- Report rendering
- Approval enforcement
- File access
- Persistence
- Audit logging

### Decision test

Ask:

What happens when the model ignores this instruction?

If the answer is “the system behaves incorrectly,” the rule should probably be enforced outside the prompt.

## 8. Explainability as a Core Capability

Explainability should not be limited to a developer debug screen.

A reviewer should be able to understand how an important conclusion was produced.

Trace should expose concise reasoning artifacts, not private model chain-of-thought.

Useful explanation includes:

- Relevant source evidence
- Approved architecture context
- Threat scenario
- Requirement applicability
- Existing controls
- Evidence assessment
- Assumptions
- Critiques
- Reviewer decision

### Product implications

Every significant finding should support a “Why?” view.

That view should help answer:

- Why was this threat considered?
- Why does this requirement apply?
- What control was evaluated?
- What evidence supports the conclusion?
- What uncertainty remains?
- Did another workflow stage challenge it?
- What did the reviewer decide?

### Engineering implications

The implementation should:

- Preserve object lineage
- Version prompts and workflow nodes
- Link outputs to execution records
- Store concise rationales
- Preserve criticism and reviewer decisions
- Avoid requiring access to hidden reasoning

### Decision test

Ask:

Can a reviewer defend this conclusion to an engineering team using the information Trace preserves?

If not, the output is not sufficiently explainable.

## 9. Quality Over Finding Volume

Trace should optimize for useful, defensible conclusions rather than the largest possible number of findings.

More findings can create:

- Review fatigue
- Reduced trust
- Duplicate work
- Poor prioritization
- Defensive engineering responses
- Missed high-impact risks hidden in noise

A successful assessment may produce few or no findings.

### Product implications

Trace should separate:

- Findings
- Questions
- Documentation gaps
- Assumptions
- Existing effective controls
- Rejected candidates

### Engineering implications

The implementation should:

- Deduplicate related threats and findings
- Require minimum finding criteria
- Preserve rejected candidates for evaluation without displaying them as results
- Measure reviewer rejection and edit rates
- Avoid quotas for threat or finding count

### Decision test

Ask:

Would a qualified reviewer keep this conclusion and act on it?

If not, it should probably not be a finding.

## 10. Evaluation Over Intuition

Trace should improve through repeatable measurement.

A prompt, agent, model, or workflow change should not be accepted merely because its output appears more sophisticated.

Changes should be compared using:

- Versioned scenarios
- Expected outputs
- Reviewer judgments
- False-positive rates
- False-negative rates
- Evidence coverage
- Edit rates
- Cost
- Runtime
- Reliability

### Product implications

Trace should make evaluation visible and useful.

The project should be able to explain:

- What improved
- What regressed
- What changed
- How the result was measured
- Whether additional complexity was justified

### Engineering implications

The implementation should:

- Record prompt and workflow versions
- Preserve benchmark fixtures
- Support repeatable runs
- Track reviewer decisions
- Calculate metrics
- Maintain regression tests
- Compare agent-enabled and agent-disabled workflows

### Decision test

Ask:

What measurable problem does this change solve?

If no evaluation can demonstrate value, the change may be unnecessary.

## 11. Simplicity Over Performative Sophistication

Trace should use the least complicated architecture that produces the required quality.

The project should not add:

- Agents
- Models
- Databases
- Queues
- Vector stores
- Microservices
- Cloud services
- Kubernetes
- Frameworks

merely to appear advanced.

### Product implications

The user experience should remain understandable.

Complexity should be visible only when it helps the reviewer make a better decision.

### Engineering implications

The initial MVP should prefer:

- One local application
- One primary language
- One primary model
- SQLite
- Local artifact storage
- Explicit workflow stages
- A limited agent set
- Simple interfaces
- Bounded retrieval

Complexity should be introduced only when a measured limitation requires it.

### Decision test

Ask:

Does this component improve quality, reliability, security, or maintainability enough to justify its cost?

If not, remove it.

## 12. Narrow Agents Over General Autonomy

Each agent should have one bounded reasoning responsibility.

Trace should not create a general security agent with broad authority over the application.

### Product implications

Agent responsibilities should be understandable to reviewers and developers.

Examples:

- Extract context
- Generate threats
- Map requirements and controls
- Validate evidence
- Critique analysis
- Generate report prose

### Engineering implications

Agents should have:

- Defined inputs
- Defined outputs
- Limited tools
- Explicit prohibitions
- Bounded retries
- Versioned prompts
- Evaluation scorecards

Agents should not:

- Create their own goals
- Change workflow configuration
- Write authoritative state directly
- Approve findings
- Access arbitrary tools
- Run indefinitely

### Decision test

Ask:

Can this agent’s responsibility be described in one sentence?

If not, it is probably too broad.

## 13. Least Privilege for Models and Tools

Model-assisted components should receive only the data and capabilities needed for their task.

### Product implications

Users should be able to understand which external services receive assessment information.

### Engineering implications

Agents should not initially have:

- General internet access
- Shell access
- Arbitrary filesystem access
- Direct database writes
- Cloud credentials
- GitHub write permissions
- Ticketing-system permissions
- Dynamic code execution

Evidence retrieval should be controlled by the application.

Model-provider access should be:

- Configured centrally
- Auditable
- Limited by assessment
- Subject to cost and data-handling controls

### Decision test

Ask:

What is the minimum data and tool access required to complete this task?

Anything beyond that should require justification.

## 14. Source Content Is Untrusted

Documents analyzed by Trace may be incorrect, malicious, contradictory, or intentionally manipulative.

Source content should never be treated as authoritative workflow instruction.

### Product implications

Trace should be capable of identifying and surfacing suspicious document content.

Prompt-injection attempts should be treated as security-relevant input, not followed as instructions.

### Engineering implications

The application should:

- Separate system instructions from source data
- Delimit untrusted content
- Restrict tools
- Validate outputs
- Test prompt-injection fixtures
- Avoid placing source content in high-authority instruction positions
- Preserve suspicious excerpts for review

### Decision test

Ask:

Could an uploaded document change what the agent is allowed to do?

The answer must be no.

## 15. Explicit Uncertainty Over Artificial Precision

Trace should communicate uncertainty honestly.

A numeric confidence score can appear scientific while representing little more than model intuition.

Trace should prefer understandable classifications and explanations.

### Product implications

The system should communicate:

- What is known
- What is inferred
- What remains unknown
- What evidence would change the conclusion
- Which assumptions matter

### Engineering implications

The implementation should:

- Use categorical confidence where appropriate
- Avoid treating confidence as probability
- Separate evidence strength from model confidence
- Require rationales for high-impact uncertain conclusions
- Trigger human review for important unresolved ambiguity

### Decision test

Ask:

Does this score help the reviewer make a decision, or merely make the output look precise?

Remove metrics that do not improve judgment.

## 16. Preserve Lineage Over Silent Mutation

Trace should preserve how objects and conclusions changed.

A reviewer should be able to distinguish among:

- Original model output
- Validation corrections
- Critic recommendations
- Reviewer edits
- Final approved state

### Product implications

Users should be able to understand why a finding changed or disappeared.

### Engineering implications

The implementation should:

- Record reviewer decisions
- Preserve superseded objects where useful
- Link objects to workflow runs
- Track generation and prompt versions
- Avoid silently overwriting evidence
- Preserve rejected findings for evaluation

The MVP does not require full event sourcing, but meaningful decisions should remain visible.

### Decision test

Ask:

Can we explain how the final object differs from the original proposal?

If not, too much history has been discarded.

## 17. Separate Analysis From Presentation

Structured analysis should remain authoritative.

Report prose and user-interface summaries are representations of approved analysis, not independent sources of truth.

### Product implications

Reports should be readable without weakening accuracy.

### Engineering implications

The report-generation agent may:

- Summarize
- Reorder
- Improve clarity
- Adjust tone

It may not:

- Create new findings
- Change severity
- Invent evidence
- Remove important limitations
- Convert questions into vulnerabilities

A deterministic renderer should assemble final reports from approved objects.

### Decision test

Ask:

Is this information part of the analysis, or only a way of presenting the analysis?

Keep those responsibilities separate.

## 18. Secure Defaults Over Optional Safety

Security and quality protections should be enabled by default.

Examples include:

- Human context review
- Human finding review
- External tracing disabled for sensitive data
- Bounded retries
- Cost limits
- Schema validation
- Evidence requirements
- Local storage separation
- Tool restrictions
- Prompt-injection protections

### Product implications

Users should not have to discover and enable the safe configuration.

### Engineering implications

Bypassing a protection should require an explicit configuration decision.

Riskier modes should be clearly labeled.

### Decision test

Ask:

What happens when a user accepts every default?

The resulting configuration should still be safe and defensible.

## 19. Clean-Room Development Over Employer-Derived Reconstruction

Trace must remain independently designed and implemented.

The project may be informed by general professional experience, but it should not reproduce confidential employer systems, prompts, requirements, code, data, or internal documentation.

### Product implications

The demo should use:

- Fictional organizations
- Synthetic architectures
- Public standards
- Original requirements
- Publicly documented technologies
- Independently created examples

### Engineering implications

The repository should not contain:

- Former-employer names
- Internal identifiers
- Proprietary requirements
- Confidential architecture details
- Reconstructed source code
- Internal prompts
- Non-public screenshots
- Real assessment data

### Decision test

Ask:

Could this artifact be confidently shared publicly and explained as independently created?

If not, it should not enter the Trace project.

## 20. Build for the Reviewer’s Decision

Every feature should help a reviewer make a better or faster security decision.

Features should not exist only because they are technically interesting.

A feature may create value by helping the reviewer:

- Understand architecture
- Identify important threats
- Validate controls
- Resolve ambiguity
- Prioritize risk
- Explain findings
- Track changes
- Reduce repetitive work
- Compare assessment versions

### Decision test

Ask:

Which reviewer decision becomes easier, faster, or more accurate because of this feature?

If no decision improves, the feature is probably not a priority.

## 21. Principle Hierarchy

When principles conflict, use the following general priority:

1. Protect confidentiality, integrity, and human authority.
2. Preserve evidence and accuracy.
3. Avoid unsupported findings.
4. Maintain explainability and lineage.
5. Improve reviewer decisions.
6. Support repeatable evaluation.
7. Reduce cost and latency.
8. Add convenience.
9. Add architectural sophistication.

For example, a faster workflow should not be preferred if it materially increases unsupported findings.

## 22. Applying the Principles

Significant product and architecture proposals should answer:

1. Which user problem does this solve?
2. Which design principles support it?
3. Which principles does it weaken?
4. What evidence shows the change is needed?
5. How will success be evaluated?
6. What new security risks does it introduce?
7. Can a simpler approach solve the same problem?
8. Does it belong in the MVP, roadmap, or future-features list?

Consequential decisions should be recorded in decision log.md.

## 23. Summary

Trace should be designed as a disciplined security-analysis system, not as an autonomous AI demonstration.

Its central principles are:

**Evidence over assumptions.**

**Context over checklists.**

**Questions over false certainty.**

**Human judgment over model authority.**

**Quality over finding volume.**

**Evaluation over intuition.**

**Simplicity over performative sophistication.**

These principles should remain stable even as models, frameworks, interfaces, and deployment architectures change.

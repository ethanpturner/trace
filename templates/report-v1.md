<!--
report-v1 — the MVP assessment report template.

This file is a **structural specification, not an engine template.** No templating library renders
it. The Report Rendering node composes the report in Python, and a test compares the headings,
numbering, anchors, ownership comments, and empty-section wording it produces against this file.
The template is the artifact that has to be edited to change the report's shape; the renderer
follows it.

Three marker forms appear below, and they are the whole grammar:

    {{ agent.<key> }}    prose written by the Report Generation agent, one key per prose section
    {{ render.<block> }} a block composed deterministically from approved objects
    {{ empty.<block> }}  the fixed wording emitted in place of that block when it has no rows

Two rules hold everywhere (DEC-035):

- **Every section has exactly one owner.** A section contains either one `agent.*` marker or one or
  more `render.*` markers, never both. Prose and rendered data are never interleaved, so a reader
  always knows which parts of a page a model wrote.
- **Every `render.*` block that can be empty has an `empty.*` counterpart**, defined verbatim at the
  bottom of this file. Empty is a defined outcome, and the wording for it is authored here rather
  than composed at runtime.

Section numbers and anchors are fixed by this file. They do not depend on content, on how many
findings exist, or on what any model wrote, so two renders of the same approved data produce the
same anchors. Anchors are written as explicit HTML anchor elements rather than relying on
heading-derived anchors, which differ between Markdown renderers and change whenever a title is
reworded.

Object anchors inside rendered blocks are the object's own identifier, lowercased: a finding
`fnd-003` is anchored `<a id="fnd-003"></a>`. Those are stable within an assessment, which is the
scope DEC-018 gives them and the scope a report is read in.
-->

# Security Architecture Assessment: {{ render.assessment_name }}

{{ render.report_header }}

<!-- owner: agent -->
<a id="s01-executive-summary"></a>
## 1. Executive summary

{{ agent.executive_summary }}

<!-- owner: rendered -->
<a id="s02-scope"></a>
## 2. Scope

{{ render.scope }}

{{ render.source_documents }}
{{ empty.source_documents }}

<!-- owner: agent -->
<a id="s03-system-overview"></a>
## 3. System overview

{{ agent.system_overview }}

<!-- owner: rendered -->
<a id="s04-architecture-summary"></a>
## 4. Architecture summary

{{ render.components }}
{{ empty.components }}

{{ render.actors }}
{{ empty.actors }}

{{ render.data_flows }}
{{ empty.data_flows }}

<!-- owner: rendered -->
<a id="s05-assets-and-trust-boundaries"></a>
## 5. Assets and trust boundaries

{{ render.assets }}
{{ empty.assets }}

{{ render.trust_boundaries }}
{{ empty.trust_boundaries }}

<!-- owner: agent -->
<a id="s06-risk-summary"></a>
## 6. Risk summary

{{ agent.risk_summary }}

<!-- owner: rendered -->
<a id="s07-significant-threats"></a>
## 7. Significant threats

{{ render.threats }}
{{ empty.threats }}

<!-- owner: rendered -->
<a id="s08-approved-findings"></a>
## 8. Approved findings

{{ render.findings }}
{{ empty.findings }}

<!-- owner: rendered -->
<a id="s09-documentation-gaps"></a>
## 9. Documentation gaps

{{ render.documentation_gaps }}
{{ empty.documentation_gaps }}

<!-- owner: rendered -->
<a id="s10-assumptions"></a>
## 10. Assumptions

{{ render.assumptions }}
{{ empty.assumptions }}

<!-- owner: rendered -->
<a id="s11-open-questions"></a>
## 11. Open questions

{{ render.open_questions }}
{{ empty.open_questions }}

<!-- owner: rendered -->
<a id="s12-existing-controls"></a>
## 12. Existing controls

{{ render.controls }}
{{ empty.controls }}

<!-- owner: rendered -->
<a id="s13-recommended-actions"></a>
## 13. Recommended actions

{{ render.recommended_actions }}
{{ empty.recommended_actions }}

<!-- owner: rendered -->
<a id="s14-methodology"></a>
## 14. Methodology

{{ render.methodology }}

{{ render.versions }}

<!-- owner: rendered -->
<a id="s15-evidence-appendix"></a>
## 15. Evidence appendix

{{ render.evidence }}
{{ empty.evidence }}

<!-- owner: agent -->
<a id="s16-assessment-limitations"></a>
## 16. Assessment limitations

{{ agent.limitations }}

---

<!--
Empty-section wording. Each string below is emitted verbatim in place of its block when that block
has no rows. None of them may be reworded at runtime, and none of them may be omitted: a section
that disappears when it is empty reads as a section that was never considered.

The wording is written to say what the absence means and what it does not. Absence of a finding is
not evidence of security, and absence of a documentation gap is not evidence of complete
documentation; both are statements about the material provided (DEC-009).
-->

<!-- empty.source_documents -->
No source documents were provided for this assessment. Nothing in this report is supported by
evidence, and no section below should be read as an assessment of the system.

<!-- empty.components -->
The approved context records no components. The architecture below is described only in prose.

<!-- empty.actors -->
The approved context records no actors. Who uses this system, and with what privileges, was not
established from the documentation provided.

<!-- empty.data_flows -->
The approved context records no data flows. Threats that depend on how data moves between
components could not be assessed against a documented flow.

<!-- empty.assets -->
The approved context records no assets. Findings below are stated against components rather than
against what those components hold.

<!-- empty.trust_boundaries -->
The approved context records no trust boundaries. The documentation provided did not establish
where trust changes in this system, which limits every conclusion that depends on exposure.

<!-- empty.threats -->
No threats were carried into this report. Either none survived validation against the approved
context, or none was significant enough to report on its own; the assessment's execution record
shows which.

<!-- empty.findings -->
No findings were approved in this assessment.

This is a defined outcome and not a failure. It means that no candidate weakness reached the bar
this assessment applies: each was unsupported by the evidence available, was recorded instead as a
documentation gap or an open question, or was rejected by the reviewer.

It is not a statement that the reviewed system is secure, and it is not a statement that no
weaknesses exist. It is a statement about what the material provided supports. Section 9 records
what could not be determined from that material, section 11 records what was asked and not
answered, and section 16 records the limits of this assessment.

<!-- empty.documentation_gaps -->
The assessment recorded no documentation gaps. Every requirement it applied could be evaluated
against the documentation provided. This is not a statement that the documentation is complete —
only that its silences did not block a conclusion the assessment tried to reach.

<!-- empty.assumptions -->
The assessment recorded no assumptions. Every claim in the approved context is documented in a
source document or was confirmed by the reviewer.

<!-- empty.open_questions -->
No questions remain open. Every question raised during the assessment was answered or dismissed
before the findings were approved.

<!-- empty.controls -->
No existing controls were confirmed. The documentation provided did not establish that any security
control is implemented.

This is a statement about the documentation and not about the system. A control that is in place
and undocumented is indistinguishable here from one that does not exist, which is what section 9
records rather than reporting as a weakness.

<!-- empty.recommended_actions -->
There are no recommended actions, because no findings were approved. Sections 9 and 11 list the
documentation and answers that would let a later assessment reach conclusions this one could not.

<!-- empty.evidence -->
No evidence references are cited above. Nothing in this report is traceable to a passage in a
source document, which section 16 records as a limitation.

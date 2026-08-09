#!/usr/bin/env bash
#
# Create the milestones, labels, and project that the issue backlog depends on.
#
# Run this once, before scripts/seed_backlog.py. Every command is idempotent enough to
# re-run: label creation uses --force, and milestone creation is skipped when the title
# already exists.
#
# The project step needs a token scope the default gh login does not include:
#
#     gh auth refresh -s project
#
# read:project is not sufficient. Projects v2 write requires `project`. A fine-grained
# personal access token cannot access user-owned projects at all, so use the gh OAuth flow.

set -euo pipefail

REPO="ethanpturner/trace"
PROJECT_TITLE="Trace pipeline"

echo "== milestones =="
create_milestone() {
  local title="$1" description="$2"
  if gh api "repos/${REPO}/milestones" --jq '.[].title' | grep -qxF "$title"; then
    echo "  exists: $title"
  else
    gh api --method POST "repos/${REPO}/milestones" \
      -f title="$title" -f state='open' -f description="$description" \
      --jq '"  created: \(.title) (#\(.number))"'
  fi
}

create_milestone "M0 Decisions" \
  "Open design decisions that implementation is blocked on. Each closes with an entry in docs/architecture/decision-log.md."
create_milestone "M1 Foundation" \
  "Trace knows documents and structured architecture. Foundations, Assessment object, evidence model, document loader."
create_milestone "M2 Context" \
  "Trace understands the architecture. Context objects, model runtime, context extraction, and the context approval checkpoint."
create_milestone "M3 Reasoning" \
  "Trace evaluates threats, requirements, and controls. Threat analysis through critical review."
create_milestone "M4 Results" \
  "Trace produces defensible findings and reports. Findings, the finding approval checkpoint, and report generation."

echo
echo "== labels =="
label() {
  gh label create "$1" --repo "$REPO" --color "$2" --description "$3" --force >/dev/null
  echo "  $1"
}

# Component axis. One shared colour so the axis reads as a unit.
label "comp:foundations"        BFD4F2 "Shared types, identifiers, persistence, artifact store"
label "comp:assessment"         BFD4F2 "Assessment object: the root state container"
label "comp:evidence"           BFD4F2 "Evidence model and citation linkage"
label "comp:doc-loader"         BFD4F2 "Document loader and untrusted-source ingestion"
label "comp:context-objects"    BFD4F2 "Context domain objects"
label "comp:context-extractor"  BFD4F2 "Context Extraction agent"
label "comp:context-review"     BFD4F2 "Context approval checkpoint (DEC-005)"
label "comp:runtime"            BFD4F2 "Model abstraction, prompt registry, orchestrator, execution ledger"
label "comp:threat-engine"      BFD4F2 "Threat Analysis agent"
label "comp:requirement-matcher" BFD4F2 "Deterministic requirement selection over the catalog"
label "comp:control-mapper"     BFD4F2 "Requirement and Control Mapping agent"
label "comp:evidence-validation" BFD4F2 "Evidence Validation agent"
label "comp:critic"             BFD4F2 "Critical Review agent"
label "comp:findings"           BFD4F2 "Findings, DocumentationGaps, and the finding checkpoint"
label "comp:report"             BFD4F2 "Report Generation agent and deterministic rendering"
label "comp:evaluation"         BFD4F2 "Benchmarks, expected outputs, and evaluation metrics"

# Type axis.
label "type:feature"  1D76DB "Builds behaviour that does not exist yet"
label "type:spike"    5319E7 "Time-boxed investigation with a written outcome"
label "type:decision" B60205 "Resolves an open question; lands an entry in the decision log"
label "type:test"     0E8A16 "Unit, integration, or evaluation coverage"
label "type:docs"     0075CA "Design corpus, README, or journal changes"
label "type:chore"    6A737D "Tooling, CI, dependencies, repository hygiene"

# Constraint flags. These exist because CLAUDE.md makes violating a binding constraint a
# decision-log event rather than an implementation detail.
label "design-change"  D93F0B "Touches a binding constraint; requires a decision-log entry"
label "needs-decision" FBCA04 "Blocked on an unresolved design decision"

echo
echo "== project =="
if ! gh project list --owner "@me" --format json >/dev/null 2>&1; then
  echo "  gh lacks the 'project' scope. Run: gh auth refresh -s project"
  echo "  Skipping project creation. Milestones and labels are done."
  exit 0
fi

if gh project list --owner "@me" --format json --jq '.projects[].title' | grep -qxF "$PROJECT_TITLE"; then
  echo "  exists: $PROJECT_TITLE"
else
  gh project create --owner "@me" --title "$PROJECT_TITLE" --format json \
    --jq '"  created: \(.title) at \(.url)"'
fi

NUMBER=$(gh project list --owner "@me" --format json \
  --jq ".projects[] | select(.title==\"${PROJECT_TITLE}\") | .number")
gh project link "$NUMBER" --owner "@me" --repo "$(basename "$REPO")" >/dev/null 2>&1 \
  && echo "  linked to $REPO" || echo "  already linked, or link failed"

echo
echo "Done. Next:"
echo "  uv run python scripts/seed_backlog.py --check"
echo "  uv run python scripts/seed_backlog.py"
echo "  uv run python scripts/seed_backlog.py --apply --project \"$PROJECT_TITLE\""
echo
echo "Board grouping, slicing, and the auto-add workflow have no API path."
echo "Configure those in the web UI once the issues exist."

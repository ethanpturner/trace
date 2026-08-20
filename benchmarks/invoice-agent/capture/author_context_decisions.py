"""Author decisions-context.yaml from review-export.yaml for the invoice-agent capture.

Reviewer reasoning, recorded here and in provenance.md: every extracted object and claim was
checked against input/agent-overview.md and approved unchanged, with one edit — df-002
(agent to hosted model provider) is a flow to a third-party hosted endpoint crossing tb-001,
so internet_exposed is corrected to true, the crypto-wallet precedent. The observability
flow's deployment is not documented and stays unknown. The three blocking questions are
answered without inventing facts.
"""

from pathlib import Path

import yaml

HERE = Path(__file__).parent

doc = yaml.safe_load((HERE / "review-export.yaml").read_text(encoding="utf-8"))

doc["reviewer"] = "recorded-reviewer"

for section in ("components", "actors", "assets", "data_flows", "trust_boundaries", "claims"):
    for entry in doc.get(section, []):
        entry["decision"] = "approve"

for flow in doc["data_flows"]:
    if flow["id"] == "df-002":
        flow["editable"]["internet_exposed"] = True

ANSWERS = {
    "qst-001": (
        "Not documented. Whether submitted invoice files persist after processing, and in "
        "which system, is undetermined; treat persistence and retention as a documentation "
        "gap, not as evidence in either direction."
    ),
    "qst-002": (
        "The document states the submitter field is a value in the uploaded invoice document "
        "and submitters are not otherwise authenticated to the workflow. Whether any upstream "
        "system authenticates submitters before submission is not documented and remains "
        "undetermined; analysis should treat submitter identity at this workflow's boundary "
        "as unverified."
    ),
    "qst-003": (
        "Not documented. The observability service's identity, retention, and access controls "
        "are undetermined. The documented fact is only that captured traces include full HTTP "
        "request and response bodies."
    ),
}
for question in doc["questions"]:
    if question["id"] in ANSWERS:
        question["answer"] = ANSWERS[question["id"]]

(HERE / "decisions-context.yaml").write_text(
    yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
)

total = sum(
    len(doc.get(s, []))
    for s in ("components", "actors", "assets", "data_flows", "trust_boundaries", "claims")
)
print(f"written; {total} decisions, 3 blocking answers, 1 edit (df-002 internet_exposed)")

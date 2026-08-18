"""The Kubernetes parser (#594): the IaC family's last named member, the rules held again.

The load-bearing assertions: only kinds on the allowlist yield anything; pod-level and
uniform container-level booleans become documented claims in either direction; a split
container statement yields nothing (not one self-contained fact — DEC-121's bar applied to
aggregation); a multi-document stream ingests and each object's excerpt quotes its own
document's lines; and the DEC-122 suppression shape holds at fixture level — a manifest
stating a control the prose omits puts the documented claim on the record.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from trace_ai.domain.component import Component
from trace_ai.domain.context_claim import ContextClaim
from trace_ai.domain.enums import ObjectStatus, SourceOrigin
from trace_ai.domain.evidence import EvidenceReference
from trace_ai.domain.source_document import MediaType
from trace_ai.services.context.kubernetes import parse_kubernetes
from trace_ai.services.context.parsers import seed_structured_documents

if TYPE_CHECKING:
    from pathlib import Path

MANIFEST = """\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: billing-worker
spec:
  template:
    spec:
      hostNetwork: false
      automountServiceAccountToken: false
      containers:
      - name: worker
        image: billing-worker:1
        securityContext:
          readOnlyRootFilesystem: true
          allowPrivilegeEscalation: false
      - name: sidecar
        image: log-shipper:2
        securityContext:
          readOnlyRootFilesystem: true
---
apiVersion: v1
kind: Service
metadata:
  name: billing-worker-svc
spec:
  selector:
    app: billing-worker
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: billing-config
data:
  mode: reconcile
"""


def test_parse_reads_the_allowlist_and_only_the_allowlist() -> None:
    parsed = parse_kubernetes(MANIFEST, media_type=MediaType.YAML)
    by_name = {obj.name: obj for obj in parsed.objects}
    # The ConfigMap is off the allowlist and yields nothing.
    assert set(by_name) == {"billing-worker", "billing-worker-svc"}
    assert by_name["billing-worker"].kind == "Deployment"
    assert dict(by_name["billing-worker"].stated) == {
        "hostNetwork": False,
        "automountServiceAccountToken": False,
        "readOnlyRootFilesystem": True,
        "allowPrivilegeEscalation": False,
    }
    assert by_name["billing-worker-svc"].stated == ()


def test_a_split_container_statement_yields_nothing() -> None:
    """Two containers stating opposite values have not stated one self-contained fact about
    the workload; the split yields silence, never a chosen side (DEC-128)."""
    parsed = parse_kubernetes(
        """\
kind: Deployment
metadata:
  name: mixed
spec:
  template:
    spec:
      containers:
      - name: a
        securityContext:
          readOnlyRootFilesystem: true
      - name: b
        securityContext:
          readOnlyRootFilesystem: false
""",
        media_type=MediaType.YAML,
    )
    (workload,) = parsed.objects
    assert workload.stated == ()


def test_a_stream_with_no_kind_is_refused() -> None:
    with pytest.raises(ValueError, match="kind"):
        parse_kubernetes("mode: reconcile\n", media_type=MediaType.YAML)


def test_seeding_enters_the_proposal_path_with_per_document_excerpts(tmp_path: Path) -> None:
    from trace_ai.domain.assessment import default_configuration
    from trace_ai.domain.hashing import content_hash
    from trace_ai.domain.source_document import TrustLevel
    from trace_ai.infrastructure.database.store import AssessmentStore
    from trace_ai.services.assessment import AssessmentService
    from trace_ai.services.ingestion.loader import DocumentLoader

    manifest = tmp_path / "billing.k8s.yaml"
    manifest.write_text(MANIFEST, encoding="utf-8")

    with AssessmentStore.at_root(tmp_path / "data") as store:
        service = AssessmentService(store, artifact_root=tmp_path / "data")
        created = service.create(
            "Declared", default_configuration("offline-fake", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        DocumentLoader(handle).load_document(
            manifest,
            origin=SourceOrigin.UPLOADED_DOCUMENT,
            trust_level=TrustLevel.UNTRUSTED,
        )

        seeded = seed_structured_documents(handle)
        assert seeded is not None
        by_name = {component.name: component for component in seeded.components}
        assert set(by_name) == {"billing worker", "billing worker svc"}
        workload = by_name["billing worker"]
        assert workload.component_type == "workload"
        assert workload.status is ObjectStatus.CANDIDATE
        assert workload.source_origin is SourceOrigin.STRUCTURED_INPUT
        assert by_name["billing worker svc"].component_type == "service"

        claims = {claim.predicate: claim for claim in handle.objects.list(ContextClaim)}
        assert set(claims) == {
            "hostNetwork",
            "automountServiceAccountToken",
            "readOnlyRootFilesystem",
            "allowPrivilegeEscalation",
        }
        # The DEC-122 suppression shape, at fixture level: the manifest states the control the
        # prose omits, and the documented claim is on the record for checkpoint 1 — the ground
        # a generic "no filesystem protections" false positive dies on.
        assert claims["readOnlyRootFilesystem"].value is True
        assert claims["hostNetwork"].value is False, "a stated false is documented"
        assert claims["readOnlyRootFilesystem"].subject_id == workload.id

        (cited,) = claims["readOnlyRootFilesystem"].evidence_ids
        reference = handle.objects.get(EvidenceReference, cited)
        assert "readOnlyRootFilesystem: true" in reference.quoted_text
        assert "billing-worker-svc" not in reference.quoted_text, "its own document's lines"
        assert reference.section_title == "Deployment.billing-worker"
        assert reference.content_hash == content_hash(reference.quoted_text.encode("utf-8"))

        # Family idempotence, checked once for the whole family (DEC-038).
        again = seed_structured_documents(handle)
        assert again is not None
        assert len(handle.objects.list(Component)) == 2


def test_a_multi_document_stream_passes_the_loader_boundary(tmp_path: Path) -> None:
    """DEC-128's loader change: a `---`-separated stream is valid YAML with the same safety
    properties, validated document by document; an unaddressable member still refuses."""
    from trace_ai.domain.assessment import default_configuration
    from trace_ai.domain.source_document import TrustLevel
    from trace_ai.infrastructure.database.store import AssessmentStore
    from trace_ai.services.assessment import AssessmentService
    from trace_ai.services.ingestion.loader import DocumentLoader, UnaddressableDocumentError

    scalar_stream = tmp_path / "scalar.yaml"
    scalar_stream.write_text("--- 3\n--- 4\n", encoding="utf-8")

    with AssessmentStore.at_root(tmp_path / "data") as store:
        service = AssessmentService(store, artifact_root=tmp_path / "data")
        created = service.create(
            "Streams", default_configuration("offline-fake", "stride-scenario-based")
        )
        handle = service.handle(created.id)
        loader = DocumentLoader(handle)
        with pytest.raises(UnaddressableDocumentError):
            loader.load_document(
                scalar_stream,
                origin=SourceOrigin.UPLOADED_DOCUMENT,
                trust_level=TrustLevel.UNTRUSTED,
            )

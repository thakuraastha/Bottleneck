from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from uuid import uuid4

from pydantic import BaseModel, Field

from app.models.domain import EvidenceItem, EvidenceType
from app.models.investigations import InvestigationOutput


class AggregationResult(BaseModel):
    evidence: list[EvidenceItem]
    missing_mandatory_fields: list[str] = Field(default_factory=list)
    unresolved_conflicts: list[str] = Field(default_factory=list)


class EvidenceAggregator:
    """Deterministically converts validated specialist outputs into provenance records."""

    def aggregate(
        self,
        *,
        incident_id: str,
        outputs: Iterable[InvestigationOutput],
        mandatory_fields: set[str],
    ) -> AggregationResult:
        evidence: list[EvidenceItem] = []
        seen: set[tuple[str, str, str, str]] = set()
        values_by_field: dict[str, set[str]] = {}
        conflicts: list[str] = []
        for output in outputs:
            conflicts.extend(output.conflicts)
            for evidence_type, facts in (
                (EvidenceType.VERIFIED_FACT, output.verified_facts),
                (EvidenceType.CALCULATED_FACT, output.calculated_facts),
            ):
                for fact in facts:
                    key = (evidence_type.value, fact.field, repr(fact.value), fact.source.source_record_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    values_by_field.setdefault(fact.field, set()).add(repr(fact.value))
                    evidence.append(EvidenceItem(
                        evidence_id=str(uuid4()), incident_id=incident_id, evidence_type=evidence_type,
                        field=fact.field, value=fact.value, unit=fact.unit,
                        source_system=fact.source.source_system,
                        source_record_id=fact.source.source_record_id,
                        observed_at=datetime.now(timezone.utc),
                    ))
        for field, distinct_values in values_by_field.items():
            if len(distinct_values) > 1:
                conflicts.append(f"contradictory values for {field}: {sorted(distinct_values)}")
        present_fields = set(values_by_field)
        return AggregationResult(
            evidence=evidence,
            missing_mandatory_fields=sorted(mandatory_fields - present_fields),
            unresolved_conflicts=sorted(set(conflicts)),
        )


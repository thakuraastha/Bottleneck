from app.models.investigations import InvestigationFact, InvestigationOutput, SourceReference
from app.services import EvidenceAggregator


def fact(field: str, value: object, record: str) -> InvestigationFact:
    return InvestigationFact(
        field=field,
        value=value,
        unit="units",
        source=SourceReference(source_system="synthetic_csv", source_record_id=record, fields=[field]),
    )


def test_aggregation_deduplicates_and_detects_missing_and_conflicting_facts() -> None:
    first = InvestigationOutput(
        summary="first",
        verified_facts=[fact("available_quantity", 600, "WH-1"), fact("supplier_status", "ACTIVE", "SUP-A")],
    )
    second = InvestigationOutput(
        summary="second",
        verified_facts=[fact("available_quantity", 600, "WH-1"), fact("supplier_status", "QUALITY_HOLD", "SUP-B")],
    )
    result = EvidenceAggregator().aggregate(
        incident_id="INC-1",
        outputs=[first, second],
        mandatory_fields={"available_quantity", "supplier_status", "revised_eta"},
    )
    assert len(result.evidence) == 3
    assert result.missing_mandatory_fields == ["revised_eta"]
    assert any("supplier_status" in conflict for conflict in result.unresolved_conflicts)


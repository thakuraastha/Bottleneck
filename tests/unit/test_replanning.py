from app.orchestration import BoundedReplanner


def test_replanning_stops_after_pass() -> None:
    result = BoundedReplanner[int](maximum_revisions=2).run(
        0,
        reflect=lambda plan, revision: (plan >= 1, [] if plan >= 1 else ["too low"], ["increase"]),
        revise=lambda plan, guidance, revision: plan + 1,
    )
    assert result.passed is True
    assert result.plan == 1
    assert result.attempts == 1
    assert result.exhausted is False


def test_replanning_exhaustion_is_bounded() -> None:
    revisions: list[int] = []
    result = BoundedReplanner[str](maximum_revisions=2).run(
        "plan",
        reflect=lambda plan, revision: (False, ["still invalid"], ["fix constraints"]),
        revise=lambda plan, guidance, revision: revisions.append(revision) or plan,
    )
    assert revisions == [1, 2]
    assert result.passed is False
    assert result.exhausted is True
    assert result.attempts == 2


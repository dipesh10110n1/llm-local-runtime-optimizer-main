from optimizer.live_comparator import parse_judgement


def test_parses_local_judge_choice_only_when_valid():
    assert parse_judgement("2", 2) == 1
    assert parse_judgement("WINNER: 1", 2) == 0
    assert parse_judgement("WINNER: 3", 2) is None
    assert parse_judgement("WINNER: TIE", 2) is None
    assert parse_judgement("I cannot choose", 2) is None

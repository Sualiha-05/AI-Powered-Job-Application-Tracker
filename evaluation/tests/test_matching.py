from evalkit.matching import alias_matches, map_to_gold
from evalkit.schema import GoldRequirement

G = [
    GoldRequirement("pg", "PostgreSQL", ["postgres"]),
    GoldRequirement("rest", "REST API design", ["rest", "api"]),
    GoldRequirement("k8s", "Kubernetes", ["kubernetes", "k8s"], "preferred"),
]


def test_aliases_match_at_the_start_of_a_word_only():
    assert alias_matches("postgres", "PostgreSQL") and alias_matches("api", "REST APIs")
    assert not alias_matches("api", "FastAPI") and not alias_matches("sql", "MySQL")
    assert alias_matches("K8S", "running k8s clusters")


def test_covered_predicted_and_evidence():
    out = map_to_gold(G, [
        {"requirement": "PostgreSQL", "supported": True, "evidence": [{"line": "x", "line_number": 5}]},
        {"requirement": "Backend API development", "supported": False, "evidence": []},
    ])
    pg, rest, k8s = out
    assert (pg.covered, pg.predicted, pg.evidence_lines) == (True, True, {5})
    assert (rest.covered, rest.predicted) == (True, False)          # produced, but marked not supported
    assert (k8s.covered, k8s.predicted) == (False, False)           # never mentioned: counts as not supported


def test_supported_wins_when_several_requirements_match():
    out = map_to_gold(G[:1], [{"requirement": "Postgres basics", "supported": False}, {"requirement": "PostgreSQL tuning", "supported": True, "evidence": []}])
    assert out[0].predicted is True and len(out[0].matched_labels) == 2

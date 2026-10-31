"""Maps a matcher's own requirement list onto the gold requirements.

Each matcher invents its own requirements ("Experience with Selenium", "Backend API development", "Docker"), so they
cannot be compared line by line. Instead, for every GOLD requirement we ask: did the matcher produce a requirement whose
label contains one of the gold requirement's aliases (matched at the start of a word, case-insensitive), and did it mark
that requirement supported? Aliases are chosen by the person labeling, in labels.json.

  covered    the matcher produced at least one requirement matching the gold requirement
  predicted  at least one matching requirement was marked supported (an uncovered requirement counts as not supported)
"""
import re
from dataclasses import dataclass, field

from .schema import GoldRequirement


def alias_matches(alias: str, text: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(alias.lower()), text.lower()) is not None


@dataclass
class Decision:
    gold_id: str
    covered: bool
    predicted: bool
    evidence_lines: set[int] = field(default_factory=set)
    matched_labels: list[str] = field(default_factory=list)


def map_to_gold(gold: list[GoldRequirement], matcher_requirements: list[dict]) -> list[Decision]:
    out = []
    for g in gold:
        matched = [r for r in matcher_requirements if any(alias_matches(a, r.get("requirement", "")) for a in g.aliases)]
        supported = [r for r in matched if r.get("supported")]
        out.append(
            Decision(
                gold_id=g.id,
                covered=bool(matched),
                predicted=bool(supported),
                evidence_lines={e["line_number"] for r in supported for e in r.get("evidence", [])},
                matched_labels=[r["requirement"] for r in matched],
            )
        )
    return out

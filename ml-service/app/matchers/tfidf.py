"""TF-IDF term-overlap matcher: free, deterministic, no external services, no heavy dependencies.

How it works
  1. The job description is split into requirement units (list items, comma/"and" separated parts, sentences),
     using section headings such as "Requirements" / "Nice to have" / "Benefits" to decide what counts and how
     important it is. This is a heuristic, not a parser: unusual layouts can produce odd units.
  2. Every unit and every resume line becomes a set of normalised terms (lower case, stop words removed,
     light suffix stemming, aliases from the skill vocabulary such as "ReactJS" -> "react").
  3. Each term gets an IDF weight, computed over ALL resume lines and requirement units as "documents":
     terms that appear in many lines (built, using, api) weigh little; rare terms (selenium, terraform) weigh a lot.
  4. A unit is supported by a resume line when that line contains at least THRESHOLD (default 60%) of the unit's
     total IDF weight. The best lines (up to 3) are returned as evidence. The score is the fraction of units supported,
     exactly like the other matchers, so results are comparable.

Two small rules go beyond plain TF-IDF, both aimed at obvious false results:
  * Lead-in phrases such as "we need someone with", "you will", "experience with" are stripped from requirements,
    because they would otherwise dilute the weight of the real skill.
  * Resume lines that only express interest ("curious about", "want to learn", ...) are never used as evidence.

What it is good at: skills that are not in the keyword matcher's fixed list (Selenium, Figma, Terraform...).
What it cannot do: understand synonyms. "REST services" does not support "API design" unless they share terms.
"""
import math
import os
import re
from collections import Counter
from dataclasses import dataclass

from ..extract import extract_skills
from ..schemas import Evidence, MatchResponse, RequirementResult
from ..skills import SKILLS
from .common import numbered_lines

MAX_UNITS = 25
MAX_EVIDENCE = 3
MAX_LABEL_CHARS = 80
SHORT_UNIT_TOKENS = 5
DEFAULT_THRESHOLD = 0.6

STOPWORDS = frozenset(
    """a an the and or of to in for on with at by from as is are be been being it its this that these those
    you your we our us they their he she i will would can could should may might must shall do does did have has had
    etc also well such using use used including include includes ideal candidate looking role team company
    experience experienced years year strong knowledge ability able skills skill proficiency proficient familiarity
    familiar working work required preferred plus nice good excellent understanding solid proven demonstrated
    more than least minimum bonus great within across other any all each both into over about
    need needs needed someone anyone seeking join looking""".split()
)

# single-token aliases from the skill vocabulary -> canonical single token ("reactjs" -> "react", "js" -> "javascript")
_SYNONYMS = {
    alias: name.lower()
    for name, aliases in SKILLS.items()
    if " " not in name
    for alias in aliases
    if " " not in alias and alias != name.lower()
}

_IRREGULAR = {"built": "build", "led": "lead", "wrote": "write", "written": "write", "ran": "run", "made": "make", "drove": "drive"}

_LEAD_INS = [
    re.compile(r"^(we|you|they)\s+(are\s+|will\s+|'ll\s+|must\s+|should\s+)?(need|needs|looking for|seeking|want|require|have|bring|will|must|should)\b\s*"),
    re.compile(r"^(must|should|will) (have|need)\s+"),
    re.compile(r"^(responsible for|ability to|able to)\s+"),
    re.compile(r"^(someone|a candidate|an? [a-z]+)\s+(with|who (has|knows|can))\s+"),
    re.compile(r"^(experience|knowledge|familiarity|proficiency|expertise|understanding)\s+(with|in|of|using)\s+"),
    re.compile(r"^(strong|solid|good|proven|hands-on|deep|working)\s+"),
]

# A resume line saying the person is only interested in or wants to learn something is not evidence of experience.
_ASPIRATION_RE = re.compile(
    r"\b(curious about|interested in|eager to learn|keen to learn|wants? to learn|wish(es)? to learn|"
    r"plans? to learn|looking to learn|hope to learn|currently learning|exploring)\b"
)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#./\-]*")
_NUMBER_RE = re.compile(r"^\d+\+?$")
_BULLET_RE = re.compile(r"^\s*(?:[-*•–—▪●·]|\d+[.)])\s+")
_CUE_RE = re.compile(r"\b(experience|proficien\w+|knowledge|familiar\w*|understanding|skills?|ability|degree|years?|expertise|must|required|hands-on)\b")
_PREFERRED_CUE_RE = re.compile(r"\b(nice to have|bonus|a plus|is plus|plus|preferred|desirable|good to have)\b")

_SKIP_HEADING = re.compile(
    r"(about (us|the company|the team|our company)|who we are|our (mission|story|values|culture)|benefits( and perks)?|perks|"
    r"what we offer|why (join us|us|work with us)|compensation( and benefits)?|salary|equal opportunity( employer)?|"
    r"how to apply|company overview|overview|location)"
)
_PREFERRED_HEADING = re.compile(
    r"((nice|good)[- ]to[- ]haves?( skills)?|bonus( points)?|a plus|pluses|preferred( qualifications| skills)?|desirable|would be great)"
)
_REQUIRED_HEADING = re.compile(
    r"((key |minimum |basic |required |technical |core )?(requirements?|qualifications?|skills?( and (experience|qualifications))?)|"
    r"(key )?responsibilities|what you'?ll (need|do|bring)|what we'?re looking for|about you|who you are|you have|you bring|"
    r"your (profile|skills|background)|must[- ]haves?|the role|your role|in this role)"
)


def _stem(t: str) -> str:
    """Very light stemmer; only needs to be consistent, because both sides are stemmed the same way."""
    if len(t) <= 3 or not t.isalpha():
        return t
    if t.endswith("ies") and len(t) > 4:
        return t[:-3] + "y"
    if t.endswith("sses"):
        return t[:-2]
    for suffix in ("ing", "ed"):
        if t.endswith(suffix) and len(t) - len(suffix) >= 4:
            return t[: -len(suffix)]
    if t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def _normalise(raw: str) -> str | None:
    raw = raw.rstrip(".-/")
    t = _IRREGULAR.get(raw) or _SYNONYMS.get(raw, raw)
    if not t or t in STOPWORDS or _NUMBER_RE.match(t):
        return None
    t = _stem(t)
    return None if t in STOPWORDS else t


def tokens(text: str) -> list[str]:
    return [t for raw in _TOKEN_RE.findall(text.lower().replace("’", "'")) if (t := _normalise(raw))]


def _strip_lead_ins(text: str) -> str:
    lower = text.lower().replace("’", "'").strip()
    for _ in range(4):
        before = lower
        for pattern in _LEAD_INS:
            lower = pattern.sub("", lower).strip()
        if lower == before:
            break
    return lower or text.lower()


def _surface(label: str) -> dict[str, str]:
    """stem -> a readable word from the requirement text, so notes say "kubernetes", not "kubernete"."""
    out: dict[str, str] = {}
    for raw in _TOKEN_RE.findall(label.lower().replace("’", "'")):
        if (t := _normalise(raw)) and t not in out:
            out[t] = raw.rstrip(".-/")
    return out


def _heading_kind(text: str) -> str | None:
    norm = re.sub(r"\s+", " ", re.sub(r"[^a-z' \-]", "", text.lower().replace("’", "'"))).strip()
    if not norm:
        return None
    if _SKIP_HEADING.fullmatch(norm):
        return "skip"
    if _PREFERRED_HEADING.fullmatch(norm):
        return "preferred"
    if _REQUIRED_HEADING.fullmatch(norm):
        return "required"
    return None


@dataclass(frozen=True)
class Unit:
    label: str
    importance: str  # "required" | "preferred"
    terms: frozenset[str]
    surface: tuple[tuple[str, str], ...] = ()


def requirement_units(job_description: str) -> list[Unit]:
    raw = []  # (label, terms, importance, section, has_skill, cue, listy)
    section: str | None = None
    saw_heading = False

    for line in job_description.splitlines():
        if not line.strip():
            continue
        bullet = bool(_BULLET_RE.match(line))
        body = _BULLET_RE.sub("", line).strip()

        for sentence in re.split(r"(?<=[.!?])\s+", body):
            sentence = sentence.strip()
            if not sentence:
                continue
            m = re.match(r"^([^:]{2,60}):\s*(.*)$", sentence)
            if m and _heading_kind(m.group(1)):
                section, saw_heading, sentence = _heading_kind(m.group(1)), True, m.group(2).strip()
                if not sentence:
                    continue
            elif not bullet and len(sentence.split()) <= 6 and not re.search(r"[.!?]$", sentence) and _heading_kind(sentence):
                section, saw_heading = _heading_kind(sentence), True
                continue
            if section == "skip":
                continue

            parts = [p.strip(" .;:") for p in re.split(r"[;,|]|\s+(?:and|or|&)\s+", sentence) if p.strip(" .;:")]
            for part in parts:
                terms = frozenset(tokens(_strip_lead_ins(part)))
                if not terms:
                    continue
                lower = part.lower()
                importance = "preferred" if (section == "preferred" or _PREFERRED_CUE_RE.search(lower)) else "required"
                label = re.sub(r"\s+", " ", part).strip(" -•*.;:")[:MAX_LABEL_CHARS]
                raw.append((label, terms, importance, section, bool(extract_skills(part)), bool(_CUE_RE.search(lower)), bullet or (len(parts) >= 2 and all(len(p.split()) <= 4 for p in parts))))

    units: list[Unit] = []
    seen: set[frozenset[str]] = set()
    for label, terms, importance, sec, has_skill, cue, listy in raw:
        if saw_heading:
            keep = sec is not None and (has_skill or cue or len(terms) <= SHORT_UNIT_TOKENS)  # text before any heading is intro
        else:
            keep = has_skill or cue or (listy and len(terms) <= SHORT_UNIT_TOKENS)
        if keep and terms not in seen:
            seen.add(terms)
            units.append(Unit(label, importance, terms, tuple(_surface(_strip_lead_ins(label)).items())))
        if len(units) >= MAX_UNITS:
            break
    return units


def _idf(documents: list[frozenset[str]]) -> dict[str, float]:
    n = len(documents)
    df = Counter(t for d in documents for t in d)
    return {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}


def document_similarity(resume_text: str, job_description: str) -> float:
    """Classic TF-IDF cosine between the whole resume and the whole job description (reported, not used for the score)."""
    lines = [ln for ln in (resume_text + "\n" + job_description).splitlines() if ln.strip()]
    idf = _idf([frozenset(tokens(ln)) for ln in lines])

    def vector(text: str) -> dict[str, float]:
        tf = Counter(tokens(text))
        return {t: c * idf.get(t, 1.0) for t, c in tf.items()}

    a, b = vector(resume_text), vector(job_description)
    dot = sum(w * b[t] for t, w in a.items() if t in b)
    norm = math.sqrt(sum(w * w for w in a.values())) * math.sqrt(sum(w * w for w in b.values()))
    return round(dot / norm, 3) if norm else 0.0


def _threshold() -> float:
    try:
        return min(1.0, max(0.05, float(os.getenv("TFIDF_THRESHOLD", DEFAULT_THRESHOLD))))
    except ValueError:
        return DEFAULT_THRESHOLD


def match(resume_text: str, job_description: str) -> MatchResponse:
    threshold = _threshold()
    lines = numbered_lines(resume_text)
    line_terms = {n: frozenset() if _ASPIRATION_RE.search(text.lower()) else frozenset(tokens(text)) for n, text in lines.items()}
    units = requirement_units(job_description)

    idf = _idf([t for t in line_terms.values() if t] + [u.terms for u in units])

    results: list[RequirementResult] = []
    for unit in units:
        total = sum(idf[t] for t in unit.terms)
        scored = []
        for n, terms in line_terms.items():
            common = unit.terms & terms
            if common:
                scored.append((sum(idf[t] for t in common) / total, n, common))
        scored.sort(key=lambda s: (-s[0], s[1]))
        best = [s for s in scored if s[0] >= threshold][:MAX_EVIDENCE]

        names = dict(unit.surface)
        if best:
            matched = ", ".join(sorted(names.get(t, t) for t in best[0][2]))
            note = f"matched {matched} ({round(best[0][0] * 100)}% of the requirement's weight)"
        elif scored:
            note = f"closest line covers {round(scored[0][0] * 100)}%, needs {round(threshold * 100)}%"
        else:
            note = "no shared terms"
        results.append(
            RequirementResult(
                requirement=unit.label,
                supported=bool(best),
                evidence=[Evidence(line=lines[n], line_number=n) for _, n, _ in best],
                importance=unit.importance,
                note=note,
            )
        )

    return MatchResponse(
        matcher="tfidf-overlap",
        score=round(sum(r.supported for r in results) / len(results), 3) if results else 0.0,
        requirements=results,
        missing=[r.requirement for r in results if not r.supported],
        doc_similarity=document_similarity(resume_text, job_description),
    )

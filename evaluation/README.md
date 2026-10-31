# Evaluation: how well do the matchers agree with a human?

This folder measures the three matchers (keyword, TF-IDF, AI) against labels **you** write, and runs a name-swap bias audit.
Nothing here needs a running server: the scripts import the ML service's matchers directly.

> `data/example/` is a tiny **synthetic** dataset (made-up people, postings written to show the tools). Use it to try the
> commands. Numbers computed on it prove nothing; build your own dataset for any claim.

## The 6 steps

1. **Collect** about 10 real job postings for roles you want, and write 4 to 5 resume versions (see "Resume variants").
2. **Register and label** them with `label.py` (below). Do this *before* running any matcher.
3. **Freeze**: commit `labels.json`. The report prints a fingerprint of it; if you edit labels later the fingerprint changes.
4. **Tune on `dev`**, choose the TF-IDF threshold: `run_eval.py --split dev --tfidf-thresholds 0.4,0.5,0.6,0.7`.
5. **Report `test` once**, with the chosen threshold: `run_eval.py --split test --tfidf-thresholds 0.5 --llm`.
6. **Bias audit**: `bias_audit.py --data ... [--llm]`, then write up what you found, including limits.

## Setup (PowerShell, from the repository root)

```powershell
cd ml-service
python -m venv .venv                   # skip if you already have one
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
cd ..
python evaluation\label.py --data evaluation\data\mine init
```

Then copy files in: job descriptions to `evaluation\data\mine\postings\<id>.txt`, resumes to
`evaluation\data\mine\resumes\<id>.txt`. **The first line of every resume must be a made-up name** (the bias audit replaces it).

## Labeling

```powershell
python evaluation\label.py --data evaluation\data\mine sync                       # registers new files, assigns dev/test
python evaluation\label.py --data evaluation\data\mine requirements backend-api   # type the gold requirements
python evaluation\label.py --data evaluation\data\mine tags strong-backend strong # tags drive the "F1 by resume type" table
python evaluation\label.py --data evaluation\data\mine pairs backend-api          # label every resume for that posting
python evaluation\label.py --data evaluation\data\mine status                     # what is left
python evaluation\label.py --data evaluation\data\mine check                      # validate before scoring
```

**Requirements** are typed one per line as `Label | alias, alias | required or preferred`. The **aliases** are how the scorer
connects a matcher's own wording to your requirement: a matcher's requirement counts as "the same" if its text contains one of
your aliases at the start of a word (case-insensitive). Example: `REST API design | rest, api`. Choose aliases that any sensible
wording would contain, and keep them specific enough not to catch other requirements (`api` matches "REST APIs" but not "FastAPI").

**Guideline for "supported"**: answer yes only if some resume line says the candidate **has used or does** it. A skill in a skills
list counts. The same capability in different words counts. Do **not** count: wanting or learning it ("curious about", "currently
learning"), coursework or tutorials only, a different tool (Docker is not Kubernetes), or no mention at all. Optionally give the
line number(s) that show it; the report then also checks whether a matcher cited a line you agree with.

**Blind labeling**: the labeling tools never run a matcher, and you must not look at matcher output while labeling. Otherwise
the evaluation only measures how much you were influenced by the matchers.

### Resume variants worth writing (all made-up people)

A strong match; a weak match; the right skills described in **different words** (synonyms); skills mentioned only as
"curious about / currently learning"; a bare skills list with no experience lines. Tag each one. Real resumes of other people are not
needed, and should not be sent to an AI provider.

### How big?

Roughly 10 postings × 4 resumes = 40 pairs and ~250 requirement decisions. Labeling that is a few hours (my estimate). With this
few labels the intervals are wide: that is a finding, not a flaw. Say so in the write-up.

## Running the scores

```powershell
python evaluation\run_eval.py --data evaluation\data\mine --split dev --tfidf-thresholds 0.4,0.5,0.6,0.7
python evaluation\run_eval.py --data evaluation\data\mine --split test --tfidf-thresholds 0.5
python evaluation\run_eval.py --data evaluation\data\mine --split test --tfidf-thresholds 0.5 --llm --llm-runs 3
```

Reports are written to `evaluation\results\` as Markdown (to read) and JSON (full details, every disagreement).

* **`--llm`** needs `GEMINI_API_KEY` (or `ANTHROPIC_API_KEY`) in your environment, asks for confirmation, and sends the texts to the provider.
  Use only your own or made-up resumes. On Gemini's free tier Google may use what you send to improve its products.
* **Quota**: the app's per-user and daily limits do not apply here; only your provider's quota does. A run stops after 3 failures in a row,
  and every finished AI answer is cached in `results\cache\`, so running the same command again later continues where it stopped.
  Start with `--llm-runs 1` to see how many calls you can afford.
* The AI matcher gives slightly different answers each time, so use `--llm-runs 3` and report the spread (the report does).
* Keyword and TF-IDF are recomputed every time (never cached), so a code change always shows up.

### Reading the report

| Section | Meaning |
|---|---|
| Coverage | Share of your gold requirements for which the matcher produced any matching requirement. A matcher that never mentions a requirement is treated as saying "not supported". |
| Precision / recall / F1 | "Supported" is the positive class. Precision: of what it called supported, how much you agree. Recall: of what you labeled supported, how much it found. |
| F1 95% interval | Resamples the labeled pairs 1,000 times. If two matchers' intervals overlap, do not claim one is better. |
| Ranking (Spearman) | Does a higher matcher score go with a larger share of your labeled requirements? Needs at least 3 resumes per posting to be defined; otherwise it shows n/a. |
| F1 by resume type | Where each matcher fails (synonyms, aspiration lines, ...) from your tags. Usually the most interesting table. |
| Evidence lines | Whether the lines a matcher cites include one you marked. |

## Bias audit

```powershell
python evaluation\bias_audit.py --data evaluation\data\mine --max-pairs 8 --names-per-group 3
python evaluation\bias_audit.py --data evaluation\data\mine --max-pairs 8 --names-per-group 3 --llm
```

Only the first line (the name) changes. The audit also runs the *same* resume twice with the *same* name: that is the noise baseline.
Flips beyond it are attributable to the name. For keyword and TF-IDF it is a sanity check (they should not react to names; TF-IDF can shift
slightly because a name changes word statistics); the AI matcher is the one that matters.

`data\names.json` is an **illustrative** list written for this project, not copied from a published list. For a claim you intend to
publish, use a validated list from the literature (for example the names used by Wilson and Caliskan, 2024), more names and more resumes.
A small audit that finds nothing does not show the absence of bias.

## Limits you must state in a write-up

* One labeler, a small sample, and resumes you wrote yourself: results describe *your* data, not hiring in general.
* The requirement-to-alias mapping is a choice you made; different aliases give different scores.
* The TF-IDF requirement splitting is a heuristic, and its threshold is tuned on `dev` only.
* The AI matcher's answers vary between runs and between model versions; report the model name and date.

## Layout

```
evaluation/
  data/example/        synthetic example dataset (labels.json, postings/, resumes/)
  data/names.json      illustrative name lists for the bias audit
  evalkit/             the library (schema, matching, metrics, runner, report, bias, labeling)
  label.py run_eval.py bias_audit.py   the commands
  results/             reports (results/cache/ is git-ignored)
  tests/               pytest -q   (run from this folder)
```

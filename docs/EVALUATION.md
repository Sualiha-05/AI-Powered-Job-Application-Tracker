# Evaluation of the three matchers

> **Status:** reviewed draft. Items marked `[CHECK]` still need your confirmation. Delete this note when none are left.

## Summary

* On a small, partly synthetic set, the keyword, TF-IDF and AI matchers could **not be ranked**: their differences are within sampling noise.
* They fail in different ways. Keyword misses skills outside its list and counts "currently learning" as experience; TF-IDF is precise but misses reworded requirements; the AI finds more but is slightly less precise.
* The AI matcher was stable across repeats (98% identical decisions) and never cited a resume line that does not exist.
* A name-swap audit found no name effect beyond the model's own run-to-run noise. With 8 resume/posting pairs and an illustrative name list, a small effect cannot be ruled out.

## 1. What was evaluated, and how

Three ways of deciding whether a resume supports each requirement of a job description:

* **keyword**: looks for skills from a fixed list of about 40 names and aliases.
* **TF-IDF** (threshold 0.5): splits the posting into requirement lines, weights rare words more, and calls a requirement supported when one resume line contains at least half of its weight.
* **AI** (`gemini-3.5-flash-lite`, free tier): a language model lists the requirements and cites resume line numbers. The cited text is always copied from the resume, never written by the model.

**Data.** 3 job postings and 4 fictional resume variants (tagged `strong`, `weak`, `synonyms`, `aspiration`): 12 pairs and 84 requirement-level labels. The dev split is 1 posting (4 pairs, 28 labels); the test split is 2 postings (8 pairs, 56 labels, of which 14 are "supported").

**Provenance.** The postings and resumes are synthetic. They were adapted from the example dataset that ships with the evaluation tools (`evaluation/data/example/`), which was itself created with the help of an AI assistant, and then modified for testing. The requirement labels were likewise adapted from that example by one person. The four resume variants were designed to include cases that are hard for matchers: skills described in different words, and skills the candidate is only learning.

**Protocol.** The labels were finalized before the matchers were run on this dataset, and their fingerprint (`9ddbd87c2abc`) is identical in the dev, test and AI reports, so they were not edited between those runs. The starting example dataset had, however, already been scored once during development, so the labeling was **not fully blind**. `The evaluation labels were finalized before running the matching algorithms on the custom dataset. However, the dataset was adapted from an example dataset that had previously been evaluated. Since the timing of reviewing those earlier results relative to dataset adaptation is uncertain, the evaluation should not be considered fully blind or independent.
A TF-IDF threshold sweep (0.4, 0.5, 0.6, 0.7) was run on dev. The test split was then scored with keyword, TF-IDF at 0.5, and 3 repeats of the AI matcher.

## 2. Results (test split: 8 pairs, 56 requirement decisions)

| Matcher | Coverage | Precision | Recall | F1 | F1 95% interval | Accuracy |
|---|---|---|---|---|---|---|
| keyword | 57% | 0.69 | 0.64 | 0.67 | 0.30 to 0.85 | 0.84 |
| TF-IDF (0.5) | 79% | 1.00 | 0.64 | 0.78 | 0.33 to 0.96 | 0.91 |
| AI, mean ± sd of 3 repeats | 77% ± 2 | 0.82 ± 0.03 | 0.86 ± 0.00 | 0.84 ± 0.02 | not computed | 0.92 ± 0.01 |

*For the AI row, ± is the spread between repeats of the same data (the model's randomness). It is not a confidence interval.*

Ranking quality (Spearman correlation between a matcher's score and the labeled share of supported requirements; 8 pairs, within-posting mean over 2 postings):

| Matcher | All pairs | Within each posting |
|---|---|---|
| keyword | 0.61 | 0.77 |
| TF-IDF | 0.91 | 0.85 |
| AI | 0.85 ± 0.02 | 0.69 ± 0.05 |

F1 by resume type (14 decisions each):

| Resume | keyword | TF-IDF | AI (3 repeats) |
|---|---|---|---|
| strong | 0.86 | 0.92 | 0.88, 0.88, 0.88 |
| synonyms | 0.67 | 0.67 | 0.89, 1.00, 0.89 |
| aspiration | 0.29 | 0.50 | 0.50, 0.50, 0.50 |
| weak | undefined | undefined | undefined |

`For the weak resume, F1 is undefined because there are no positive supported requirements. Both matchers achieved 1.00 accuracy, correctly classifying all 14 requirements.`

## 3. What these results support

**They do not support a ranking of the matchers.** The F1 intervals of keyword (0.30 to 0.85) and TF-IDF (0.33 to 0.96) overlap almost completely, and the test split contains only 14 supported requirements. The same is true of the ranking correlations, which come from 8 pairs.

**They do show specific behaviours worth reporting:**

* *keyword* found a matching requirement for only 57% of the labeled requirements (skills outside its list, such as Terraform or test-case design, were "not found") and made 4 false positives, including counting lines like "currently learning" or "curious about" as experience.
* *TF-IDF* made no false positives on the test split (precision 1.00) but missed 5 of the 14 supported requirements. Its handling of "curious about" lines was designed while developing against the example dataset this set is adapted from, so its result on the `aspiration` resume is **not an independent test**.
* *AI* found more of the supported requirements (recall 0.86 against 0.64) at some cost in precision (0.82 against 1.00).
* On the single `synonyms` resume (requirements described in different words) the AI scored 0.89 to 1.00 against 0.67 for the other two. That is one resume and 14 decisions: an observation to investigate, not a result.
* All three matchers had trouble with the `aspiration` resume.
* The AI matcher was stable: 98% of decisions were identical across the 3 repeats, and none of its cited lines were invented (0 removed claims). Cost: 9,288 input and 7,415 output tokens for 24 calls.
* **The TF-IDF threshold was not tuned.** Every value from 0.4 to 0.7 gave identical decisions on the dev split (1 posting, 4 resumes), so 0.5 is a default.

## 4. Name-swap bias audit

The audit used the 8 resume/posting pairs of the test split. Only the name on the first line of each resume was changed (8 pairs × 12 names = 96 variants per matcher; the names are an illustrative list, 3 per group). Each resume was also run twice with the same name to measure the model's own randomness.

| Matcher | Decisions flipped by a name change | Flipped with no change (noise) | Beyond noise |
|---|---|---|---|
| keyword | 0 of 96 variants | 0 | 0 |
| TF-IDF | 0 of 96 variants | 0 | 0 |
| AI | 0.7% of decisions (5 of 96 variants had any flip) | 1.8% | 0.0% |

All 5 flips were on one requirement ("test-case-design") of one pair (qa-automation × synonyms), and they occurred with names from all four groups. Mean AI score by name group was 31.2%, 31.8%, 31.9% and 32.6% (white_female, white_male, black_female, black_male). The largest average gap between two groups was 1.5 points (the black_male group scored higher than white_female); the largest single paired gap was 13.3 points, for one resume/posting pair.

**Reading:** the AI matcher's decisions changed no more with the name than when the same resume was simply run again. That is consistent with no name effect in this audit, but 8 pairs and an illustrative name list cannot rule out a small one, so these results are preliminary. Only names were tested, not other signals such as schools, locations or clubs.

`The name-swap audit evaluated eight test-split resume/job pairs using three names per group and three repeated runs. Keyword and TF-IDF showed no name-related decision flips. Gemini showed a 0.7% flip rate, compared with 1.8% same-name run-to-run noise, resulting in 0.0% flips beyond the measured noise. Its largest average score gap between name groups was 1.5 percentage points. These preliminary findings do not establish that the matching system is unbiased because the dataset and illustrative name list are small.`

## 5. Limitations (keep these in the README)

* Small and single-labeler: 3 postings, 4 resumes, one person's adaptation of the labels, and no agreement measure.
* The data is synthetic and adapted from an AI-assisted example. The set deliberately includes hard cases (reworded skills, "currently learning" lines), so scores describe a stress test, not typical performance on real resumes.
* The labeling was not fully blind (see Protocol), and the TF-IDF rules were developed while looking at the example dataset, so TF-IDF's results on this adapted set are optimistic.
* How a matcher's wording is matched to a requirement depends on the aliases chosen when labeling.
* The TF-IDF requirement splitting is a heuristic and its threshold is a default.
* The AI results are specific to one model on one date (`gemini-3.5-flash-lite`, free tier, 2026-10-31).
* This project is a portfolio tool. It has not been validated for hiring decisions and should not make automated ones.
* Only fictional resumes were sent to the AI provider during the evaluation, and no real candidate resumes were used. This matters because Gemini's free tier may use submitted text to improve Google's products.

## 6. What more time would add

10 or more real postings, 4 to 5 resumes per posting, labels written without having seen any matcher results, a second labeler to measure agreement, a dev split large enough to tune the threshold, a validated name list with many more names, and repeating the AI evaluation across models.

## 7. Reproduce

Needs `GEMINI_API_KEY` (and `LLM_PROVIDER=gemini` if another key is also set) for the AI runs; finished AI answers are cached in `evaluation/results/cache/`.

```powershell
python evaluation\run_eval.py --data evaluation\data\mine --split dev --tfidf-thresholds 0.4,0.5,0.6,0.7
python evaluation\run_eval.py --data evaluation\data\mine --split test --tfidf-thresholds 0.5 --llm --llm-runs 3
python evaluation\bias_audit.py --data evaluation\data\mine --split test --max-pairs 8 --names-per-group 3 --llm
```

Reports are in `evaluation/results/`. Labels fingerprint: `9ddbd87c2abc`.

# Ask the Warehouse

Natural language analytics over a SQL warehouse, with a measured evaluation harness.

Type a business question in plain English. The system writes the DuckDB SQL, runs it, and shows
you the rows. Then the interesting part: a golden question set measures how often it is actually
right, and an error taxonomy explains every failure.

**Current score: 97.6 percent execution accuracy on 41 unseen questions** (40 of 41), measured
against verified reference queries, with local models only and zero API spend.

This is the AI engineering step in my portfolio. The earlier projects answer questions with
analysis and ship models as APIs. This one builds a system where a language model is a component
that has to be evaluated, guarded and explained.

## Why this project exists

Most natural language to SQL demos stop at one successful query. That is a demo, not engineering.
The questions worth answering are:

- How accurate is it, measured on questions it has never seen?
- Which kinds of questions does it fail, and why?
- What stops it from running a destructive query?
- What does it cost in latency, and does a smaller model hold up?

This repo answers those with numbers instead of adjectives.

## Current status

| Layer | Scope | Status |
|---|---|---|
| 1 | Schema introspection, prompt builder, question to SQL, CLI | Complete, 5 of 5 acceptance questions pass and are factually correct |
| 2 | Execution guardrails: read only, table allowlist, forced limit, timeout | Complete, 14 of 14 checks pass |
| 3 | Evaluation harness: golden set, execution accuracy, error taxonomy | Complete, 97.6% accuracy, 7 of 7 checks |
| 4 | Streamlit interface for non technical users | Complete, 7 of 7 checks, verified in a browser |
| 5 | Forward deployed pass: one command setup, user guide, handoff note | Complete, 8 of 8 checks |

## Architecture

```
question (plain English)
   |
   v
schema.py        introspects DuckDB: tables, columns, row counts,
   |             real values for category, region, segment, ship mode
   v
prompt.py        system rules plus schema, value lists and sample rows
   |
   v
generate.py      local Ollama call, JSON output, temperature 0, fixed seed
   |
   v
guardrails.py    one SELECT only, five table allowlist, row cap applied
   |
   v
execute.py       child process, hard timeout, terminated if it overruns
   |
   v
ask.py           prints rows, timing and the policy that applied
```

## Quick start

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# the warehouse lives in the sibling retail BI project
python -m src.ask "What is total sales by category?" --model qwen3.5:9b --show-sql
python scripts/acceptance_layer1.py
```

## Layer 1 results (measured, not estimated)

Model: `qwen3.5:9b` through Ollama, temperature 0, seed 42, 4096 context.

| Question | SQL executes | Answer correct | Latency |
|---|---|---|---|
| Total sales by category | yes | yes, Technology 836,154.03 | 26.9s |
| Region with highest profit | yes | yes, West 109,879.80 | 25.4s |
| Distinct orders in 2017 | yes | yes, 1,687 | 14.7s |
| Top 5 sub categories by sales | yes | yes, Phones 330,007.05 leads | 14.3s |
| Segment with lowest average discount | yes | yes, Home Office at 14.7 percent | 17.0s |

Latency includes model load on the first call. Later calls settle around 14 to 17 seconds on this
machine. Every answer above was checked against a direct SQL query, not assumed correct because
the query ran.

## Layer 2 results: guardrails (14 of 14 checks pass)

A language model is an untrusted SQL author, so nothing reaches the database without passing a
validator. The checks and their outcomes:

| Check | Outcome |
|---|---|
| DROP TABLE | refused, only SELECT is allowed |
| DELETE and UPDATE | refused |
| Unknown table | refused, with the allowed list in the message |
| External reader such as read_csv | refused |
| System catalog such as information_schema | refused |
| Two statements in one string | refused, counted as 2 statements |
| PRAGMA | refused |
| Legitimate SELECT, CTE, join and quoted literal | allowed and executed |
| Row cap | a full table scan returned exactly 500 rows, not 9,994 |
| Runaway query | stopped at the timeout and the process terminated |

Every refusal carries a reason a user can read. A silent failure teaches nobody anything.

### Two real bugs the tests caught

**A pipe deadlock.** The first version waited for the child process to exit before reading its
result. With a 500 row payload the pipe buffer filled, the child blocked inside its write, and the
parent blocked waiting for an exit that could never happen. The row cap test exposed it, and the
executor now reads while the child is alive.

**A test that was wrong, not the code.** The first version of the aggregate check summed a column
that lives in a different table. Worth stating plainly: when a test fails, the test is sometimes
the bug.

## Layer 4 results: the interface

`streamlit run app.py` opens a page with a question box, six example questions, and a settings
sidebar showing the model, the query time limit, the row cap and the measured accuracy.

The design rule is that a non technical user never has to see SQL. The answer table is the
primary result. The generated SQL, the explanation and the safety checks are all behind
disclosure controls, available if the user is curious and out of the way if they are not.

Verified by driving the real page in a browser, not by inspecting the code:

| Check | Outcome |
|---|---|
| Page renders | yes, sidebar, examples and question box all present |
| Example button fills the question | yes |
| Submitting runs the pipeline | yes, 21.7s total, 20.9s of it model time |
| Answer table | 3 rows, Technology 836,154.03, matching the verified reference |
| SQL visible in the main view | no, behind a disclosure control as designed |
| Accuracy shown in the sidebar | 40/41 (97.6%), read live from the evaluation results |

### A bug in the acceptance test itself, worth recording

The first version of the Layer 4 test failed with a timeout that made no sense. The cause was
not the app: query execution spawns a child process, and spawn re-imports the entry module in
that child. Because the test script had unguarded top level code, the child re-ran the entire
test recursively. Wrapping the body in a main guard fixed it. The failure looked like a query
problem and was actually a process model problem.

## Layer 3 results: how accurate is it, and where does it fail

41 hand written questions across 8 categories. The reference SQL for every question was executed
and inspected before use, because an unverified oracle makes an accuracy score meaningless.
Numbers are compared after rounding to 2 decimals, ignoring row and column order, but requiring
exact row and column counts.

### Prompt A/B on identical data

| Version | Accuracy | Notes |
|---|---|---|
| v1, original rules | 36/41 = 87.8% | clean baseline, after the warehouse fix |
| **v2, four rules added** | **40/41 = 97.6%** | plus 9.8 points |

The v2 rules were written to target failure modes that were actually observed, not guessed:
DuckDB date syntax, weighted ratios for margins, no unrequested identifier columns, and subquery
alias scoping. No rule was added about the trap questions, because teaching to the test would make
the number meaningless.

### Accuracy by question type (v2)

| Category | v1 | v2 |
|---|---|---|
| aggregation | 100% | 100% |
| filtering | 100% | 100% |
| ratios | 100% | 100% |
| traps | 100% | 100% |
| time | 100% | 100% |
| joins | 80% | 100% |
| ranking | 60% | 100% |
| comparison | 60% | 80% |

### The one remaining failure, described honestly

Question: which state has the most loss making order lines?

The model returned Texas, which is the correct state, but counted 312 distinct orders instead of
486 order lines. It answered a slightly different question correctly. That is a real error and it
stays in the score.

### What v2 fixed, and one regression

Five questions moved from wrong to right. One moved from right to wrong in v1 terms, the counting
unit question above, which v1 had answered by luck with the right count.

## Two data quality bugs this project found

The evaluation was built to measure a model. The first thing it did was find two latent bugs in
the warehouse underneath.

### 1. Non unique product key

The first generated query returned total sales of 2,394,666.53. The true figure is 2,297,200.86,
a 4.2 percent overstatement, and the SQL itself was correct.

`dim_product` had 1,894 rows but only 1,862 distinct product ids. The source file reuses a Product
ID for more than one product name, so a plain `SELECT DISTINCT` left duplicate keys and every join
fanned out. Fixed by keeping one row per product id, using the most frequent name, after confirming
all 32 duplicates agree on category and sub category.

### 2. Non unique date key, the worse one

`dim_date` had 3,472 rows but only 1,237 distinct order dates, because it was built with
`DISTINCT (order_date, ship_date)`. Joining on `order_date` fanned 9,994 rows out to 37,031 and
inflated sales from 2.30M to **8.56M**, a factor of 3.7. Three of the evaluation failures traced
to this single table.

Fixed by rebuilding the dimension at one row per order date. Ship date attributes remain on the
fact table where they belong.

Both are the same failure mode, and it is the one that makes natural language analytics dangerous:
correct looking SQL producing a confidently wrong number. Syntax safety cannot catch it. Only
comparison against a verified reference can.

## Design decisions

- **Local models only.** No API keys, no spend. Ollama on the same machine.
- **Read only connection.** The database is opened read only, so a destructive query cannot commit
  even before the guardrail layer exists.
- **Real categorical values in the prompt.** The model is told the actual labels. Without them it
  invents variants like "Technology and Electronics".
- **JSON output.** The response is parsed as JSON with a fence tolerant fallback, so a stray code
  block cannot break the pipeline.
- **Temperature 0 and a fixed seed.** Runs are reproducible, which matters when comparing models.

## Handoff documents

- [docs/USER_GUIDE.md](docs/USER_GUIDE.md): written for the person using the tool, not the
  person who built it. How to ask well, how to read the answer, and what the failure messages mean.
- [docs/DISCOVERY.md](docs/DISCOVERY.md): the forward deployed note. What was asked for, what was
  built, what was deliberately cut, and what the build actually taught me.

## Disclaimer

Educational portfolio project. The warehouse is a public sample retail dataset.

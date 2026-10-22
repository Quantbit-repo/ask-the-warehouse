# User Guide

For the person using this tool, not the person who built it.

## What this is

A question box for the retail sales data. You type a question in ordinary
English, it works out the query, runs it, and shows you a table of results.

You do not need to know SQL, or how the data is organised underneath.

## Getting started

Ask your question in the box and press **Get the answer**. The first answer
takes about twenty seconds, because the model has to load. After that it is
faster.

If you are not sure what to ask, press one of the example buttons. That fills
the question box for you, and you can edit it before submitting.

## Asking good questions

The tool works best when a question names what you want to measure and how you
want it grouped.

| Works well | Works less well |
|---|---|
| What is total sales by category? | How are we doing? |
| Which region has the highest total profit? | What is the best region? |
| How many orders were placed in 2017? | Tell me about last year |
| What are the top 5 sub categories by sales? | Which products matter? |

Two habits that help:

- **Name the measure.** Sales, profit, quantity, number of orders, discount,
  margin. Saying which one removes guesswork.
- **Name the grouping.** By category, by region, by month, by customer segment.

## Reading the answer

The table is the answer. Above it you get three things worth a glance:

- **The row count and timing**, so you know how much data you are looking at.
- **What this query does**, a one sentence description in plain language.
- **Show the SQL behind this answer**, if you want to check the working or hand
  it to someone technical.

## When something goes wrong

| What you see | What it means | What to do |
|---|---|---|
| "That query was blocked by the safety layer" | The tool tried to do something other than read data, and stopped itself | Rephrase as a question about the data |
| "The question could not be answered from this warehouse" | The data needed is not in here | Check whether the column exists, or ask differently |
| "The query took too long and was stopped" | The question required too much computation | Narrow it down, for example add a year |
| "The local model could not be reached" | Ollama is not running on this machine | Start it with `ollama serve` |
| Empty table, no error | The question was valid but nothing matched | Check the filter, for example the year or the category name |

## What it will not do

- **It will not change your data.** Every query runs on a read only connection,
  and only single SELECT statements are allowed.
- **It will not return more than 500 rows** by default. That is a safety limit
  and you can change it in the sidebar.
- **It is not always right.** It scores 97.6 percent on 41 unseen test
  questions, which means it is wrong about once in every forty questions.
  Spot check anything that drives a real decision.

## If you want to check its accuracy yourself

```bash
python -m eval.run_eval
```

That runs all 41 test questions and prints the score, the breakdown by question
type, and every failure with its cause. It takes about fifteen minutes.

## Where the data comes from

A public sample retail dataset, roughly ten thousand order lines, loaded into a
small analytical database in the sibling `retail-bi-dashboard` project. The
numbers in this tool and the numbers in that dashboard come from the same place,
so they agree.

# Discovery and Handoff Note

A forward deployed engineer does not just build the thing. They write down what
was asked for, what was built, what was left out, and why. This is that note.

**Honest framing first:** this is a self directed portfolio project. The user
described below is a target user I designed for, not a paying client I
interviewed. Everything else in this document, including the cuts and the
reasoning, is real and reflects how I actually built it. I would rather state
that plainly than imply a client engagement that did not happen.

## Who this is for

A retail operations or finance manager who owns questions about sales and profit
but does not write SQL. They currently do one of three things: ask an analyst and
wait, export to a spreadsheet and build a pivot, or give up and guess.

They are not going to learn SQL for this. They are not going to read a schema
diagram. They will use the tool for two weeks and then stop if it wastes their
time once.

## The ask, as a user would put it

> "I can get a report from the BI dashboard, but it only shows what somebody
> already thought to put on it. When I have a new question, I wait two days. I
> want to just ask it and get a number, and I want to know whether the number is
> trustworthy."

Two requirements sit in that paragraph, and only one of them is about answering
questions. The other is about **trust**, which is the harder half.

## What I built, and the reasoning

| Decision | Why |
|---|---|
| Natural language to SQL, not a fixed report list | The complaint was about waiting for new questions, not about missing reports |
| A measured accuracy figure, shown in the interface | The user asked whether numbers are trustworthy. Answering that requires a number, not a promise |
| SQL visible behind a disclosure control | Trust grows when a curious user can check the working. It is hidden because it is not the answer |
| Guardrails that refuse rather than fail | A wrong number that looks plausible is worse than a refusal. The user cannot audit SQL they cannot read |
| Read only connection as well as SQL checks | Two independent barriers, because the cost of one mistake here is the data |
| Local model only | Zero running cost means the tool survives a budget review. It also keeps the data on the machine |
| An error taxonomy rather than one accuracy number | "97.6 percent" does not tell you what to fix. Knowing that margins and counting units are the weak spots does |

## What I deliberately did not build

| Cut | Reason |
|---|---|
| Conversation memory across questions | Adds a failure mode, ambiguous references to earlier questions, for little gain on single question lookups |
| Charts and exports | The user already has a dashboard for visuals. Duplicating it adds surface area without answering the actual complaint |
| Write access of any kind | Nobody asked to change data through chat, and the risk is not worth the convenience |
| A hosted deployment | Running cost and data residency were both open questions. Local was the defensible default |
| Fine tuning the model | The failures were rule and schema problems, not knowledge problems. Prompt rules and a schema fix moved accuracy further, faster |
| Multi database support | One warehouse was the scope. Generality would have meant testing none of it properly |

## What the build actually taught me

Three things I did not expect, all of which changed the work:

1. **Half the accuracy gain came from fixing the data, not the model.** The
   evaluation found two latent bugs in the warehouse underneath, one of which
   inflated joins by a factor of 3.7. No amount of prompt engineering fixes a
   duplicated key.
2. **The failure that matters is silent wrongness.** Correct looking SQL
   returning a confidently wrong number is the dangerous case, and it passes
   every syntax and safety check. Only comparison against a verified reference
   catches it.
3. **Non determinism is a design constraint.** The same question can produce
   different SQL on different runs. Any claim about accuracy has to be a
   measured rate over many questions, never an anecdote from one.

## What I would do in week one with a real user

- Sit with them for an hour and collect the twenty questions they actually ask.
  That becomes the real golden set, replacing my hand written one.
- Instrument the tool to log every question, whether it was answered, and
  whether the user rephrased. Rephrasing is the clearest signal of failure.
- Review the logged failures together, weekly, and turn the recurring ones into
  prompt rules or schema fixes. The accuracy figure should be a moving number,
  not a launch statistic.

## What I would tell them on handover day

- It is right about forty times in forty one. Spot check anything that drives
  a real decision.
- It will refuse rather than guess. A refusal is the system working.
- If it is wrong twice on the same kind of question, that is worth reporting.
  Repeated failures are fixable, and single ones often are not.

## If someone else picks this up

Start with `README.md` for the architecture and the measured results, then
`docs/USER_GUIDE.md` for the user facing behaviour. The acceptance tests under
`scripts/` document what each layer promises, and each one runs in a single
command. If you change the prompt, re run `python -m eval.run_eval` and compare
against the stored results in `eval/results/`, because a prompt change without a
measurement is a guess.

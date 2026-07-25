---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me".
---

## Ask questions one at a time

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask the questions one at a time.

If a question can be answered by exploring the codebase, explore the codebase instead.

## When you are done asking questions

What you found out you should encapsulate into idea.md document in the current project `.../project_dir/plans/IDE-001/idea.md`. `ls` the dir to find the next iteration number.
The file should be a markdown with frontmatter:

```markdown
---
name: IDE-001
description: The idea for description.
---

details here...

```

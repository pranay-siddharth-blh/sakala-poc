# Project Handoff Prompt

**How to use:** Your colleague pastes everything below the line into his Claude chat (ideally inside the same Claude Project where the work was done, so it can use all files and past chats). The prompt already tells his Claude to return the report as a downloadable `.md` file or an artifact, which he can then download or share with you.

---

I need to hand this project over to a teammate who is joining mid-way. He knows nothing about it, and I want him to understand **every bit of the work done so far**. Please go through everything available to you (all chats in this project, uploaded files, code, documents, decisions, outputs, errors, and anything I told you along the way) and write a complete, exhaustive onboarding report. **Deliver it as a downloadable Markdown (.md) file or as an artifact, not as a plain chat reply**, so I can save it and share it. If the report is too long for one file, split it into numbered parts (part-1.md, part-2.md, ...) and give me every one.

Be thorough rather than brief. Do not summarize away details. If something was tried, changed, fixed, or abandoned, include it. Where you are uncertain or inferring rather than sure, flag it clearly with "(uncertain)".

## Required structure

### 1. Project overview
- The problem being solved and why it matters
- Who it is for (client, users, internal team)
- The end goal and what "done" looks like (deliverables, success criteria, deadlines if any)

### 2. Full chronological history (from the very start)
Go step by step, in order, from the first idea or message to today. For each stage include:
- What was done
- Why it was done that way
- What the result or output was
- Any problems hit and how they were solved

### 3. Current state
- What is complete and working
- What is half-done or in progress
- What is broken, untested, or blocked
- The exact point where work stopped, and what was about to happen next

### 4. Architecture and tech stack
- Every component, tool, library, framework, service, API, and data source used
- How the pieces connect (describe or draw a text diagram)
- File and folder structure, with the purpose of each key file
- Important code, queries, prompts, schemas, or configs (include them or point to where they live)

### 5. Data
- Where the data comes from, its format, size, and quality issues
- Cleaning and transformation steps applied
- Any assumptions made about the data

### 6. Key decisions and trade-offs
- What was chosen, what was rejected, and the reasons
- Dead ends and failed approaches, so they are not repeated

### 7. Setup and reproduction guide
- How to run everything from scratch: environment, dependencies, credentials or access he needs to request, commands, in order
- How to verify that it works

### 8. Open questions, risks, and dependencies
- Unresolved issues and assumptions
- Things that depend on other people, approvals, or external services

### 9. Roadmap to the end goal
- Remaining steps in priority order
- Effort estimate for each (rough is fine)
- A suggested way to split the work between two people so we can move in parallel without blocking each other

### 10. Glossary
- Project-specific terms, names, abbreviations, and people involved with their roles

### 11. Where things live
- A list of every file, repo, doc, dashboard, account, or link related to the project

Finish with a short "If you read nothing else" section: the five most important things my teammate must know on day one.

# UI Walkthrough

The UI is a local product console for evidence-quality decisions. It is built to feel like an operations tool, not a fixture viewer.

## Start The App

Start the backend:

```bash
uvicorn api.main:app --reload
```

Start the UI:

```bash
cd ui
npm run dev
```

The UI expects the API at `http://127.0.0.1:8000` unless `VITE_API_BASE_URL` is set.

## Main Console

Route:

```text
/
```

Use the console to run evidence checks.

What to look for:

- API health status
- sample/custom source switch
- fixture bundle selector
- manual evidence builder
- rank-only evidence action
- decision check action
- guided agent check action
- agent assist controls for owner validation, retrieval hit, and retrieval no-hit fixtures
- context need summary
- evidence/source overview
- current outcome card
- next action preview
- run history
- reliability snapshot

Recommended demo flow:

1. Pick a bundle.
2. Use Rank only to inspect source quality without saving a decision run.
3. Run a decision check.
4. For an improving agent case, select a compatible Agent assist option before running a guided check.
5. Switch to Custom evidence and rank or check the default manually entered scenario.
6. Open the saved run from history.
7. Return and run another scenario.

## Run Detail

Route:

```text
/runs/:runId
```

Use run detail to explain why the product made a decision.

What to look for:

- decision summary
- selected claims
- selected evidence
- source-level quality cards
- dimension score bars
- next action or review prompt
- context request or blocked reason
- audit timeline
- report link
- outcome feedback controls

This is the best screen for explaining that the UI is rendering backend-owned policy rather than recalculating the decision.

## Run Report

Route:

```text
/runs/:runId/report
```

Use the report view when you want a presentation-ready record of the check.

What to look for:

- decision brief
- supported claims
- source quality summary
- safety checks
- audit trail
- copy summary action
- print / PDF action

## Review Inbox

Route:

```text
/review/local
```

Use the inbox to triage human-in-the-loop work.

The inbox groups saved runs into review states:

- pending review
- needs context
- needs learning
- answered
- blocked

Open an item to answer the reviewer question or inspect the completed review.

## Review Portal

Route:

```text
/review/:runId
```

Use the review portal when a saved run has an approval prompt.

The portal shows:

- reviewer question
- backend-generated choices
- relevant source citations
- selected claims
- owner picker when the chosen response requires an owner
- risk acceptance when the chosen response requires explicit risk acknowledgement
- notes
- completed review result
- learning feedback after a review is saved

Review submissions call `POST /runs/{run_id}/review`. Learning feedback calls `POST /runs/{run_id}/feedback`.

## Settings

Route:

```text
```text
/settings
```

Settings are local to the browser.

Available sections:

- appearance
- notifications
- user
- systems
- data

Appearance separates color from light/dark mode so the same color direction can be used in either mode.
Systems shows which source systems, persistence, review sharing, and job states are simulated locally versus modelled for future production wiring.
Data reset clears selected run history, review answers, and learning feedback through the API while keeping fixtures and scoring rules intact.

## Recommended Presentation Path

For a 5 to 7 minute walkthrough:

1. Open the console.
2. Rank `Acme Auto Handoff` to show source quality before policy.
3. Run `Acme Auto Handoff`.
4. Open run detail and show source scores.
5. Open the report view and show copy/print export.
6. Run `Northstar Similar Client Review`.
7. Open the review portal and save a directional-context answer.
8. Save learning feedback.
9. Return to the console and show the reliability snapshot.
10. Run or describe the guided agent improvement scenario.

## Current Limits

- The UI uses synthetic fixture bundles and manually entered local evidence.
- Review links are local routes, not emailed links.
- Settings are local browser preferences.
- Feedback learning is conservative and local.
- The UI does not implement production auth, real connectors, emailed review links, or background jobs yet.

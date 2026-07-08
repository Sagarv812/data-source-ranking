# Demo Script

Use this script for the Week 3 local product walkthrough. The story should be that Source Signal is a trust gate for email automation: it decides when retrieved business context is safe to use, when a human should answer a focused question, and when automation should stop.

## Setup

Install and verify the project:

```bash
uv sync --extra dev
cd ui
npm install
cd ..
```

Use the stable fixture date for repeatable scoring:

```bash
export AS_OF=2026-06-21
```

Start the backend:

```bash
uvicorn api.main:app --reload
```

In a second terminal, start the UI:

```bash
cd ui
npm run dev
```

Open the Vite URL, usually `http://localhost:5173`.

Optional clean slate:

1. Open Settings.
2. Go to Data.
3. Reset run history, review answers, and learning feedback before rehearsing the walkthrough.

## Opening Story

Automated email context fails when every retrieved note, deck, proposal, and CRM update is treated as equally trustworthy. This product ranks the evidence first, chooses the safest automation outcome, and asks the smallest useful human question when evidence is incomplete or risky.

In the demo, avoid presenting this as an email-writing tool. Present it as the evidence-quality layer that protects downstream email automation.

## UI Walkthrough

Start on the main console.

1. Confirm the API health indicator is online.
2. Use the bundle picker to select a scenario.
3. Run either a decision check or guided agent check.
4. Open the saved run detail from history.
5. Show evidence quality, selected claims, source scores, the decision summary, next action, and audit timeline.
6. Open the report view to show the shareable decision record, copy summary, and print/PDF action.
7. Open the review portal when a saved run needs human review.
8. Submit a review answer and then save learning feedback.
9. Switch to Custom evidence to show that the UI can test manually entered context, not only fixtures.
10. Return to the console and show the reliability snapshot.

## Scenario 1: Strong Evidence Becomes Auto Handoff

Fixture:

```text
bundles/acme_auto_handoff
```

CLI reference:

```bash
data-source-ranking decide fixtures/bundles/acme_auto_handoff.json --as-of "$AS_OF"
```

UI flow:

1. Select "Acme Auto Handoff".
2. Run a decision check.
3. Show the outcome as "Auto handoff".
4. Open the run detail.
5. Point out the selected sources, high-confidence decision, source citations, and generated handoff preview.

Key message:

The system can move quickly when recent, direct, owned, low-risk evidence supports the needed context.

## Scenario 2: Medium Evidence Asks The Owner

Fixture:

```text
bundles/beta_needs_owner_validation
```

CLI reference:

```bash
data-source-ranking decide fixtures/bundles/beta_needs_owner_validation.json --as-of "$AS_OF"
```

UI flow:

1. Select "Beta Needs Owner Validation".
2. Run a decision check.
3. Show the outcome as a context request.
4. Open the run detail.
5. Show the owner question and why the stale proposal needs validation.

Key message:

The system does not block useful medium-strength context immediately. It asks the most relevant owner a focused question.

## Scenario 3: Similar-Client Evidence Needs Human Review

Fixture:

```text
bundles/northstar_similar_client_review
```

CLI reference:

```bash
data-source-ranking decide fixtures/bundles/northstar_similar_client_review.json --as-of "$AS_OF"
```

UI flow:

1. Select "Northstar Similar Client Review".
2. Run a decision check.
3. Open the saved run detail.
4. Open the review portal.
5. Choose the directional-context option.
6. Save the review.
7. Save learning feedback if the reviewer answer was useful.

Key message:

Similar-client evidence can be useful, but the product keeps it explicitly directional instead of letting it masquerade as confirmed same-client context.

## Scenario 4: Sensitive Partner Material Is Gated

Fixture:

```text
bundles/deltabank_sensitive_partner_material_review
```

CLI reference:

```bash
data-source-ranking decide fixtures/bundles/deltabank_sensitive_partner_material_review.json --as-of "$AS_OF"
```

UI flow:

1. Select "Deltabank Sensitive Partner Material Review".
2. Run a decision check.
3. Show the review prompt and sensitivity reason.
4. Open the review portal.
5. Either exclude the sensitive source or request validation, depending on the story you want to tell.

Key message:

Sensitive evidence is not only a scoring problem. It becomes a policy gate and a reviewer workflow.

## Scenario 5: Weak Ownerless Evidence Is Blocked

Fixture:

```text
bundles/gamma_blocked
```

CLI reference:

```bash
data-source-ranking decide fixtures/bundles/gamma_blocked.json --as-of "$AS_OF"
```

UI flow:

1. Select "Gamma Blocked".
2. Run a decision check.
3. Show the blocked outcome.
4. Open the run detail.
5. Show weak points and the audit trail.

Key message:

The product is allowed to stop automation when the evidence is too vague, stale, ownerless, or unsupported.

## Scenario 6: Guided Agent Improves A Weak Case

Fixture:

```text
bundles/gamma_blocked
```

Simulated retrieval fixture:

```text
simulated_retrieval/gammahealth_retrieves_validated_context
```

CLI reference:

```bash
data-source-ranking run-agent fixtures/bundles/gamma_blocked.json \
  --simulated-retrieval fixtures/simulated_retrieval/gammahealth_retrieves_validated_context.json \
  --as-of "$AS_OF"
```

UI flow:

1. Select "Gamma Blocked".
2. In Agent assist, choose "Retrieval".
3. Choose "Retrieve validated evidence".
4. Run a guided check.
5. Show the initial blocked decision, the retrieval action, the added validated evidence, and the improved final decision.
6. Optionally run the same scenario again with "No retrieval hit" to show that a no-op search stays blocked.

Key message:

The agent loop is bounded and deterministic. It does not invent policy. It retrieves or validates evidence, runs the same decision engine again, and records what changed.

## Scenario 7: Feedback Changes Reliability Snapshot

Fixture:

```text
fixtures/feedback/acme_handoff_accepted.json
```

CLI reference:

```bash
data-source-ranking feedback add fixtures/feedback/acme_handoff_accepted.json
data-source-ranking feedback snapshot
```

UI flow:

1. Open a saved run detail.
2. Save outcome feedback.
3. Return to the console.
4. Show the reliability snapshot card.

Key message:

Feedback affects historical reliability conservatively. It can nudge source-type and source-system reliability, but it cannot override sensitivity, ownership, or unsupported-claim gates.

## Closing Story

The product is intentionally local and synthetic for Week 3, but the product shape is real:

- backend-owned decision policy
- persisted run history
- review portal
- audit timeline
- source-level scoring
- feedback learning
- bounded agent loop

The next product phase is not to make the UI recompute rules. It is to replace fixture providers with real data providers while keeping the same evidence-quality contract.

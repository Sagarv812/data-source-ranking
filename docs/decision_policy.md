# Decision Policy

This document explains how the current prototype turns ranked evidence into a product-facing automation decision.

The policy layer answers one question:

```text
What should the system do next with this evidence bundle?
```

The answer must be one of four outcomes:

- `auto_handoff`
- `generate_context_request`
- `needs_user_review`
- `blocked`

The system exposes the evidence, gates, next action, prompt or request, and audit trace that led to the outcome. A UI should render those fields directly. It should not recalculate ranking, policy, or selected evidence.

## Layers

The code separates evidence quality from automation policy.

`rank_bundle()` handles the evidence layer. It scores each source, assigns source tiers, records weak points, and returns the starter bundle decision. This layer decides whether the evidence looks strong, medium, weak, usable, or blocked from an evidence perspective.

`decide()` handles the automation layer. It calls `rank_bundle()`, evaluates policy gates, selects exactly one final decision, selects evidence for display, and creates the next product action.

That split matters because a bundle can have usable evidence and still require review. For example, an old proposal may help with context, but the policy layer still asks someone to validate it or label it as historical. A similar-client proposal may support directional wording, but the policy layer does not treat it as current-client proof.

## Decision Object Contract

`AutomationDecision` is the API-ready object. It includes:

- `decision`
- `confidence`
- `summary`
- `ranked_bundle`
- `selected_claims`
- `selected_sources`
- `source_citations`
- `weak_points`
- `policy_gates`
- `next_action`
- `approval_prompt`
- `context_request`
- `draft_handoff`
- `blocked_output`
- `audit_trace`
- `metadata`

The output uses mutually exclusive action surfaces:

- `auto_handoff` may include `draft_handoff`.
- `generate_context_request` may include `context_request`.
- `needs_user_review` may include `approval_prompt`.
- `blocked` may include `blocked_output`.

The current implementation keeps the other action surfaces empty for each outcome. That gives the UI a simple rendering rule: render the surface that matches the top-level decision.

## Policy Gates

`evaluate_policy_gates()` returns visible `PolicyGateResult` objects. Each gate has:

- `gate`
- `status`
- `effect`
- `message`
- `source_ids`
- `needed_claim_ids`
- `metadata`

The current gate list is:

| Gate | Main Trigger | Effect |
| --- | --- | --- |
| `required_claims_have_usable_coverage` | Required claims lack usable coverage, or direct but incomplete evidence needs details. | `blocks_automation` or `requires_context_request` |
| `required_claims_have_strong_coverage` | Required claims have usable but not strong coverage. | `prevents_auto_handoff` |
| `sensitivity_allows_automation` | A source has sensitivity risk. | `prevents_auto_handoff` |
| `sensitive_evidence_overlap_absent` | Sensitive weak evidence overlaps usable evidence for the same need. | `requires_user_review` |
| `directional_context_review_absent` | Similar-client evidence supports selected context. | `requires_user_review` |
| `old_proposal_review_absent` | A stale proposal appears while required claims already have strong coverage. | `requires_user_review` |
| `stale_unvalidated_source_absent` | Decision-relevant stale evidence needs owner validation. | `requires_context_request` |
| `unsupported_inference_absent` | A claim uses unsupported inference. | `requires_user_review` |
| `owner_signal_available` | No usable source has a clear validation owner, or usable evidence has an unclear owner. | `blocks_automation` or `requires_user_review` |

Policy gates serve two audiences. Engineers use them to test policy drift. Product surfaces use them to explain why the system chose the next action.

## Precedence

`select_final_decision()` applies gate effects in this order:

1. Any `blocks_automation` gate selects `blocked`.
2. Any `requires_user_review` gate selects `needs_user_review`.
3. A context-request path selects `generate_context_request`.
4. A fully clean strong-evidence path selects `auto_handoff`.
5. A remaining `prevents_auto_handoff` gate selects `needs_user_review`.
6. The fallback selects `blocked`.

This precedence favors safety. A review gate outranks context request and auto handoff. A blocking gate outranks review. The system records all gate results so a user can see related context even when one gate determines the final decision.

## Outcomes

### `auto_handoff`

The system selects `auto_handoff` when all required claims have strong coverage and no review gate fired.

The output includes:

- selected strong source-backed claims
- source citations
- a paragraph-style `draft_handoff`
- `next_action.type = prepare_handoff`
- confidence label `high`

The draft handoff stays extractive. It uses selected claims from sources and does not add inferred bridges.

### `generate_context_request`

The system selects `generate_context_request` when useful evidence exists and the system knows who can answer the missing validation question.

The output includes:

- selected usable evidence
- a `ContextRequest`
- recipient id and name
- the reason that owner was selected
- one focused question
- `next_action.type = ask_owner`

Typical cases:

- stale but useful proposal with a proposal owner
- meeting title without notes where an attendee can fill the missing detail
- medium evidence that needs validation before automation continues

### `needs_user_review`

The system selects `needs_user_review` when useful evidence exists but the current user must resolve one focused uncertainty.

The output includes:

- selected evidence that would be affected by the review
- an `ApprovalPrompt`
- explicit choices with effects
- `next_action.type = ask_user`

Current prompt types:

- `similar_client_directional_context`
- `unclear_owner`
- `sensitive_evidence_overlap`
- `unsupported_claim`
- `sensitive_partner_material`
- `old_proposal`

The prompt does not ask the user to approve a whole email. It asks for one decision: use with a caveat, choose an owner, request validation, remove evidence, skip a source, or stop.

### `blocked`

The system selects `blocked` when the bundle does not have a safe path to automation.

The output includes:

- `BlockedOutput.blocking_reason`
- missing evidence
- sources considered
- blocking policy gates
- manual next step
- `next_action.type = stop`

`blocked` represents a trust-preserving system action. The system evaluated the sources and refused to generate handoff context from weak, missing, ownerless, or risky evidence.

## Selected Evidence

The decision layer selects evidence based on the final decision:

- `auto_handoff` selects strong sources only.
- `generate_context_request` and `needs_user_review` select strong and medium sources.
- `blocked` selects no claims.

For context requests, the selected source list can include the source that needs validation even when no selected claim exists yet. The UI should show that source as the subject of the request.

`source_citations` map selected claims back to source ids, titles, source types, and citation labels. The UI should use citations instead of parsing claim text.

## Confidence

Confidence describes confidence in the chosen decision, not confidence that automation can proceed.

Examples:

- A blocked decision can have high confidence because the system has clear evidence that automation should stop.
- A review decision can have medium confidence because usable evidence exists, but a policy gate requires a human answer.
- An auto handoff can have high confidence because all required claims have strong evidence and no review gate fired.

The confidence object includes both a score and reasons. UI copy should show the reasons when users need to understand the decision.

## Review Responses

`apply_review_response()` handles user answers to approval prompts.

The response layer validates:

- bundle id
- prompt issue type
- selected choice id
- selected owner fields for `choose_owner`
- explicit risk acceptance for risky choices

Accepted responses record deterministic effects and may produce an updated decision.

Current transition behavior:

| Choice | Updated Decision Behavior |
| --- | --- |
| `stop_automation` | Converts the decision to `blocked`. |
| `choose_owner` | Converts the decision to `generate_context_request` for the selected owner. |
| `request_validation` | Converts the decision to `generate_context_request` when the prompt has an owner candidate. If no owner exists, records the missing-owner state. |
| `skip_source` | Removes selected evidence from that source. Blocks when no selected evidence remains. |
| `exclude_sensitive_source` | Removes selected evidence from that source. Keeps review state when safe selected evidence remains. |
| `remove_claim` | Removes matching selected claims and keeps unrelated safe evidence. |
| `use_directional_with_label` | Clears the prompt, preserves evidence, records the directional caveat, and asks for rerun. |
| `use_without_owner` | Clears the prompt, preserves evidence, records ownership risk acceptance, and asks for rerun. |
| `use_cautious_wording` | Clears the prompt, preserves evidence, records unsupported-inference risk acceptance, and asks for rerun. |
| `use_historical_context` | Clears the prompt, preserves evidence, records historical-context caveat, and asks for rerun. |

Review responses do not run the full decision engine again. They apply the user's answer to the current decision object, record effects, and return enough metadata for a later rerun or UI workflow.

This rule prevents a response handler from silently promoting a reviewed decision to auto handoff after only a partial update. A future orchestration layer can run `decide()` again with updated evidence or accepted caveats encoded in state.

## CLI Flows

Use `decide` to inspect the current automation decision:

```bash
data-source-ranking decide fixtures/bundles/northstar_similar_client_review.json --as-of 2026-06-21
```

Use `apply-review` to apply a fixture-backed review answer:

```bash
data-source-ranking apply-review fixtures/reviews/similar_client_use_directional.json
```

Both commands support `--json`. The JSON output should drive tests, API responses, and the future UI.

## Deferred Work

The current policy does not implement semantic contradiction detection. The system can detect sensitive evidence overlap, but it does not compare claim meaning across sources to decide that two claims conflict.

True contradiction support should add:

- contradiction weak points from semantic comparison
- a contradiction policy gate
- a focused contradiction approval prompt
- review-response choices for choosing the safer claim, requesting validation, or stopping automation

The current system also uses hand-written fixture claims. Real deployments need source connectors, normalization, claim extraction, owner inference, and feedback history before the policy can operate on live data.

## UI Guidance

A UI should treat the decision object as the source of truth.

Recommended rendering:

- Show the top-level decision and confidence first.
- Show selected evidence and citations beside the decision.
- Show policy gates as the explanation trail.
- Render exactly one action surface: draft handoff, context request, approval prompt, or blocked output.
- Show audit events as the machine trace for developers and operators.

The UI should not infer hidden state from prose. If a field matters for display or follow-up, the backend should add it to the structured decision object.

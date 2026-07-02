# Prompt Examples

This document shows the focused approval prompts that `decide()` can attach to `needs_user_review` decisions.

Each prompt asks the current user to resolve one evidence issue. The prompt choice records a deterministic effect. The review-response handler can then clear the prompt, request owner validation, remove selected evidence, or block automation.

Use this command shape to inspect any prompt:

```bash
data-source-ranking decide fixtures/bundles/northstar_similar_client_review.json --json --as-of 2026-06-21
```

Use this command shape to apply a fixture-backed answer:

```bash
data-source-ranking apply-review fixtures/reviews/similar_client_use_directional.json --json
```

## Prompt Contract

`ApprovalPrompt` contains:

- `issue_type`
- `question`
- `explanation`
- `recommended_action`
- `choices`
- `source_ids`
- `metadata`

Each choice contains:

- `id`
- `label`
- `effect`
- optional `metadata`

Risk-accepting choices set `metadata.requires_user_acceptance = true`. The response must include `user_accepts_risk = true`, or validation rejects it.

## Similar-Client Directional Context

Fixture:

```bash
data-source-ranking decide fixtures/bundles/northstar_similar_client_review.json --as-of 2026-06-21
```

The policy layer uses this prompt when similar-client evidence supports selected context. The user decides whether the source can help as directional context or should be skipped.

Prompt:

```json
{
  "issue_type": "similar_client_directional_context",
  "question": "Use 'Retail rollout proposal for HarborMart' only as directional context for this automation, or skip it?",
  "recommended_action": "use_directional_with_label",
  "source_ids": ["src_northstar_similar_client_proposal"]
}
```

Choices:

| Choice | Effect |
| --- | --- |
| `use_directional_with_label` | Preserve selected evidence, record `accepted_caveat = similar_client_directional_context`, clear the prompt, and ask for rerun. |
| `skip_source` | Remove the similar-client source from selected context. Block if no selected evidence remains. |

Review examples:

```bash
data-source-ranking apply-review fixtures/reviews/similar_client_use_directional.json
data-source-ranking apply-review fixtures/reviews/similar_client_skip_source.json --json
```

## Unclear Owner

Fixture:

```bash
data-source-ranking decide fixtures/bundles/gammahealth_unclear_owner_review.json --as-of 2026-06-21
```

The policy layer uses this prompt when useful evidence exists but the source lacks a clear validation owner. The current user can choose an owner, accept ownership risk, or skip the source.

Prompt:

```json
{
  "issue_type": "unclear_owner",
  "question": "Who should validate or own 'GammaHealth referral intake workflow notes' before automation continues?",
  "recommended_action": "choose_owner",
  "source_ids": ["src_gammahealth_useful_document_unclear_owner"]
}
```

Choices:

| Choice | Effect |
| --- | --- |
| `choose_owner` | Create a `generate_context_request` decision for the selected owner. |
| `use_without_owner` | Preserve selected evidence, record `accepted_risk = owner_unvalidated`, clear the prompt, and ask for rerun. |
| `skip_source` | Remove the source from selected context. Block if no selected evidence remains. |

Review examples:

```bash
data-source-ranking apply-review fixtures/reviews/unclear_owner_choose_owner.json --json
data-source-ranking apply-review fixtures/reviews/unclear_owner_use_without_owner.json --show-metadata
```

The `choose_owner` response must include:

```json
{
  "selected_owner_id": "user_priya",
  "selected_owner_name": "Priya Shah"
}
```

## Sensitive Evidence Overlap

Fixture:

```bash
data-source-ranking decide fixtures/bundles/delta_contradictory_sources.json --as-of 2026-06-21
```

The policy layer uses this prompt when sensitive weak evidence overlaps safer usable evidence for the same needed claim. The recommended action excludes the sensitive source because safer evidence already supports the need.

Prompt:

```json
{
  "issue_type": "sensitive_evidence_overlap",
  "question": "Sensitive evidence overlaps with usable source-backed context. Should we exclude the sensitive source, request validation, or stop?",
  "recommended_action": "exclude_sensitive_source",
  "source_ids": ["src_deltabank_unverified_partner_material"]
}
```

Choices:

| Choice | Effect |
| --- | --- |
| `exclude_sensitive_source` | Remove selected evidence from the sensitive source. Keep review state when safer selected evidence remains. |
| `request_validation` | Create a context request when the prompt has an owner candidate. |
| `stop_automation` | Convert the decision to `blocked`. |

Review example:

```bash
data-source-ranking apply-review fixtures/reviews/sensitive_overlap_exclude_source.json --json
```

## Unsupported Claim

Fixture:

```bash
data-source-ranking decide fixtures/bundles/acme_unsupported_claim_review.json --as-of 2026-06-21
```

The policy layer uses this prompt when a source includes an inferred claim without enough support. The user can remove the claim, accept cautious wording risk, or stop automation.

Prompt:

```json
{
  "issue_type": "unsupported_claim",
  "question": "This source includes an unsupported inferred claim. Should we remove the claim, use only cautious wording, or stop?",
  "recommended_action": "remove_claim",
  "source_ids": ["src_acme_unsupported_inferred_claim"]
}
```

Choices:

| Choice | Effect |
| --- | --- |
| `remove_claim` | Remove matching selected claims and keep unrelated safe evidence. |
| `use_cautious_wording` | Preserve selected evidence, record `accepted_risk = unsupported_inference`, clear the prompt, and ask for rerun. |
| `stop_automation` | Convert the decision to `blocked`. |

Review example:

```bash
data-source-ranking apply-review fixtures/reviews/unsupported_claim_remove.json --json
```

Risk-accepting response shape:

```json
{
  "selected_choice_id": "use_cautious_wording",
  "user_accepts_risk": true
}
```

## Sensitive Partner Material

Fixture:

```bash
data-source-ranking decide fixtures/bundles/deltabank_sensitive_partner_material_review.json --as-of 2026-06-21
```

The policy layer uses this prompt when standalone partner-channel or sensitive material appears in the bundle. The recommended action requests validation because excluding the source may leave useful context unresolved.

Prompt:

```json
{
  "issue_type": "sensitive_partner_material",
  "question": "This source is sensitive partner material. Should we request validation, exclude it, or stop?",
  "recommended_action": "request_validation",
  "source_ids": ["src_deltabank_unverified_partner_material"]
}
```

Choices:

| Choice | Effect |
| --- | --- |
| `request_validation` | Create a context request when the prompt has an owner candidate. |
| `exclude_sensitive_source` | Remove selected evidence from the sensitive source. |
| `stop_automation` | Convert the decision to `blocked`. |

Review example:

```bash
data-source-ranking apply-review fixtures/reviews/sensitive_partner_request_validation.json --json
```

## Old Proposal

Fixture:

```bash
data-source-ranking decide fixtures/bundles/betaworks_old_proposal_review.json --as-of 2026-06-21
```

The policy layer uses this prompt when a stale proposal appears while required claims already have strong coverage. The user can validate the proposal, label it as historical context, or skip it.

Prompt:

```json
{
  "issue_type": "old_proposal",
  "question": "This proposal may be stale. Should we request validation, use it only as historical context, or skip it?",
  "recommended_action": "request_validation",
  "source_ids": ["src_betaworks_old_proposal_with_owner"]
}
```

Choices:

| Choice | Effect |
| --- | --- |
| `request_validation` | Create a context request for the proposal owner when available. |
| `use_historical_context` | Preserve selected evidence, record `accepted_caveat = historical_context_only`, clear the prompt, and ask for rerun. |
| `skip_source` | Remove the old proposal from selected context. Block if no selected evidence remains. |

Review example:

```bash
data-source-ranking apply-review fixtures/reviews/old_proposal_use_historical_context.json --show-metadata
```

Risk-accepting response shape:

```json
{
  "selected_choice_id": "use_historical_context",
  "user_accepts_risk": true
}
```

## Review Fixture Index

| Prompt Type | Review Fixture | Expected Updated Decision |
| --- | --- | --- |
| `similar_client_directional_context` | `fixtures/reviews/similar_client_use_directional.json` | `needs_user_review` with prompt cleared and directional caveat recorded. |
| `similar_client_directional_context` | `fixtures/reviews/similar_client_skip_source.json` | `blocked` because skipping removes the only selected evidence. |
| `unclear_owner` | `fixtures/reviews/unclear_owner_choose_owner.json` | `generate_context_request` for `user_priya`. |
| `unclear_owner` | `fixtures/reviews/unclear_owner_use_without_owner.json` | `needs_user_review` with prompt cleared and owner risk recorded. |
| `sensitive_evidence_overlap` | `fixtures/reviews/sensitive_overlap_exclude_source.json` | `needs_user_review` with safer selected evidence preserved. |
| `sensitive_partner_material` | `fixtures/reviews/sensitive_partner_request_validation.json` | `generate_context_request` for the prompt owner candidate. |
| `unsupported_claim` | `fixtures/reviews/unsupported_claim_remove.json` | `needs_user_review` with unrelated safe evidence preserved. |
| `old_proposal` | `fixtures/reviews/old_proposal_use_historical_context.json` | `needs_user_review` with prompt cleared and historical caveat recorded. |

## Deferred Prompt Type

The current system does not generate contradiction prompts. Semantic contradiction detection needs a claim-comparison layer before the prompt builder can ask the user to choose between conflicting claims.

The future contradiction prompt should include the conflicting claim texts, source ids, source titles, and choices to pick a safer claim, request validation, or stop automation.

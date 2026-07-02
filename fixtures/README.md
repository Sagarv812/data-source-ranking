# Fixture Conventions

Fixtures are realistic example scenarios used to test and demonstrate the evidence-quality ranking system without connecting to real CRM, calendar, document, proposal, or partner systems.

The shared fictional setting is a tech consulting and enterprise software services environment. The company using this system sells workflow automation, implementation support, and transformation programs to mid-market and enterprise clients.

## Normalized Data, Not Raw Exports

Fixture JSON files represent normalized post-retrieval records, not raw Salesforce, HubSpot, Gong, Drive, or proposal-system payloads.

In a real implementation, the flow would look like this:

```text
raw CRM / meeting / document / proposal data
  -> connector-specific parsing
  -> normalized Source records
  -> claim extraction
  -> owner candidate inference
  -> directness inference
  -> sensitivity labeling
  -> scoring and decisions
```

Fields such as `id`, `title`, `summary`, `created_at`, `updated_at`, `author`, `attendees`, `client_id`, `account_id`, `opportunity_id`, and `source_system` are usually available or derivable from source systems.

Fields such as `claims`, `supports_needed_claim_ids`, `directness_relation`, `owner_candidates`, and `sensitivity_labels` are the system's normalized/enriched view of the raw source. For the MVP fixtures, these are written manually so the ranking engine can be tested before real connectors and extraction logic exist.

The `expected` object is test metadata only. It is not input the production system would receive.

## Stable Date

Use this stable evaluation date for fixture expectations:

```text
2026-06-21
```

All freshness expectations should be interpreted relative to that date unless a test passes a different `as_of` value.

## Folder Structure

```text
fixtures/strong/
fixtures/medium/
fixtures/weak/
fixtures/bundles/
fixtures/reviews/
```

Use strength folders for single-source scenarios. Use `bundles/` for multi-source scenarios where corroboration, sensitive evidence overlap, owner resolution, or automation decisions will eventually be tested.
Use `reviews/` for deterministic examples of prompt responses applied to bundle decisions.

## Fixture Index

Single-source fixtures are grouped by expected source tier. The tier describes individual evidence strength for the fixture's context need, not whether the source alone completes every automation need.

### Strong Sources

| Fixture | Expected Tier | What It Proves |
| --- | --- | --- |
| `fixtures/strong/acme_recent_crm_note.json` | `strong` | Recent same-client CRM evidence from an account owner can be strong even before bundle corroboration. |
| `fixtures/strong/acme_recent_meeting_notes_clear_attendees.json` | `strong` | Recent meeting notes with clear attendees and next-step detail can support auto-handoff context. |
| `fixtures/strong/betaworks_current_opportunity_owner_note.json` | `strong` | Same-opportunity evidence authored by the current opportunity owner can stand on strong authority. |
| `fixtures/strong/deltabank_recent_meeting_notes_clear_attendees.json` | `strong` | Direct financial-services meeting evidence can be strong when it is recent, specific, and owner-linked. |
| `fixtures/strong/gammahealth_human_validated_context.json` | `strong` | Human validation can refresh and strengthen otherwise risky re-engagement context. |
| `fixtures/strong/northstar_final_proposal_with_feedback.json` | `strong` | Final proposal feedback with accepted validation can provide high-authority decision context. |

### Medium Sources

| Fixture | Expected Tier | What It Proves |
| --- | --- | --- |
| `fixtures/medium/acme_same_client_adjacent_work.json` | `medium` | Same-client adjacent-opportunity work is useful but should not masquerade as current-opportunity evidence. |
| `fixtures/medium/betaworks_old_proposal_with_owner.json` | `medium` | Older proposal evidence can be useful when it has a clear owner path for validation. |
| `fixtures/medium/deltabank_meeting_title_without_notes.json` | `medium` | A meeting event/title can confirm interaction but remains incomplete without notes. |
| `fixtures/medium/gammahealth_useful_document_unclear_owner.json` | `medium` | Useful content with unclear ownership should be treated as usable but not automatic. |
| `fixtures/medium/northstar_similar_client_proposal.json` | `medium` | Similar-client context can be directional support, capped below strong. |

### Weak Sources

| Fixture | Expected Tier | What It Proves |
| --- | --- | --- |
| `fixtures/weak/acme_document_no_clear_owner.json` | `weak` | Strong-looking document content is unsafe when no validation owner is available. |
| `fixtures/weak/acme_unsupported_inferred_claim.json` | `weak` | Unsupported inference should block confident automation even when the surrounding source looks direct. |
| `fixtures/weak/betaworks_stale_account_context.json` | `weak` | Stale account context should not drive current expansion messaging without validation. |
| `fixtures/weak/deltabank_unverified_partner_material.json` | `weak` | Partner-channel material is sensitive and low-directness unless validated by the account team. |
| `fixtures/weak/gammahealth_old_generic_deck.json` | `weak` | Old generic decks are too stale and vague for personalized outreach context. |
| `fixtures/weak/gammahealth_vague_crm_note.json` | `weak` | Recent CRM data can still be weak when the claim is too vague. |
| `fixtures/weak/northstar_weak_similar_client_match.json` | `weak` | Keyword-only similar-client matches are weak directional evidence. |

### Bundles

Bundle fixtures combine scattered sources around one context need and exercise the final automation decision.

| Fixture | Expected Decision | What It Proves |
| --- | --- | --- |
| `fixtures/bundles/acme_auto_handoff.json` | `auto_handoff` | Strong recent CRM and meeting evidence can safely cover the required handoff context. |
| `fixtures/bundles/acme_unsupported_claim_review.json` | `needs_user_review` | Usable adjacent context is present, but an unsupported inferred claim overlaps that need and should force focused review. |
| `fixtures/bundles/betaworks_old_proposal_review.json` | `auto_handoff` | Evidence-layer output is safe on required claims; policy gates escalate because optional old proposal context needs validation, historical labeling, or skipping. |
| `fixtures/bundles/beta_needs_owner_validation.json` | `generate_context_request` | Useful but older BetaWorks evidence should ask for owner validation before automation. |
| `fixtures/bundles/delta_contradictory_sources.json` | `needs_user_review` | Sensitive partner-channel evidence overlapping with usable evidence should force review. |
| `fixtures/bundles/deltabank_sensitive_partner_material_review.json` | `auto_handoff` | Evidence-layer output is safe on required claims; policy gates escalate because optional partner material is sensitive. |
| `fixtures/bundles/gamma_blocked.json` | `blocked` | Vague or stale weak evidence should block automation when no usable source covers the required need. |
| `fixtures/bundles/gammahealth_unclear_owner_review.json` | `generate_context_request` | Evidence-layer output is usable-but-owner-ambiguous; policy gates escalate the final automation decision to unclear-owner review. |
| `fixtures/bundles/northstar_similar_client_review.json` | `generate_context_request` | Evidence-layer output is usable-but-not-strong; policy gates escalate the final automation decision to similar-client review. |

### Review Responses

Review fixtures pair a bundle fixture with one user response to the focused approval prompt. They are consumed by `data-source-ranking apply-review`.

| Fixture | Response | What It Proves |
| --- | --- | --- |
| `fixtures/reviews/similar_client_use_directional.json` | `use_directional_with_label` | Accepts similar-client evidence as directional context and preserves selected evidence for rerun. |
| `fixtures/reviews/similar_client_skip_source.json` | `skip_source` | Removes the only selected similar-client evidence and blocks automation. |
| `fixtures/reviews/unclear_owner_choose_owner.json` | `choose_owner` | Converts an unclear-owner review into an owner validation context request. |
| `fixtures/reviews/unclear_owner_use_without_owner.json` | `use_without_owner` | Records explicit owner-risk acceptance and preserves selected evidence for rerun. |
| `fixtures/reviews/sensitive_overlap_exclude_source.json` | `exclude_sensitive_source` | Excludes sensitive overlapping evidence while preserving safer selected evidence. |
| `fixtures/reviews/sensitive_partner_request_validation.json` | `request_validation` | Converts standalone sensitive partner material review into an owner validation context request. |
| `fixtures/reviews/unsupported_claim_remove.json` | `remove_claim` | Records unsupported-claim removal without deleting unrelated safe evidence. |
| `fixtures/reviews/old_proposal_use_historical_context.json` | `use_historical_context` | Records stale-proposal risk acceptance and historical-context labeling. |

## Fictional Clients

| Client ID | Name | Industry | Typical Scenario Use |
| --- | --- | --- | --- |
| `client_acme` | Acme Robotics | manufacturing / robotics | renewal pitch, implementation-risk concerns, auto-handoff bundle |
| `client_betaworks` | BetaWorks Software | B2B SaaS | expansion opportunities, old proposal validation, current-owner notes |
| `client_gammahealth` | GammaHealth | healthcare operations | re-engagement outreach, human-validated context, vague/stale context contrasts |
| `client_deltabank` | DeltaBank | financial services | risk-workshop context, meeting evidence, sensitive partner evidence, review risk |
| `client_northstar` | Northstar Retail | retail operations | final proposal feedback, similar-client references, directional examples |

## Fictional People

| User ID | Name | Role | Typical Scenario Use |
| --- | --- | --- | --- |
| `user_priya` | Priya Shah | `account_owner` | strong account-owner CRM notes, owner validation |
| `user_mateo` | Mateo Chen | `opportunity_owner` | current opportunity notes and pitch context |
| `user_lina` | Lina Rao | `proposal_owner` | old proposals, final proposal feedback |
| `user_jordan` | Jordan Lee | `meeting_attendee` | meeting notes, implementation details, solution context |
| `user_avery` | Avery Brooks | `partner_contact` | partner-channel material and sensitivity cases |
| `user_sam` | Sam Rivera | `user` | current user who may answer focused review prompts |

Use role enum values in fixture data and keep human-readable titles in `role_title`.

## Common Accounts And Opportunities

| Object ID | Description |
| --- | --- |
| `account_acme` | Acme Robotics account |
| `opp_acme_renewal_2026` | Acme renewal pitch for 2026 |
| `opp_acme_implementation_review_2025` | Prior Acme implementation review |
| `account_betaworks` | BetaWorks Software account |
| `opp_betaworks_expansion_2026` | BetaWorks expansion opportunity |
| `account_gammahealth` | GammaHealth account |
| `opp_gammahealth_reengagement_2026` | GammaHealth re-engagement outreach |
| `account_deltabank` | DeltaBank account |
| `opp_deltabank_risk_workshop_2026` | DeltaBank risk workshop pitch |
| `account_northstar` | Northstar Retail account |
| `opp_northstar_transformation_2026` | Northstar transformation program |

## ID Conventions

Use IDs that expose the business meaning:

```text
need_acme_renewal
need_claim_current_concern
src_acme_recent_crm_note
claim_acme_timeline_concern
user_priya
```

Prefer scenario file names that include the client and source behavior:

```text
fixtures/strong/acme_recent_crm_note.json
fixtures/medium/betaworks_old_proposal_with_owner.json
fixtures/weak/gammahealth_vague_crm_note.json
fixtures/bundles/acme_auto_handoff.json
```

## Source Realism

Fixtures should look like data that might plausibly come from real systems:

- Salesforce or CRM notes should be concise, timestamped, and tied to account or opportunity IDs.
- Meeting events may have attendees but little detail.
- Meeting notes should include specific concerns, decisions, or next steps.
- Proposals should contain concrete prior-work claims and a proposal owner.
- Final proposal feedback should include decision outcome or buyer feedback.
- Decks may be generic or stale, especially weak examples.
- Similar-client examples must be clearly marked with `directness_relation: "similar_client"` and a `similarity_reason`.
- Partner material should include `partner_channel` or related sensitivity labels.

## Expected Metadata

Single-source fixtures should include expected tier metadata:

```json
{
  "expected": {
    "tier": "medium",
    "weak_points": ["stale_source", "missing_owner"]
  }
}
```

Use expected weak points to describe why a source should not be stronger. These expected values will power regression tests before scoring exists.

## Modeling Rules

- Every source must include `summary` or `body`.
- Missing dates are allowed when they are part of the scenario.
- Missing owners are allowed when they are part of the scenario.
- Similar-client sources must include `similarity_reason`.
- Sensitive or partner-channel sources should use `sensitivity_labels`.
- Claims should reference structured context needs using `supports_needed_claim_ids`.
- Human validation should use `validation_history`, including `validated_claim_ids` when only specific claims were validated.

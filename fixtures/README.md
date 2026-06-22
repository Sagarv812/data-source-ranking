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
```

Use strength folders for single-source scenarios. Use `bundles/` for multi-source scenarios where corroboration, contradiction, owner resolution, or automation decisions will eventually be tested.

## Fictional Clients

| Client ID | Name | Industry | Typical Scenario Use |
| --- | --- | --- | --- |
| `client_acme` | Acme Robotics | manufacturing / robotics | renewal pitch, implementation-risk concerns, auto-handoff bundle |
| `client_betaworks` | BetaWorks Software | B2B SaaS | expansion opportunities, old proposal validation, current-owner notes |
| `client_gammahealth` | GammaHealth | healthcare operations | re-engagement outreach, human-validated context, vague/stale context contrasts |
| `client_deltabank` | DeltaBank | financial services | risk-workshop context, meeting evidence, contradictions and sensitivity risk |
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

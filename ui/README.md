# Source Signal UI

React interface for the local data source ranking product.

## Commands

```bash
npm install
npm run dev
npm run build
npm run lint
```

The UI expects the FastAPI backend at `http://127.0.0.1:8000` by default.
Override with `VITE_API_BASE_URL` when needed.

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

Amplify Hosting builds use the root `amplify.yml`. That build generates Amplify outputs and runs `scripts/write-ui-api-env.mjs` so `VITE_API_BASE_URL`, `VITE_AUTH_USER_POOL_ID`, and `VITE_AUTH_USER_POOL_CLIENT_ID` point at the deployed API Gateway and Cognito resources before `npm run build` runs.

## Current Slice

- Pastel evidence-console shell with local theme settings.
- API health, bundle fixtures, run history, review queue, and feedback snapshot queries.
- Standalone rank-only workflow for fixture-backed and manually entered evidence.
- Decision, custom evidence, and guided agent run creation through persisted API run endpoints.
- Agent assist controls for compatible owner-response, retrieval-hit, and retrieval no-hit fixtures.
- Run detail route at `/runs/:runId` with decision summary, score breakdowns, selected claims, audit timeline, review link, report link, and outcome feedback.
- Run report route at `/runs/:runId/report` with copy-summary and browser print/PDF actions.
- Review inbox at `/review/local`.
- Review portal route at `/review/:runId` with backend-generated choices, owner/risk follow-up controls, saved review result, and learning feedback.
- Settings route at `/settings` with appearance, notification, local user, systems readiness, and data reset sections.

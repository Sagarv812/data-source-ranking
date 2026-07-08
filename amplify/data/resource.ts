import { type ClientSchema, a, defineData } from '@aws-amplify/backend';

const schema = a.schema({
  Workspace: a
    .model({
      name: a.string().required(),
      slug: a.string().required(),
      defaultReviewerName: a.string(),
      settings: a.json(),
      createdAt: a.datetime(),
      updatedAt: a.datetime(),
    })
    .authorization((allow) => [allow.authenticated()]),

  ClientAccount: a
    .model({
      workspaceId: a.id().required(),
      name: a.string().required(),
      accountKey: a.string(),
      ownerName: a.string(),
      metadata: a.json(),
      createdAt: a.datetime(),
      updatedAt: a.datetime(),
    })
    .authorization((allow) => [allow.authenticated()]),

  Scenario: a
    .model({
      workspaceId: a.id().required(),
      clientAccountId: a.id(),
      title: a.string().required(),
      emailGoal: a.string().required(),
      riskTolerance: a.string(),
      status: a.string(),
      bundlePayload: a.json().required(),
      createdAt: a.datetime(),
      updatedAt: a.datetime(),
    })
    .authorization((allow) => [allow.authenticated()]),

  EvidenceSource: a
    .model({
      workspaceId: a.id().required(),
      clientAccountId: a.id(),
      scenarioId: a.id(),
      sourceSystem: a.string().required(),
      sourceType: a.string().required(),
      title: a.string().required(),
      summary: a.string(),
      payload: a.json().required(),
      createdAt: a.datetime(),
      updatedAt: a.datetime(),
    })
    .authorization((allow) => [allow.authenticated()]),

  EvidenceRun: a
    .model({
      workspaceId: a.id().required(),
      clientAccountId: a.id(),
      scenarioId: a.id(),
      kind: a.string().required(),
      status: a.string().required(),
      decision: a.string(),
      confidenceLabel: a.string(),
      sourceCount: a.integer(),
      resultPayload: a.json().required(),
      startedAt: a.datetime(),
      completedAt: a.datetime(),
    })
    .authorization((allow) => [allow.authenticated()]),

  ReviewTask: a
    .model({
      workspaceId: a.id().required(),
      runId: a.id().required(),
      assignedTo: a.string(),
      status: a.string().required(),
      issueType: a.string(),
      question: a.string(),
      reviewPayload: a.json(),
      createdAt: a.datetime(),
      completedAt: a.datetime(),
    })
    .authorization((allow) => [allow.authenticated()]),

  FeedbackSignal: a
    .model({
      workspaceId: a.id().required(),
      runId: a.id().required(),
      reviewTaskId: a.id(),
      outcome: a.string().required(),
      sourceOutcomePayload: a.json(),
      createdAt: a.datetime(),
    })
    .authorization((allow) => [allow.authenticated()]),

  SourceSystemConnection: a
    .model({
      workspaceId: a.id().required(),
      sourceSystem: a.string().required(),
      displayName: a.string().required(),
      status: a.string().required(),
      configPayload: a.json(),
      updatedAt: a.datetime(),
    })
    .authorization((allow) => [allow.authenticated()]),
});

export type Schema = ClientSchema<typeof schema>;

export const data = defineData({
  schema,
  authorizationModes: {
    defaultAuthorizationMode: 'userPool',
  },
});

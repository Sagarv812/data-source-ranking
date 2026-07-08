import { RemovalPolicy, Stack } from 'aws-cdk-lib';
import { AttributeType, BillingMode, Table } from 'aws-cdk-lib/aws-dynamodb';
import type { Construct } from 'constructs';

export type ProductStateTables = {
  runTable: Table;
  reviewEventTable: Table;
  feedbackTable: Table;
};

export function createProductStateTables(scope: Construct): ProductStateTables {
  const tableDefaults = {
    billingMode: BillingMode.PAY_PER_REQUEST,
    partitionKey: {
      name: 'id',
      type: AttributeType.STRING,
    },
    pointInTimeRecoverySpecification: {
      pointInTimeRecoveryEnabled: true,
    },
    removalPolicy: RemovalPolicy.RETAIN,
  };

  return {
    runTable: new Table(scope, 'ProductRunTable', tableDefaults),
    reviewEventTable: new Table(scope, 'ProductReviewEventTable', tableDefaults),
    feedbackTable: new Table(scope, 'ProductFeedbackTable', tableDefaults),
  };
}

export function productStoreEnvironment(tables: ProductStateTables) {
  return {
    API_PRODUCT_STORE_BACKEND: 'dynamodb',
    API_DYNAMODB_RUN_TABLE: tables.runTable.tableName,
    API_DYNAMODB_REVIEW_EVENT_TABLE: tables.reviewEventTable.tableName,
    API_DYNAMODB_FEEDBACK_TABLE: tables.feedbackTable.tableName,
    AWS_REGION: Stack.of(tables.runTable).region,
  };
}

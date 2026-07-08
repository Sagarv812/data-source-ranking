import { defineBackend } from '@aws-amplify/backend';
import { auth } from './auth/resource';
import { createProductApi, productApiOutput } from './product-api/resource';
import { createProductStateTables, productStoreEnvironment } from './product-state/resource';

/**
 * @see https://docs.amplify.aws/react/build-a-backend/ to add storage, functions, and more
 */
const backend = defineBackend({
  auth,
});

const productStateStack = backend.createStack('product-state-stack');
const productStateTables = createProductStateTables(productStateStack);
const productStoreEnv = productStoreEnvironment(productStateTables);
const productApiStack = backend.createStack('product-api-stack');
const productApi = createProductApi(
  productApiStack,
  productStateTables,
  productStoreEnv,
  backend.auth.resources.userPool,
);

backend.addOutput({
  custom: {
    API: {
      SourceSignalProductApi: productApiOutput(productApi),
    },
    productState: {
      backend: productStoreEnv.API_PRODUCT_STORE_BACKEND,
      tables: {
        runs: productStoreEnv.API_DYNAMODB_RUN_TABLE,
        reviews: productStoreEnv.API_DYNAMODB_REVIEW_EVENT_TABLE,
        feedback: productStoreEnv.API_DYNAMODB_FEEDBACK_TABLE,
      },
      apiEnvironment: productStoreEnv,
      region: productStoreEnv.AWS_REGION,
    },
  },
});

import { existsSync, cpSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { join } from 'node:path';
import { Duration, Stack } from 'aws-cdk-lib';
import {
  AuthorizationType,
  CognitoUserPoolsAuthorizer,
  Cors,
  LambdaIntegration,
  RestApi,
} from 'aws-cdk-lib/aws-apigateway';
import type { IUserPool } from 'aws-cdk-lib/aws-cognito';
import { Code, Function, Runtime } from 'aws-cdk-lib/aws-lambda';
import type { Construct } from 'constructs';
import type { ProductStateTables } from '../product-state/resource';

export type ProductApi = {
  function: Function;
  restApi: RestApi;
};

export function createProductApi(
  scope: Construct,
  tables: ProductStateTables,
  environment: Record<string, string>,
  userPool: IUserPool,
): ProductApi {
  const productApiFunction = new Function(scope, 'ProductApiFunction', {
    runtime: Runtime.PYTHON_3_12,
    handler: 'api.lambda_handler.handler',
    code: Code.fromAsset('.', {
      bundling: {
        local: {
          tryBundle(outputDir: string) {
            return tryLocalPythonBundle(outputDir);
          },
        },
        image: Runtime.PYTHON_3_12.bundlingImage,
        command: [
          'bash',
          '-c',
          [
            'python -m pip install /asset-input -t /asset-output',
            'cp -R /asset-input/api /asset-output/api',
            'cp -R /asset-input/fixtures /asset-output/fixtures',
          ].join(' && '),
        ],
      },
    }),
    environment: {
      ...lambdaEnvironment(environment),
      API_FIXTURE_ROOT: 'fixtures',
      API_CORS_ALLOW_ORIGINS: '*',
    },
    memorySize: 1024,
    timeout: Duration.seconds(30),
  });

  tables.runTable.grantReadWriteData(productApiFunction);
  tables.reviewEventTable.grantReadWriteData(productApiFunction);
  tables.feedbackTable.grantReadWriteData(productApiFunction);

  const restApi = new RestApi(scope, 'ProductRestApi', {
    restApiName: 'source-signal-product-api',
    deploy: true,
    deployOptions: {
      stageName: 'prod',
    },
    defaultCorsPreflightOptions: {
      allowHeaders: [...Cors.DEFAULT_HEADERS, 'Authorization'],
      allowMethods: Cors.ALL_METHODS,
      allowOrigins: Cors.ALL_ORIGINS,
    },
  });
  const integration = new LambdaIntegration(productApiFunction);
  const authorizer = new CognitoUserPoolsAuthorizer(scope, 'ProductApiAuthorizer', {
    cognitoUserPools: [userPool],
  });
  const protectedMethodOptions = {
    authorizer,
    authorizationType: AuthorizationType.COGNITO,
  };

  restApi.root.addMethod('ANY', integration, protectedMethodOptions);
  restApi.root.addProxy({
    anyMethod: true,
    defaultIntegration: integration,
    defaultMethodOptions: protectedMethodOptions,
  });

  return {
    function: productApiFunction,
    restApi,
  };
}

function lambdaEnvironment(environment: Record<string, string>) {
  const { AWS_REGION: _awsRegion, ...allowedEnvironment } = environment;
  return allowedEnvironment;
}

function tryLocalPythonBundle(outputDir: string) {
  if (process.platform !== 'linux') {
    return false;
  }

  const python = findPythonWithPip();
  if (!python) {
    return false;
  }

  const install = spawnSync(
    python,
    ['-m', 'pip', 'install', process.cwd(), '-t', outputDir],
    { stdio: 'inherit' },
  );
  if (install.status !== 0) {
    return false;
  }

  cpSync(join(process.cwd(), 'api'), join(outputDir, 'api'), { recursive: true });
  cpSync(join(process.cwd(), 'fixtures'), join(outputDir, 'fixtures'), { recursive: true });
  return true;
}

function findPythonWithPip() {
  const candidates = [
    process.env.PYTHON,
    join(process.cwd(), '.venv', 'bin', 'python'),
    'python3',
    'python',
  ].filter((candidate): candidate is string => Boolean(candidate));

  for (const candidate of candidates) {
    if (candidate.includes('/') && !existsSync(candidate)) {
      continue;
    }

    const result = spawnSync(candidate, ['-m', 'pip', '--version'], { stdio: 'ignore' });
    if (result.status === 0) {
      return candidate;
    }
  }

  return null;
}

export function productApiOutput(productApi: ProductApi) {
  return {
    apiName: productApi.restApi.restApiName,
    endpoint: productApi.restApi.url,
    authorization: 'cognito_user_pools',
    region: Stack.of(productApi.restApi).region,
    stage: 'prod',
  };
}

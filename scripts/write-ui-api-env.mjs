import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

const args = new Map();
for (let index = 2; index < process.argv.length; index += 1) {
  const arg = process.argv[index];
  if (arg.startsWith('--')) {
    const next = process.argv[index + 1];
    if (next && !next.startsWith('--')) {
      args.set(arg, next);
      index += 1;
    } else {
      args.set(arg, true);
    }
  }
}

const outputsPath = resolve(String(args.get('--outputs') ?? 'amplify_outputs.json'));
const outPath = resolve(String(args.get('--out') ?? 'ui/.env.production.local'));
const required = args.has('--required');

if (!existsSync(outputsPath)) {
  if (required) {
    console.error(`Amplify outputs file not found: ${outputsPath}`);
    process.exit(1);
  }
  console.warn(`Amplify outputs file not found, skipping UI API env: ${outputsPath}`);
  process.exit(0);
}

const outputs = JSON.parse(readFileSync(outputsPath, 'utf8'));
const endpoint =
  outputs?.custom?.API?.SourceSignalProductApi?.endpoint ??
  outputs?.custom?.api_endpoint ??
  outputs?.custom?.API?.endpoint;
const auth = outputs?.auth ?? {};
const userPoolId = auth.user_pool_id ?? auth.userPoolId;
const userPoolClientId = auth.user_pool_client_id ?? auth.userPoolClientId;
const region =
  auth.aws_region ??
  auth.region ??
  outputs?.custom?.API?.SourceSignalProductApi?.region ??
  outputs?.custom?.productState?.region;

if (!endpoint || typeof endpoint !== 'string') {
  if (required) {
    console.error('Amplify outputs did not include custom.API.SourceSignalProductApi.endpoint.');
    process.exit(1);
  }
  console.warn('Amplify outputs did not include a Source Signal product API endpoint.');
  process.exit(0);
}

const missingAuth = [
  ['auth.user_pool_id', userPoolId],
  ['auth.user_pool_client_id', userPoolClientId],
].filter(([, value]) => !value || typeof value !== 'string');

if (missingAuth.length > 0 && required) {
  console.error(
    `Amplify outputs did not include required auth values: ${missingAuth
      .map(([name]) => name)
      .join(', ')}.`,
  );
  process.exit(1);
}

const lines = [`VITE_API_BASE_URL=${endpoint.replace(/\/$/, '')}`];
if (userPoolId && typeof userPoolId === 'string') {
  lines.push(`VITE_AUTH_USER_POOL_ID=${userPoolId}`);
}
if (userPoolClientId && typeof userPoolClientId === 'string') {
  lines.push(`VITE_AUTH_USER_POOL_CLIENT_ID=${userPoolClientId}`);
}
if (region && typeof region === 'string') {
  lines.push(`VITE_AWS_REGION=${region}`);
}

mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(outPath, `${lines.join('\n')}\n`, 'utf8');
console.log(`Wrote UI API env to ${outPath}`);

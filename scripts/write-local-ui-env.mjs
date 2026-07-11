import { mkdirSync, writeFileSync } from 'node:fs';
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

const apiBaseUrl = String(args.get('--api-base-url') ?? 'http://127.0.0.1:8000');
const outPath = resolve(String(args.get('--out') ?? 'ui/.env.local'));
const lines = [
  `VITE_API_BASE_URL=${apiBaseUrl.replace(/\/$/, '')}`,
  '# Cognito vars are intentionally omitted for local unauthenticated mode.',
];

mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(outPath, `${lines.join('\n')}\n`, 'utf8');
console.log(`Wrote local UI env to ${outPath}`);

/**
 * Create initial TrucCompression bounty issues.
 *   node scripts/create-bounties.mjs
 *   node scripts/create-bounties.mjs --dry-run
 */
import { execSync } from 'node:child_process';

const dry = process.argv.includes('--dry-run');
const REPO = 'mergeos-bounties/TrucCompression';

const issues = [
  {
    title: '[25 MRG] Fixture pack: 5 corpus samples + expected ratio smoke',
    labels: ['bounty', 'bounty: feature', 'good first issue', 'reward:25-mrg', 'data'],
    body: `## Goal
Add five small binary fixtures under \`data/samples/\` (zeros, const, repeat, text, ramp) and a pytest that compresses each with \`fast=True\` and asserts round-trip + compressed size bounds.

## Acceptance
- [ ] Fixtures committed (no secrets)
- [ ] Test green on CI
- [ ] README samples path still accurate
`,
  },
  {
    title: '[50 MRG] Op: RLE opcode with encode/decode + unit tests',
    labels: ['bounty', 'bounty: feature', 'reward:50-mrg', 'codec'],
    body: `## Goal
Add a reversible RLE-style opcode to MFC (new opcode id, encode candidate, decode path). Must not break existing containers.

## Acceptance
- [ ] New opcode documented in README table
- [ ] Round-trip tests for RLE-friendly and non-RLE data
- [ ] Demo still passes
`,
  },
  {
    title: '[50 MRG] CLI: progress bar + JSON report export for compress',
    labels: ['bounty', 'bounty: feature', 'reward:50-mrg', 'cli'],
    body: `## Goal
Improve \`truccompression compress\` with optional \`--json-report path\` and rich progress for multi-block files.

## Acceptance
- [ ] Flags documented in README CLI table
- [ ] Tests cover JSON report shape
- [ ] No network required
`,
  },
  {
    title: '[100 MRG] Pages demo: browser WASM/pure-JS mini encode of small buffers',
    labels: ['bounty', 'bounty: feature', 'reward:100-mrg', 'web'],
    body: `## Goal
Extend GitHub Pages (\`docs/\`) with an interactive mini-demo that encodes a small typed buffer client-side (pure JS port of CONST/REPEAT/RAW/ZLIB via CompressionStream if available).

## Acceptance
- [ ] Works offline after first load
- [ ] No secrets / no backend
- [ ] Accessible UI (keyboard + contrast)
`,
  },
  {
    title: '[25 MRG] Docs: architecture diagram for MFC container layout',
    labels: ['bounty', 'bounty: feature', 'good first issue', 'reward:25-mrg', 'documentation'],
    body: `## Goal
Add \`docs/diagrams/\` SVG (or HTML) describing MFC file header + block record layout. Link from README Diagrams section.

## Acceptance
- [ ] Full-width diagram linked in README
- [ ] Accurate field sizes from \`codec.py\` structs
`,
  },
];

function sh(cmd) {
  return execSync(cmd, { encoding: 'utf8' }).trim();
}

function ensureLabel(name, color, description) {
  try {
    sh(
      `gh label create ${JSON.stringify(name)} --repo ${REPO} --color ${color} --description ${JSON.stringify(description)}`,
    );
  } catch {
    /* exists */
  }
}

const labels = [
  ['bounty', '5319E7', 'MergeOS bounty'],
  ['bounty: feature', 'A2EEEF', 'Feature bounty'],
  ['reward:25-mrg', 'FEF2C0', '25 MRG'],
  ['reward:50-mrg', 'FEF2C0', '50 MRG'],
  ['reward:100-mrg', 'FEF2C0', '100 MRG'],
  ['good first issue', '7057FF', 'Newcomer friendly'],
  ['codec', '0E8A16', 'Codec core'],
  ['cli', '1D76DB', 'CLI'],
  ['web', 'FBCA04', 'Pages / web'],
  ['data', 'C5DEF5', 'Fixtures'],
  ['documentation', '0075CA', 'Docs'],
];

for (const [n, c, d] of labels) ensureLabel(n, c, d);

for (const issue of issues) {
  const labelFlags = issue.labels.map((l) => `--label ${JSON.stringify(l)}`).join(' ');
  const bodyFile = `${process.env.TEMP || '/tmp'}/tc-issue-body.md`;
  const fs = await import('node:fs');
  fs.writeFileSync(bodyFile, issue.body, 'utf8');
  const cmd = `gh issue create --repo ${REPO} --title ${JSON.stringify(issue.title)} --body-file ${JSON.stringify(bodyFile)} ${labelFlags}`;
  if (dry) {
    console.log('[dry-run]', issue.title);
    continue;
  }
  console.log(sh(cmd));
}
console.log('done', issues.length);

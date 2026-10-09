// update_cost_map.mjs
// Refresh the CommandCode model entries in custom_cost_map.json from the live
// catalog.
//
// The file is not uniformly pretty-printed (nested objects are inlined and the
// number formatting is idiosyncratic), so we do NOT re-serialize the whole file.
// We surgically replace only the contiguous CommandCode block (identified by
// source === CC_SOURCE) and leave every other byte untouched.
//
//   node update_cost_map.mjs
import fs from 'node:fs';
import https from 'node:https';

const COST_MAP = 'custom_cost_map.json';
const MODELS_MD =
  'https://cdn.jsdelivr.net/npm/command-code@latest/dist/bundled/command-code-knowledge/reference/models.md';
const API_MODELS = 'https://api.commandcode.ai/provider/v1/models';
const CC_SOURCE = 'https://commandcode.ai/models';

function httpGet(url, headers = {}) {
  return new Promise((resolve, reject) => {
    https
      .get(url, { headers: { 'User-Agent': 'cost-map-updater', ...headers } }, (res) => {
        let d = '';
        res.on('data', (c) => (d += c));
        res.on('end', () => resolve({ status: res.statusCode, body: d }));
      })
      .on('error', reject);
  });
}

function envKey() {
  if (process.env.COMMANDCODE_API_KEY) return process.env.COMMANDCODE_API_KEY;
  try {
    for (const line of fs.readFileSync('.env', 'utf8').split(/\r?\n/)) {
      const m = line.match(/^\s*COMMANDCODE_API_KEY\s*=\s*(.+?)\s*$/);
      if (m) return m[1];
    }
  } catch {
    /* no .env */
  }
  return null;
}

function parseContext(s) {
  const m = /^([\d.]+)\s*([KM])?$/i.exec((s || '').trim().replace(/,/g, ''));
  if (!m) return null;
  let v = parseFloat(m[1]);
  const u = (m[2] || '').toUpperCase();
  if (u === 'K') v *= 1e3;
  else if (u === 'M') v *= 1e6;
  return Math.round(v);
}

function perToken(perMillion) {
  return Number((perMillion / 1e6).toPrecision(12));
}

function sortedEntry(raw) {
  return Object.fromEntries(Object.entries(raw).sort(([a], [b]) => (a < b ? -1 : 1)));
}

// Find the `{ ... }` span that starts at/after the value of `"key":`.
function matchBrace(s, openIdx) {
  let depth = 0;
  let inStr = false;
  let esc = false;
  for (let i = openIdx; i < s.length; i++) {
    const c = s[i];
    if (inStr) {
      if (esc) esc = false;
      else if (c === '\\') esc = true;
      else if (c === '"') inStr = false;
    } else if (c === '"') inStr = true;
    else if (c === '{' || c === '[') depth++;
    else if (c === '}' || c === ']') {
      depth--;
      if (depth === 0) return i;
    }
  }
  return -1;
}

// [lineStart, closeBrace+1] for a top-level "key": {...} entry.
function entrySpan(text, key) {
  const tok = '"' + key + '"';
  const ki = text.indexOf(tok);
  if (ki === -1) return null;
  const colon = text.indexOf(':', ki + tok.length);
  const brace = text.indexOf('{', colon);
  const end = matchBrace(text, brace);
  if (brace === -1 || end === -1) return null;
  const lineStart = text.lastIndexOf('\n', ki) + 1;
  return [lineStart, end + 1];
}

function entryText(key, entry) {
  const body = JSON.stringify(entry, null, 4)
    .split('\n')
    .map((l, i) => (i === 0 ? l : '    ' + l))
    .join('\n');
  return '    ' + JSON.stringify(key) + ': ' + body;
}

async function buildEntries(rows, endpoints, ctxById) {
  const entries = {};
  let skipped = 0;
  for (const row of rows) {
    const cols = row
      .trim()
      .replace(/^\|/, '')
      .replace(/\|$/, '')
      .split('|')
      .map((c) => c.trim());
    if (cols.length < 6) continue;
    const id = (cols[0].match(/`([^`]+)`/) || [])[1];
    if (!id) continue;

    const priceCol = cols[4] || '';
    let inP = null;
    let outP = null;
    let crP = null;
    let cwP = null;
    if (/free/i.test(priceCol)) {
      inP = 0;
      outP = 0;
    } else {
      const io = priceCol.match(/\$([\d.]+)\s*\/\s*\$([\d.]+)/);
      if (io) {
        inP = parseFloat(io[1]);
        outP = parseFloat(io[2]);
      }
      const cr = priceCol.match(/cache\s*\$([\d.]+)/);
      if (cr) crP = parseFloat(cr[1]);
      const cw = priceCol.match(/\(write\s*\$([\d.]+)\)/);
      if (cw) cwP = parseFloat(cw[1]);
    }
    if (inP === null && outP === null) {
      skipped++;
      continue;
    }

    const ctx = ctxById[id] || parseContext(cols[2]) || 0;
    const provider = (endpoints[id] || []).includes('/messages') ? 'anthropic' : 'openai';
    const raw = {
      input_cost_per_token: perToken(inP ?? 0),
      output_cost_per_token: perToken(outP ?? 0),
      cache_read_input_token_cost: perToken(crP ?? 0),
      litellm_provider: provider,
      max_input_tokens: ctx,
      max_output_tokens: ctx,
      max_tokens: ctx,
      mode: 'chat',
      source: CC_SOURCE,
    };
    if (cwP !== null) raw.cache_creation_input_token_cost = perToken(cwP);
    entries[`${provider}/${id}`] = sortedEntry(raw);
  }
  return { entries, skipped };
}

async function main() {
  const key = envKey();
  const [md, api] = await Promise.all([
    httpGet(MODELS_MD),
    key ? httpGet(API_MODELS, { Authorization: `Bearer ${key}` }) : Promise.resolve({ body: '{}' }),
  ]);

  const endpoints = {};
  const ctxById = {};
  try {
    for (const m of JSON.parse(api.body).data || []) {
      endpoints[m.id] = m.supported_endpoints || [];
      ctxById[m.id] = m.context_length;
    }
  } catch {
    /* no api data */
  }

  const rows = md.body.split(/\r?\n/).filter((l) => l.trim().startsWith('| `'));
  const { entries, skipped } = await buildEntries(rows, endpoints, ctxById);

  const text = fs.readFileSync(COST_MAP, 'utf8');
  const parsed = JSON.parse(text);

  // existing CommandCode keys (in the file) + any orphans we should preserve
  const existingCC = Object.keys(parsed).filter(
    (k) => parsed[k] && parsed[k].source === CC_SOURCE,
  );
  const merged = {};
  for (const k of existingCC) merged[k] = parsed[k];
  let added = 0;
  let updated = 0;
  for (const [k, e] of Object.entries(entries)) {
    if (k in merged) {
      if (JSON.stringify(merged[k]) !== JSON.stringify(e)) updated++;
    } else {
      added++;
    }
    merged[k] = e;
  }

  const spans = existingCC.map((k) => entrySpan(text, k)).filter(Boolean);
  if (!spans.length) throw new Error('could not locate the CommandCode block');
  const regionStart = Math.min(...spans.map((s) => s[0]));
  const regionEnd = Math.max(...spans.map((s) => s[1]));

  const block = Object.keys(merged)
    .sort()
    .map((k) => entryText(k, merged[k]))
    .join(',\n');

  const out = text.slice(0, regionStart) + block + text.slice(regionEnd);

  JSON.parse(out); // validate before writing
  fs.writeFileSync(COST_MAP, out);

  console.log(`catalog rows parsed : ${rows.length}`);
  console.log(`entries built       : ${Object.keys(entries).length} (skipped no-price: ${skipped})`);
  console.log(`added / updated     : ${added} / ${updated}`);
  console.log(`CommandCode entries : ${Object.keys(merged).length}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

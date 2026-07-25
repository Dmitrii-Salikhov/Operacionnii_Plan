#!/usr/bin/env node
/** Zip electron-builder win-unpacked like Slice. */
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '..');
const unpacked = path.join(root, 'desktop', 'release', 'win-unpacked');
const outZip = path.join(root, 'desktop', 'release', 'PlanOperaciy-Windows.zip');

if (!fs.existsSync(unpacked)) {
  console.error('Missing', unpacked);
  process.exit(1);
}

if (fs.existsSync(outZip)) fs.unlinkSync(outZip);

const r = spawnSync(
  'powershell.exe',
  [
    '-NoProfile',
    '-Command',
    `Compress-Archive -Path '${unpacked}\\*' -DestinationPath '${outZip}' -Force`,
  ],
  { stdio: 'inherit' },
);
if (r.status !== 0) process.exit(r.status || 1);
console.log('Wrote', outZip);

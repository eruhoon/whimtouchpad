import fs from 'node:fs';
import path from 'node:path';

const ROOT_DIR = process.cwd();
const DIST_DIR = path.join(ROOT_DIR, 'dist');
const TEMPLATE_BIN = path.join(ROOT_DIR, 'template', 'whimtouchpad');

if (fs.existsSync(DIST_DIR)) {
  fs.rmSync(DIST_DIR, { recursive: true, force: true });
}

if (fs.existsSync(TEMPLATE_BIN)) {
  fs.rmSync(TEMPLATE_BIN, { force: true });
}

console.log('[whimtouchpad] Clean completed.');

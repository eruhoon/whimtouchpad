import fs from 'node:fs';
import path from 'node:path';

const ROOT_DIR = process.cwd();
const pkg = JSON.parse(fs.readFileSync(path.join(ROOT_DIR, 'package.json'), 'utf-8'));

// 1. 버전 4자리 형식 검증 (Major.Minor.Patch.Revision)
const versionPattern = /^\d+\.\d+\.\d+\.\d+$/;
if (!versionPattern.test(pkg.version)) {
  console.error(`[test] Version format error: "${pkg.version}" does not match Major.Minor.Patch.Revision (e.g. 0.1.0.0)`);
  process.exit(1);
}

// 2. 주요 필수 파일 존재 여부 검증
const requiredFiles = [
  'GEMINI.md',
  'PLAN.md',
  'package.json',
  'scripts/build.mjs',
  'scripts/clean.mjs',
  'src/main.c',
  'src/uinput.c',
  'src/uinput.h',
  'template/whimpad.sh',
  'template/conf/config.json',
  '.github/workflows/release.yml'
];

for (const file of requiredFiles) {
  const filePath = path.join(ROOT_DIR, file);
  if (!fs.existsSync(filePath)) {
    console.error(`[test] Missing required file: ${file}`);
    process.exit(1);
  }
}

console.log(`[test] All pre-flight tests passed for whimtouchpad v${pkg.version}`);

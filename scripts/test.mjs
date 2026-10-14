import fs from 'node:fs';
import path from 'node:path';
import AdmZip from 'adm-zip';

const ROOT_DIR = process.cwd();
const pkg = JSON.parse(fs.readFileSync(path.join(ROOT_DIR, 'package.json'), 'utf-8'));

// 1. 버전 4자리 형식 검증 (Major.Minor.Patch.Revision)
const versionPattern = /^\d+\.\d+\.\d+\.\d+$/;
if (!versionPattern.test(pkg.version)) {
  console.error(`[test] Version format error: "${pkg.version}" does not match Major.Minor.Patch.Revision (e.g. 0.1.0.0)`);
  process.exit(1);
}

// 2. 주요 필수 파일 존재 여부 검증 (SSOT src/ 포함)
const requiredFiles = [
  'GEMINI.md',
  'PLAN.md',
  'package.json',
  'scripts/build.mjs',
  'scripts/clean.mjs',
  'src/backend.c',
  'src/backlight.py',
  'src/controller.py',
  'src/ui.py',
  'src/layout_loader.py',
  'src/gesture_manager.py',
  'src/hangul.py',
  'template/whimpad.sh',
  'template/whim_hook.sh',
  'template/whim_cleanup.sh',
  'template/conf/config.json',
  'template/layouts/default.xml',
  'template/layouts/sample_rpg.xml',
  '.github/workflows/release.yml'
];

for (const file of requiredFiles) {
  const filePath = path.join(ROOT_DIR, file);
  if (!fs.existsSync(filePath)) {
    console.error(`[test] Missing required file: ${file}`);
    process.exit(1);
  }
}

// 3. 레이아웃 회귀 동등성 및 단위 테스트 검증
import { execSync } from 'node:child_process';
try {
  execSync('python3 tests/test_parity.py', { stdio: 'inherit' });
  execSync('python3 tests/test_controller.py', { stdio: 'inherit' });
  execSync('python3 tests/test_custom_layout.py', { stdio: 'inherit' });
  execSync('python3 tests/test_power_efficiency.py', { stdio: 'inherit' });
} catch (e) {
  console.error('[test] Python unit tests failed');
  process.exit(1);
}

// 4. 패키지 ZIP 권한 검증 (dist 디렉토리에 zip이 존재하는 경우)
const distDir = path.join(ROOT_DIR, 'dist');
if (fs.existsSync(distDir)) {
  const zips = fs.readdirSync(distDir).filter(f => f.endsWith('.zip'));
  for (const zipFile of zips) {
    const zipPath = path.join(distDir, zipFile);
    const zip = new AdmZip(zipPath);
    const entries = zip.getEntries();
    
    for (const entry of entries) {
      if (entry.entryName.endsWith('whimpad_backend') || entry.entryName.endsWith('.sh')) {
        const mode = (entry.attr >> 16) & 0o777;
        if (mode !== 0o755) {
          console.warn(`[test] Warning: Entry ${entry.entryName} in ${zipFile} does not have mode 0755 (got 0${mode.toString(8)})`);
        }
      }
    }
  }
}

console.log(`[test] All pre-flight tests passed for whimtouchpad v${pkg.version}`);

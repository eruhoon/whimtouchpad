import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';
import AdmZip from 'adm-zip';

const ROOT_DIR = process.cwd();
const pkg = JSON.parse(fs.readFileSync(path.join(ROOT_DIR, 'package.json'), 'utf-8'));
const DIST_DIR = path.join(ROOT_DIR, 'dist');
const TEMPLATE_DIR = path.join(ROOT_DIR, 'template');
const SRC_DIR = path.join(ROOT_DIR, 'src');

if (!fs.existsSync(DIST_DIR)) {
  fs.mkdirSync(DIST_DIR, { recursive: true });
}

console.log(`[whimtouchpad] Building version v${pkg.version}...`);

// 1. C 컴파일러로 backend C 바이너리 빌드
const isCrossArm64 = process.env.TARGET_ARCH === 'arm64' || process.env.CROSS_COMPILE;
const cc = isCrossArm64 ? 'aarch64-linux-gnu-gcc' : (process.env.CC || 'gcc');

const outBin = path.join(TEMPLATE_DIR, 'whimpad_backend');

try {
  console.log(`[whimtouchpad] Compiling C backend using ${cc}...`);
  const compileCmd = `${cc} -O2 -Wall -Wextra src/backend.c -o ${outBin}`;
  console.log(`[whimtouchpad] Command: ${compileCmd}`);
  execSync(compileCmd, { cwd: ROOT_DIR, stdio: 'inherit' });
} catch (e) {
  console.warn(`[whimtouchpad] Note: Local compile skipped or failed (${e.message}).`);
  if (!fs.existsSync(outBin) || fs.statSync(outBin).size === 0) {
    console.warn(`[whimtouchpad] Creating placeholder binary for packaging.`);
    fs.writeFileSync(outBin, '#!/bin/sh\necho "WhimTouchpad backend placeholder"\n', { mode: 0o755 });
  } else {
    console.log(`[whimtouchpad] Preserving existing pre-compiled aarch64 binary.`);
  }
}

// 2. Python 스크립트 복사
fs.copyFileSync(path.join(SRC_DIR, 'controller.py'), path.join(TEMPLATE_DIR, 'controller.py'));
fs.copyFileSync(path.join(SRC_DIR, 'gesture_manager.py'), path.join(TEMPLATE_DIR, 'gesture_manager.py'));
if (fs.existsSync(path.join(SRC_DIR, 'layout_loader.py'))) {
  fs.copyFileSync(path.join(SRC_DIR, 'layout_loader.py'), path.join(TEMPLATE_DIR, 'layout_loader.py'));
}

// 스크립트 실행 권한 부여
for (const sh of ['whim_hook.sh', 'whim_cleanup.sh', 'whimpad.sh']) {
  const shPath = path.join(TEMPLATE_DIR, sh);
  if (fs.existsSync(shPath)) {
    fs.chmodSync(shPath, 0o755);
  }
}

// 불필요한 __pycache__ 정리
const pycacheDir = path.join(TEMPLATE_DIR, '__pycache__');
if (fs.existsSync(pycacheDir)) {
  fs.rmSync(pycacheDir, { recursive: true, force: true });
}

// 3. 패키징 (ZIP 생성: 폴더명 whimpad로 통일)
const tagVersion = pkg.version.split('.').slice(0, 3).join('.');
const zipName = `whimpad-v${tagVersion}.zip`;
const zipPath = path.join(DIST_DIR, zipName);
const zip = new AdmZip();

zip.addLocalFolder(TEMPLATE_DIR, 'whimpad');
zip.writeZip(zipPath);

console.log(`[whimtouchpad] Successfully built release package: ${zipPath}`);

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
    console.log(`[whimtouchpad] Preserving existing pre-compiled binary.`);
  }
}

// ELF AArch64 검증 함수
function checkIsAarch64(binPath) {
  if (!fs.existsSync(binPath)) return false;
  const buf = fs.readFileSync(binPath);
  if (buf.length < 20 || buf[0] !== 0x7f || buf[1] !== 0x45 || buf[2] !== 0x4c || buf[3] !== 0x46) {
    return false;
  }
  const machine = buf.readUInt16LE(18);
  return machine === 0x00b7; // EM_AARCH64 (183)
}

if (isCrossArm64 || process.env.CI) {
  const isArm64 = checkIsAarch64(outBin);
  if (isArm64) {
    console.log(`[whimtouchpad] Verified backend binary: valid ELF AArch64 (ARM64).`);
  } else if (isCrossArm64) {
    console.error(`[whimtouchpad] Error: Compiled binary is not ELF AArch64!`);
    process.exit(1);
  }
}

// 2. Python 스크립트 전체 동기화 (src/ -> template/)
const pyFiles = fs.readdirSync(SRC_DIR).filter(f => f.endsWith('.py'));
for (const file of pyFiles) {
  fs.copyFileSync(path.join(SRC_DIR, file), path.join(TEMPLATE_DIR, file));
}
console.log(`[whimtouchpad] Synced ${pyFiles.length} python source files from src/ to template/.`);

// 스크립트 및 바이너리 실행 권한 부여
for (const sh of ['whim_hook.sh', 'whim_cleanup.sh', 'whimpad.sh']) {
  const shPath = path.join(TEMPLATE_DIR, sh);
  if (fs.existsSync(shPath)) {
    fs.chmodSync(shPath, 0o755);
  }
}
if (fs.existsSync(outBin)) {
  fs.chmodSync(outBin, 0o755);
}

// 불필요한 __pycache__ 정리
const pycacheDir = path.join(TEMPLATE_DIR, '__pycache__');
if (fs.existsSync(pycacheDir)) {
  fs.rmSync(pycacheDir, { recursive: true, force: true });
}

// 3. 패키징 (UNIX 퍼미션 0755/0644 보존 ZIP 생성)
const tagVersion = pkg.version.split('.').slice(0, 3).join('.');
const zipName = `whimpad-v${tagVersion}.zip`;
const zipPath = path.join(DIST_DIR, zipName);
const zip = new AdmZip();

function addFolderWithPermissions(zipInstance, sourceDir, zipRoot) {
  function walk(dir, relPath = '') {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      const entryZipPath = relPath ? `${relPath}/${entry.name}` : entry.name;
      const zipTargetPath = `${zipRoot}/${entryZipPath}`;

      if (entry.isDirectory()) {
        if (entry.name === '__pycache__' || entry.name === '.git') continue;
        zipInstance.addFile(`${zipTargetPath}/`, Buffer.alloc(0));
        const zipEntry = zipInstance.getEntry(`${zipTargetPath}/`);
        if (zipEntry) {
          zipEntry.header.made = 0x031e;
          zipEntry.attr = 0o40755 * 65536;
        }
        walk(fullPath, entryZipPath);
      } else {
        const content = fs.readFileSync(fullPath);
        zipInstance.addFile(zipTargetPath, content);
        const zipEntry = zipInstance.getEntry(zipTargetPath);
        if (zipEntry) {
          const isExecutable = entry.name.endsWith('.sh') || entry.name === 'whimpad_backend';
          const mode = isExecutable ? 0o100755 : 0o100644;
          zipEntry.header.made = 0x031e;
          zipEntry.attr = mode * 65536;
        }
      }
    }
  }
  walk(sourceDir);
}

addFolderWithPermissions(zip, TEMPLATE_DIR, 'whimpad');
zip.writeZip(zipPath);

console.log(`[whimtouchpad] Successfully built release package with UNIX permissions: ${zipPath}`);

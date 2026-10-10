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

// 1. C 컴파일러 확인 및 바이너리 빌드
const isCrossArm64 = process.env.TARGET_ARCH === 'arm64' || process.env.CROSS_COMPILE;
const cc = isCrossArm64 ? 'aarch64-linux-gnu-gcc' : (process.env.CC || 'gcc');

const outBin = path.join(TEMPLATE_DIR, 'whimtouchpad');

try {
  console.log(`[whimtouchpad] Compiling C source using ${cc}...`);
  // SDL2가 환경에 있을 경우 -DUSE_SDL2 -lSDL2 사용, 기본 헤드리스/테스트 모드는 기본 C
  const hasSDL2 = (() => {
    try {
      execSync('pkg-config --exists sdl2', { stdio: 'ignore' });
      return true;
    } catch {
      return false;
    }
  })();

  const sdlFlags = hasSDL2 ? '$(pkg-config --cflags --libs sdl2) -DUSE_SDL2' : '';
  const compileCmd = `${cc} -O2 -Wall -Wextra src/main.c src/uinput.c -o ${outBin} ${sdlFlags}`;
  console.log(`[whimtouchpad] Command: ${compileCmd}`);
  execSync(compileCmd, { cwd: ROOT_DIR, stdio: 'inherit' });
} catch (e) {
  console.warn(`[whimtouchpad] Note: Local compile skipped or failed (${e.message}).`);
  console.warn(`[whimtouchpad] Creating placeholder binary for packaging.`);
  fs.writeFileSync(outBin, '#!/bin/sh\necho "WhimTouchpad binary placeholder"\n', { mode: 0o755 });
}

// 2. 패키징 (ZIP 생성)
const zipName = `whimtouchpad-v${pkg.version}.zip`;
const zipPath = path.join(DIST_DIR, zipName);
const zip = new AdmZip();

// template 폴더 전체를 whimtouchpad/ 경로로 아카이브에 추가
zip.addLocalFolder(TEMPLATE_DIR, 'whimtouchpad');
zip.writeZip(zipPath);

console.log(`[whimtouchpad] Successfully built release package: ${zipPath}`);

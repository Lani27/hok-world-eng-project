'use strict';
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const os = require('os');
const asar = require('./asar');

const IS_SEA = (() => { try { return require('node:sea').isSea(); } catch { return false; } })();
const EXE_PATH = process.execPath;
const UNINSTALL_MODE = process.argv.includes('--uninstall');

const LOG_FILE = path.join(os.homedir(), 'eng_patch_install.log');
function log(msg) {
  console.log('  ' + msg);
  try { fs.appendFileSync(LOG_FILE, msg + '\n'); } catch {}
}
function header(title) {
  console.log('');
  console.log('  ===================================================');
  console.log('   ' + title);
  console.log('  ===================================================');
  console.log('');
}
function pause() {
  try { execSync('pause', { stdio: 'inherit' }); } catch {}
}
function fatal(msg) {
  console.log('');
  log('ERROR: ' + msg);
  console.log('');
  pause();
  process.exit(1);
}

// Check if running as admin
function isAdmin() {
  try {
    execSync('net session', { stdio: 'ignore' });
    return true;
  } catch { return false; }
}

// Re-launch as admin
function elevate() {
  log('Requesting administrator privileges...');
  const args = process.argv.slice(1).map(a => `'${a}'`).join(',');
  const cmd = IS_SEA
    ? `Start-Process '${EXE_PATH}' -ArgumentList ${args || "''"} -Verb RunAs`
    : `Start-Process node -ArgumentList '${process.argv[1]}',${args || "''"} -Verb RunAs`;
  try {
    execSync(`powershell -Command "${cmd}"`, { stdio: 'ignore' });
  } catch {}
  process.exit(0);
}

// Open folder picker dialog, returns path or null
function pickFolder(description) {
  try {
    const ps = `Add-Type -AssemblyName System.Windows.Forms; $f = New-Object System.Windows.Forms.FolderBrowserDialog; $f.Description = '${description}'; $f.ShowNewFolderButton = $false; if ($f.ShowDialog() -eq 'OK') { $f.SelectedPath } else { '' }`;
    const result = execSync(`powershell -Command "${ps}"`, { encoding: 'utf8' }).trim();
    return result || null;
  } catch { return null; }
}

// Find the KingLauncher base directory
function findKingBase() {
  const defaultPath = 'C:\\Program Files\\KingLauncher';
  if (fs.existsSync(defaultPath)) return defaultPath;
  return null;
}

// Find version subdirectory with app.asar
function findLauncherDir(kingBase) {
  if (!fs.existsSync(kingBase)) return null;
  const dirs = fs.readdirSync(kingBase).filter(d => {
    const p = path.join(kingBase, d);
    return fs.statSync(p).isDirectory() && fs.existsSync(path.join(p, 'resources', 'app.asar'));
  });
  if (dirs.length === 0) return null;
  dirs.sort();
  return path.join(kingBase, dirs[dirs.length - 1]);
}

// Validate that a path looks like a KingLauncher directory
function validateKingBase(dir) {
  if (!fs.existsSync(dir)) return false;
  return findLauncherDir(dir) !== null;
}

// Get the launcher directory, with folder picker fallback
function getLauncherDir() {
  let kingBase = findKingBase();

  if (!kingBase) {
    log('KingLauncher not found at the default location.');
    log('Please select your KingLauncher folder.');
    console.log('');
    log('IMPORTANT: Select the "KingLauncher" folder itself,');
    log('NOT a subfolder inside it.');
    console.log('');

    kingBase = pickFolder('Select your KingLauncher folder');
    if (!kingBase) fatal('No folder selected. Operation cancelled.');
  }

  const launcherDir = findLauncherDir(kingBase);
  if (!launcherDir) {
    fatal(
      'Invalid KingLauncher folder!\n\n' +
      '  Could not find a valid installation in:\n' +
      '    ' + kingBase + '\n\n' +
      '  Make sure you selected the correct "KingLauncher" folder.\n' +
      '  Use the official Windows PC launcher from https://world.qq.com/\n' +
      '  The WeGame launcher is NOT supported.'
    );
  }

  return launcherDir;
}

// Kill the launcher process
function killLauncher() {
  try { execSync('taskkill /f /im "\u738b\u8005\u8363\u8000\u4e16\u754c.exe"', { stdio: 'ignore' }); } catch {}
}

// Get patch file content (from SEA assets or from disk)
function getPatchFile(name) {
  if (IS_SEA) {
    const sea = require('node:sea');
    // sea.getAsset() returns ArrayBuffer, convert to Buffer for fs.writeFileSync
    return Buffer.from(sea.getAsset(name));
  }
  // Dev mode: read from patch_files/
  const p = path.join(__dirname, '..', 'patch_files', name);
  return fs.readFileSync(p);
}

// ============ INSTALL ============
function install() {
  header('Honor of Kings: World - English Patch Installer');

  if (!isAdmin()) elevate();

  const launcherDir = getLauncherDir();
  log('Found launcher: ' + launcherDir);

  killLauncher();

  const resources = path.join(launcherDir, 'resources');
  const asarPath = path.join(resources, 'app.asar');
  const backupPath = asarPath + '.original';
  const tmpDir = path.join(os.tmpdir(), 'kl_eng_patch_tmp');
  const tmpAsar = path.join(os.tmpdir(), 'kl_eng_patched.asar');

  // Backup
  if (!fs.existsSync(backupPath)) {
    log('Backing up original app.asar...');
    fs.copyFileSync(asarPath, backupPath);
  }

  // Extract
  log('Extracting app.asar... (this may take a moment)');
  log('  Source: ' + asarPath);
  log('  Temp: ' + tmpDir);
  if (fs.existsSync(tmpDir)) fs.rmSync(tmpDir, { recursive: true, force: true });
  asar.extract(asarPath, tmpDir);
  log('  Extraction complete.');

  if (!fs.existsSync(path.join(tmpDir, 'package.json'))) {
    fatal('Failed to extract app.asar');
  }

  // Apply patch files
  log('Applying English patch...');
  log('  Loading patch files...');
  const mainPatch = getPatchFile('main.92fa614d.js');
  log('  main.92fa614d.js: ' + mainPatch.length + ' bytes');
  const rendererPatch = getPatchFile('eng_patch_renderer.js');
  log('  eng_patch_renderer.js: ' + rendererPatch.length + ' bytes');
  fs.writeFileSync(path.join(tmpDir, 'main.92fa614d.js'), mainPatch);
  fs.writeFileSync(path.join(tmpDir, 'eng_patch_renderer.js'), rendererPatch);

  // Repack
  log('Repacking app.asar... (this may take a moment)');
  if (fs.existsSync(tmpAsar)) fs.unlinkSync(tmpAsar);
  const tmpAsarUnpacked = tmpAsar + '.unpacked';
  if (fs.existsSync(tmpAsarUnpacked)) fs.rmSync(tmpAsarUnpacked, { recursive: true, force: true });
  asar.pack(tmpDir, tmpAsar, ['game', 'node_modules']);

  if (!fs.existsSync(tmpAsar)) {
    fatal('Failed to repack app.asar');
  }

  // Deploy
  log('Installing...');
  fs.copyFileSync(tmpAsar, asarPath);

  // Copy unpacked directory
  const destUnpacked = path.join(resources, 'app.asar.unpacked');
  if (fs.existsSync(destUnpacked)) fs.rmSync(destUnpacked, { recursive: true, force: true });
  if (fs.existsSync(tmpAsarUnpacked)) {
    copyDirRecursive(tmpAsarUnpacked, destUnpacked);
  }

  // Cleanup
  log('Cleaning up...');
  try { fs.rmSync(tmpDir, { recursive: true, force: true }); } catch {}
  try { fs.unlinkSync(tmpAsar); } catch {}
  try { fs.rmSync(tmpAsarUnpacked, { recursive: true, force: true }); } catch {}

  header('English Patch installed successfully!');
  log('You can now launch the game normally.');
  log('If the launcher updates, just run this again.');
  console.log('');
  pause();
}

// ============ UNINSTALL ============
function uninstall() {
  header('Honor of Kings: World - Remove English Patch');

  if (!isAdmin()) elevate();

  const launcherDir = getLauncherDir();
  const resources = path.join(launcherDir, 'resources');
  const asarPath = path.join(resources, 'app.asar');
  const backupPath = asarPath + '.original';

  if (!fs.existsSync(backupPath)) {
    fatal('No backup found. The English patch may not be installed.');
  }

  killLauncher();

  log('Restoring original launcher...');
  fs.copyFileSync(backupPath, asarPath);

  header('English Patch removed');
  log('Launcher restored to Chinese.');
  console.log('');
  pause();
}

// Recursive directory copy
function copyDirRecursive(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src)) {
    const srcPath = path.join(src, entry);
    const destPath = path.join(dest, entry);
    if (fs.statSync(srcPath).isDirectory()) {
      copyDirRecursive(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

// Main
try { fs.writeFileSync(LOG_FILE, '=== English Patch Log ' + new Date().toISOString() + ' ===\n'); } catch {}
try {
  if (UNINSTALL_MODE) {
    uninstall();
  } else {
    install();
  }
} catch (err) {
  console.log('');
  log('UNEXPECTED ERROR:');
  log(err.message);
  log(err.stack || '');
  if (err.stack) {
    console.log('');
    console.log(err.stack);
  }
  console.log('');
  pause();
  process.exit(1);
}

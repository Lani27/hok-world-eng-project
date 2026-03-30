'use strict';
const fs = require('fs');
const path = require('path');
const https = require('https');
const readline = require('readline');
const { execSync } = require('child_process');
const os = require('os');
const asar = require('./asar');

const VERSION = 'v1.0.0';
const REPO = 'Lani27/hok-world-eng-project';
const IS_SEA = (() => { try { return require('node:sea').isSea(); } catch { return false; } })();
const EXE_PATH = process.execPath;
const UNINSTALL_MODE = process.argv.includes('--uninstall');
const SKIP_UPDATE = process.argv.includes('--skip-update');

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

// ============ UPDATE CHECK ============
function compareVersions(current, latest) {
  const parse = v => v.replace(/^v/, '').split('.').map(Number);
  const c = parse(current);
  const l = parse(latest);
  for (let i = 0; i < 3; i++) {
    if ((l[i] || 0) > (c[i] || 0)) return 1;
    if ((l[i] || 0) < (c[i] || 0)) return -1;
  }
  return 0;
}

function fetchLatestRelease() {
  return new Promise((resolve) => {
    const opts = {
      hostname: 'api.github.com',
      path: `/repos/${REPO}/releases/latest`,
      headers: { 'User-Agent': 'KingLauncher-EngPatch/' + VERSION },
      timeout: 5000
    };
    const req = https.get(opts, res => {
      let data = '';
      res.on('data', d => data += d);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); } catch { resolve(null); }
      });
    });
    req.on('error', () => resolve(null));
    req.on('timeout', () => { req.destroy(); resolve(null); });
  });
}

function askUser(question) {
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    const timer = setTimeout(() => { rl.close(); resolve('n'); }, 15000);
    rl.question(question, answer => {
      clearTimeout(timer);
      rl.close();
      resolve((answer || '').trim().toLowerCase());
    });
  });
}

async function checkForUpdate() {
  if (SKIP_UPDATE) return;
  log('Checking for updates... (current: ' + VERSION + ')');
  const release = await fetchLatestRelease();
  if (!release || !release.tag_name) {
    log('  Could not check for updates (no internet?)');
    return;
  }
  const latest = release.tag_name;
  if (compareVersions(VERSION, latest) <= 0) {
    log('  You have the latest version.');
    return;
  }
  // Find the exe asset download URL
  const asset = (release.assets || []).find(a => a.name.endsWith('.exe'));
  const downloadUrl = asset
    ? asset.browser_download_url
    : `https://github.com/${REPO}/releases/tag/${latest}`;

  console.log('');
  log('=== UPDATE AVAILABLE ===');
  log('  New version: ' + latest + ' (you have ' + VERSION + ')');
  if (release.name) log('  ' + release.name);
  console.log('');

  const answer = await askUser('  Download the new version? (Y/N): ');
  if (answer === 'y' || answer === 'yes') {
    log('Opening download page...');
    try { execSync(`start "" "${downloadUrl}"`, { stdio: 'ignore' }); } catch {}
    log('Download started in your browser. Please run the new version after downloading.');
    console.log('');
    pause();
    process.exit(0);
  }
  log('Continuing with current version...');
  console.log('');
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
(async () => {
  try { fs.writeFileSync(LOG_FILE, '=== English Patch Log ' + new Date().toISOString() + ' ===\n'); } catch {}
  try {
    await checkForUpdate();
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
})();

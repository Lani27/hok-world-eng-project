'use strict';
const fs = require('fs');
const path = require('path');
const http = require('http');
const https = require('https');
const { spawn, execSync } = require('child_process');
const os = require('os');
// Node 20+ has built-in WebSocket (global)

const VERSION = 'v1.0.0';
const REPO = 'Lani27/hok-world-eng-project';
const IS_SEA = (() => { try { return require('node:sea').isSea(); } catch { return false; } })();
const CDP_PORT = 19200 + Math.floor(Math.random() * 100);

function log(msg) { console.log('  [EngPatch] ' + msg); }

// Check if running as admin
function isAdmin() {
  try { execSync('net session', { stdio: 'ignore' }); return true; } catch { return false; }
}

function elevate() {
  log('Requesting administrator privileges...');
  const args = process.argv.slice(1).map(a => `'${a}'`).join(',');
  const cmd = IS_SEA
    ? `Start-Process '${process.execPath}' -ArgumentList ${args || "''"} -Verb RunAs`
    : `Start-Process node -ArgumentList '${process.argv[1]}',${args || "''"} -Verb RunAs`;
  try { execSync(`powershell -Command "${cmd}"`, { stdio: 'ignore' }); } catch {}
  process.exit(0);
}

// ============ FIND LAUNCHER ============
function findLauncherExe() {
  const base = 'C:\\Program Files\\KingLauncher';
  if (!fs.existsSync(base)) return null;
  const dirs = fs.readdirSync(base).filter(d => {
    const p = path.join(base, d);
    return fs.statSync(p).isDirectory() &&
      fs.existsSync(path.join(p, '\u738b\u8005\u8363\u8000\u4e16\u754c.exe'));
  });
  if (dirs.length === 0) return null;
  dirs.sort();
  return path.join(base, dirs[dirs.length - 1], '\u738b\u8005\u8363\u8000\u4e16\u754c.exe');
}

function pickFolder() {
  try {
    const ps = `Add-Type -AssemblyName System.Windows.Forms; $f = New-Object System.Windows.Forms.FolderBrowserDialog; $f.Description = 'Select your KingLauncher folder'; $f.ShowNewFolderButton = $false; if ($f.ShowDialog() -eq 'OK') { $f.SelectedPath } else { '' }`;
    const result = execSync(`powershell -Command "${ps}"`, { encoding: 'utf8' }).trim();
    if (!result) return null;
    // Find exe in selected folder
    const dirs = fs.readdirSync(result).filter(d => {
      const p = path.join(result, d);
      return fs.statSync(p).isDirectory() &&
        fs.existsSync(path.join(p, '\u738b\u8005\u8363\u8000\u4e16\u754c.exe'));
    });
    if (dirs.length === 0) return null;
    dirs.sort();
    return path.join(result, dirs[dirs.length - 1], '\u738b\u8005\u8363\u8000\u4e16\u754c.exe');
  } catch { return null; }
}

// ============ GET TRANSLATION SCRIPT ============
function getTranslationScript() {
  if (IS_SEA) {
    const sea = require('node:sea');
    return Buffer.from(sea.getAsset('eng_patch_renderer.js')).toString('utf8');
  }
  // Dev mode: read from launcher/patch_files/
  const p = path.join(__dirname, '..', '..', 'launcher', 'patch_files', 'eng_patch_renderer.js');
  return fs.readFileSync(p, 'utf8');
}

// ============ CDP FUNCTIONS ============
function httpGet(url) {
  return new Promise((resolve, reject) => {
    const req = http.get(url, res => {
      let data = '';
      res.on('data', d => data += d);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); } catch { reject(new Error('Invalid JSON')); }
      });
    });
    req.on('error', reject);
    req.setTimeout(3000, () => { req.destroy(); reject(new Error('timeout')); });
  });
}

function waitForCDP(port, timeoutMs) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    function poll() {
      if (Date.now() - start > timeoutMs) {
        return reject(new Error('CDP timeout: launcher did not start within ' + (timeoutMs / 1000) + 's'));
      }
      httpGet(`http://127.0.0.1:${port}/json`).then(targets => {
        const pages = targets.filter(t => t.type === 'page' && t.webSocketDebuggerUrl);
        if (pages.length > 0) resolve(pages);
        else setTimeout(poll, 500);
      }).catch(() => setTimeout(poll, 500));
    }
    poll();
  });
}

function injectViaWebSocket(wsUrl, script) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    let resolved = false;
    const timer = setTimeout(() => {
      if (!resolved) { resolved = true; try { ws.close(); } catch {} reject(new Error('WS timeout')); }
    }, 10000);

    ws.onopen = () => {
      ws.send(JSON.stringify({
        id: 1,
        method: 'Runtime.evaluate',
        params: { expression: script, returnByValue: false }
      }));
    };

    ws.onmessage = (event) => {
      try {
        const resp = JSON.parse(typeof event.data === 'string' ? event.data : event.data.toString());
        if (resp.id === 1) {
          clearTimeout(timer);
          resolved = true;
          ws.close();
          resolve(resp.result);
        }
      } catch {}
    };

    ws.onerror = (err) => {
      if (!resolved) { resolved = true; clearTimeout(timer); reject(err.error || new Error('WebSocket error')); }
    };
  });
}

// ============ MONITOR & INJECT ============
async function injectAll(port, script, injectedSet) {
  let targets;
  try {
    targets = await httpGet(`http://127.0.0.1:${port}/json`);
  } catch { return 0; }

  let count = 0;
  for (const t of targets) {
    if (t.type !== 'page' || !t.webSocketDebuggerUrl) continue;
    if (injectedSet.has(t.id)) continue;
    try {
      await injectViaWebSocket(t.webSocketDebuggerUrl, script);
      injectedSet.add(t.id);
      log('Injected into: ' + (t.title || t.url || t.id));
      count++;
    } catch (e) {
      log('Failed to inject into ' + (t.title || t.id) + ': ' + e.message);
    }
  }
  return count;
}

function isProcessRunning(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch { return false; }
}

// ============ UPDATE CHECK ============
function checkForUpdate() {
  return new Promise(resolve => {
    const opts = {
      hostname: 'api.github.com',
      path: `/repos/${REPO}/releases/latest`,
      headers: { 'User-Agent': 'KingLauncher-EngPatch-Wrapper/' + VERSION },
      timeout: 5000
    };
    const req = https.get(opts, res => {
      let data = '';
      res.on('data', d => data += d);
      res.on('end', () => {
        try {
          const r = JSON.parse(data);
          const latest = r.tag_name;
          if (latest && latest !== VERSION) {
            const parse = v => v.replace(/^v/, '').split('.').map(Number);
            const c = parse(VERSION), l = parse(latest);
            let newer = false;
            for (let i = 0; i < 3; i++) {
              if ((l[i] || 0) > (c[i] || 0)) { newer = true; break; }
              if ((l[i] || 0) < (c[i] || 0)) break;
            }
            if (newer) {
              log('Update available: ' + latest + ' (you have ' + VERSION + ')');
              log('Download from: https://github.com/' + REPO + '/releases/latest');
            }
          }
        } catch {}
        resolve();
      });
    });
    req.on('error', () => resolve());
    req.on('timeout', () => { req.destroy(); resolve(); });
  });
}

// ============ MAIN ============
async function main() {
  console.log('');
  console.log('  ===================================================');
  console.log('   Honor of Kings: World - English Patch (Wrapper)');
  console.log('   ' + VERSION);
  console.log('  ===================================================');
  console.log('');

  // Admin check
  if (!isAdmin()) elevate();

  // Update check (non-blocking, just logs)
  await checkForUpdate();

  // Find launcher
  let exePath = findLauncherExe();
  if (!exePath) {
    log('KingLauncher not found at default location.');
    log('Please select your KingLauncher folder.');
    exePath = pickFolder();
    if (!exePath) {
      log('ERROR: No launcher found. Exiting.');
      process.exit(1);
    }
  }
  log('Found launcher: ' + exePath);

  // Load translation script
  const script = getTranslationScript();
  log('Translation script loaded (' + script.length + ' bytes)');

  // Launch with CDP
  log('Starting launcher with debugging port ' + CDP_PORT + '...');
  const child = spawn(exePath, ['--remote-debugging-port=' + CDP_PORT], {
    detached: false,
    stdio: 'ignore',
    cwd: path.dirname(exePath)
  });

  child.on('error', err => {
    log('ERROR: Failed to start launcher: ' + err.message);
    process.exit(1);
  });

  // Wait for CDP to become available
  log('Waiting for launcher to start...');
  try {
    await waitForCDP(CDP_PORT, 30000);
  } catch (e) {
    log('ERROR: ' + e.message);
    log('The launcher may have failed to start or does not support debugging.');
    process.exit(1);
  }

  // Initial injection
  const injected = new Set();
  const count = await injectAll(CDP_PORT, script, injected);
  log('Initial injection: ' + count + ' page(s) translated');

  // Monitor for new pages and re-inject periodically
  log('Monitoring for new pages... (close this window to stop)');
  console.log('');

  const monitorInterval = setInterval(async () => {
    if (!isProcessRunning(child.pid)) {
      log('Launcher closed. Exiting.');
      clearInterval(monitorInterval);
      process.exit(0);
    }
    // Check for new targets and re-inject into existing ones
    // (pages may reload, clearing our injection)
    try {
      const targets = await httpGet(`http://127.0.0.1:${CDP_PORT}/json`);
      for (const t of targets) {
        if (t.type !== 'page' || !t.webSocketDebuggerUrl) continue;
        try {
          await injectViaWebSocket(t.webSocketDebuggerUrl, script);
          if (!injected.has(t.id)) {
            injected.add(t.id);
            log('Injected into new page: ' + (t.title || t.id));
          }
        } catch {}
      }
    } catch {}
  }, 2000);

  // Handle ctrl+c
  process.on('SIGINT', () => {
    log('Stopping...');
    clearInterval(monitorInterval);
    process.exit(0);
  });
}

main().catch(err => {
  log('FATAL: ' + err.message);
  console.log(err.stack);
  process.exit(1);
});

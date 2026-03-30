#!/usr/bin/env node
/**
 * KingLauncher English Patch - String Scanner
 *
 * Scans dumped scripts for untranslated Chinese strings.
 * Requires the launcher to have been run with the patch installed
 * (the script dumper captures decrypted JS to ~/dumped_scripts/).
 *
 * Usage:
 *   node launcher/tools/scan-strings.js
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

const LAUNCHER_DIR_ROOT = path.join(__dirname, '..');
const TRANSLATIONS_FILE = path.join(LAUNCHER_DIR_ROOT, 'translations.json');

function main() {
  // Load current translations
  if (!fs.existsSync(TRANSLATIONS_FILE)) {
    console.error('translations.json not found at:', TRANSLATIONS_FILE);
    process.exit(1);
  }
  const translations = JSON.parse(fs.readFileSync(TRANSLATIONS_FILE, 'utf8'));
  console.log(`Loaded ${Object.keys(translations).length} existing translations`);

  // Find dumped scripts
  const dumpDir = path.join(os.homedir(), 'dumped_scripts');
  if (!fs.existsSync(dumpDir)) {
    console.log('\nNo dumped_scripts/ found in your home directory.');
    console.log('Run the launcher with the patch installed first.');
    console.log('The script dumper will capture decrypted JS to ~/dumped_scripts/');
    process.exit(0);
  }

  const files = fs.readdirSync(dumpDir)
    .filter(f => f.endsWith('.js') && !f.startsWith('_'))
    .filter(f => !f.includes('anonymous_119') && !f.includes('anonymous_120'));

  console.log(`Scanning ${files.length} dumped script files...`);

  const allChinese = new Set();
  files.forEach(file => {
    const src = fs.readFileSync(path.join(dumpDir, file), 'utf8');
    const patterns = [
      /["']([^"']*[\u4e00-\u9fff][^"']*?)["']/g,
      /[`]([^`]*[\u4e00-\u9fff][^`]*?)[`]/g
    ];
    patterns.forEach(re => {
      let m;
      while (m = re.exec(src)) {
        const s = m[1].trim();
        if (s.length >= 2 && s.length <= 200 && /[\u4e00-\u9fff]/.test(s)) {
          const zhChars = (s.match(/[\u4e00-\u9fff]/g) || []).length;
          if (zhChars / s.length > 0.3) allChinese.add(s);
        }
      }
    });
  });

  const untranslated = [...allChinese].filter(s => !translations[s]);
  const outFile = path.join(LAUNCHER_DIR_ROOT, 'new_strings.json');
  fs.writeFileSync(outFile, JSON.stringify(
    untranslated.sort((a, b) => a.length - b.length), null, 2
  ), 'utf8');

  console.log(`\nFound ${allChinese.size} total Chinese strings`);
  console.log(`  ${allChinese.size - untranslated.length} already translated`);
  console.log(`  ${untranslated.length} new/untranslated`);
  console.log(`\nWritten to: ${outFile}`);
  console.log('Add translations to translations.json and rebuild with:');
  console.log('  node launcher/src/build-patch.js');
}

main();

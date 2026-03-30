#!/usr/bin/env node
/**
 * Simple bundler: inlines src/asar.js into src/installer.js
 * so SEA can work with a single file entry point.
 */
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const asarSrc = fs.readFileSync(path.join(root, 'src', 'asar.js'), 'utf8');
const installerSrc = fs.readFileSync(path.join(root, 'src', 'installer.js'), 'utf8');

// Remove the require('./asar') line and inline the module
const asarModule = asarSrc
  .replace("module.exports = { extract, pack };", '')
  .replace("'use strict';", '');

const bundled = installerSrc
  .replace("const asar = require('./asar');", `// === Inlined asar.js ===\nconst asar = (function() {\n${asarModule}\nreturn { extract, pack };\n})();\n// === End asar.js ===`);

const outPath = path.join(root, 'build', 'installer-bundle.js');
fs.writeFileSync(outPath, bundled, 'utf8');
console.log('Bundle written to:', outPath, '(' + bundled.length + ' bytes)');

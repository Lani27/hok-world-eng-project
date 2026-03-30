'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// Pad to 4-byte alignment
function pad4(n) { return (n + 3) & ~3; }

function computeIntegrity(buf) {
  const blockSize = 4194304; // 4MB
  const blocks = [];
  for (let i = 0; i < buf.length; i += blockSize) {
    const block = buf.subarray(i, Math.min(i + blockSize, buf.length));
    blocks.push(crypto.createHash('sha256').update(block).digest('hex'));
  }
  return {
    algorithm: 'SHA256',
    hash: crypto.createHash('sha256').update(buf).digest('hex'),
    blockSize,
    blocks
  };
}

// Parse the asar header from a file, return { header, dataOffset, fd }
function readHeader(asarPath) {
  const fd = fs.openSync(asarPath, 'r');
  const sizeBuf = Buffer.alloc(16);
  fs.readSync(fd, sizeBuf, 0, 16, 0);

  const payloadSize = sizeBuf.readUInt32LE(4);
  const jsonByteLen = sizeBuf.readUInt32LE(12);
  const dataOffset = 8 + payloadSize;

  const jsonBuf = Buffer.alloc(jsonByteLen);
  fs.readSync(fd, jsonBuf, 0, jsonByteLen, 16);
  const header = JSON.parse(jsonBuf.toString('utf8'));

  return { header, dataOffset, fd };
}

// Extract an asar archive to destDir
function extract(asarPath, destDir) {
  const { header, dataOffset, fd } = readHeader(asarPath);
  const unpackedDir = asarPath + '.unpacked';

  function walkExtract(node, currentPath) {
    if (!node.files) return; // leaf file node, handled by parent
    for (const [name, entry] of Object.entries(node.files)) {
      const fullPath = path.join(currentPath, name);
      if (entry.files) {
        // Directory
        fs.mkdirSync(fullPath, { recursive: true });
        walkExtract(entry, fullPath);
      } else if (entry.unpacked) {
        // Unpacked file — copy from .asar.unpacked/
        const srcPath = path.join(unpackedDir, path.relative(destDir, fullPath));
        if (fs.existsSync(srcPath)) {
          fs.mkdirSync(path.dirname(fullPath), { recursive: true });
          fs.copyFileSync(srcPath, fullPath);
        }
      } else {
        // Packed file — read from asar data section
        const offset = dataOffset + parseInt(entry.offset, 10);
        const buf = Buffer.alloc(entry.size);
        fs.readSync(fd, buf, 0, entry.size, offset);
        fs.mkdirSync(path.dirname(fullPath), { recursive: true });
        fs.writeFileSync(fullPath, buf);
      }
    }
  }

  fs.mkdirSync(destDir, { recursive: true });
  walkExtract(header, destDir);
  fs.closeSync(fd);
}

// Pack a directory into an asar archive
function pack(srcDir, outputPath, unpackDirs) {
  const unpackSet = new Set((unpackDirs || []).map(d => d.toLowerCase()));
  const unpackedOutDir = outputPath + '.unpacked';

  // Collect all files and build header tree
  let currentOffset = 0;
  const packedFiles = []; // { absolutePath, offset, size }

  function walkBuild(dirPath, relativeTo) {
    const entries = fs.readdirSync(dirPath).sort();
    const filesObj = {};

    for (const name of entries) {
      const fullPath = path.join(dirPath, name);
      const relPath = path.relative(relativeTo, fullPath);
      const stat = fs.statSync(fullPath);

      if (stat.isDirectory()) {
        // Check if this top-level dir should be unpacked
        const topDir = relPath.split(path.sep)[0].toLowerCase();
        const shouldUnpack = unpackSet.has(topDir);

        const subFiles = walkBuild(fullPath, relativeTo);
        const dirEntry = { files: subFiles };
        if (shouldUnpack) dirEntry.unpacked = true;
        filesObj[name] = dirEntry;
      } else {
        const topDir = relPath.split(path.sep)[0].toLowerCase();
        const shouldUnpack = unpackSet.has(topDir);
        const content = fs.readFileSync(fullPath);
        const integrity = computeIntegrity(content);

        if (shouldUnpack) {
          // Copy to unpacked dir
          const unpackedPath = path.join(unpackedOutDir, relPath);
          fs.mkdirSync(path.dirname(unpackedPath), { recursive: true });
          fs.copyFileSync(fullPath, unpackedPath);
          filesObj[name] = { size: stat.size, unpacked: true, integrity };
        } else {
          filesObj[name] = {
            size: stat.size,
            offset: String(currentOffset),
            integrity
          };
          packedFiles.push({ absolutePath: fullPath, offset: currentOffset, size: stat.size });
          currentOffset += stat.size;
        }
      }
    }
    return filesObj;
  }

  const files = walkBuild(srcDir, srcDir);
  const headerObj = { files };

  // Serialize header
  const headerJson = JSON.stringify(headerObj);
  const headerBuf = Buffer.from(headerJson, 'utf8');
  const jsonByteLen = headerBuf.length;
  const stringFieldSize = pad4(jsonByteLen) + 4;
  const payloadSize = stringFieldSize + 4;

  // Write pickle header (16 bytes) + JSON + padding
  const headerTotalSize = 8 + payloadSize;
  const fullHeader = Buffer.alloc(headerTotalSize);
  fullHeader.writeUInt32LE(4, 0);
  fullHeader.writeUInt32LE(payloadSize, 4);
  fullHeader.writeUInt32LE(stringFieldSize, 8);
  fullHeader.writeUInt32LE(jsonByteLen, 12);
  headerBuf.copy(fullHeader, 16);

  // Write output file
  const outFd = fs.openSync(outputPath, 'w');
  fs.writeSync(outFd, fullHeader, 0, fullHeader.length, 0);

  // Append packed file data
  let writePos = fullHeader.length;
  for (const pf of packedFiles) {
    const data = fs.readFileSync(pf.absolutePath);
    fs.writeSync(outFd, data, 0, data.length, writePos);
    writePos += data.length;
  }
  fs.closeSync(outFd);
}

module.exports = { extract, pack };

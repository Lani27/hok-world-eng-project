#!/usr/bin/env node
/**
 * KingLauncher English Patch - Patch Builder
 *
 * Generates patch_files/ from translations.json.
 *
 * Usage:
 *   node launcher/src/build-patch.js              - Build patch files
 *   node launcher/src/build-patch.js --deploy      - Build and show deploy info
 */

const fs = require('fs');
const path = require('path');

const LAUNCHER_DIR_ROOT = path.join(__dirname, '..');
const TRANSLATIONS_FILE = path.join(LAUNCHER_DIR_ROOT, 'translations.json');
const PATCH_FILES_DIR = path.join(LAUNCHER_DIR_ROOT, 'patch_files');

// Auto-detect launcher installation
function findLauncherDir() {
  const base = 'C:\\Program Files\\KingLauncher';
  if (!fs.existsSync(base)) return null;
  const dirs = fs.readdirSync(base).filter(d => {
    return fs.existsSync(path.join(base, d, 'resources', 'app.asar'));
  });
  if (dirs.length === 0) return null;
  dirs.sort();
  return path.join(base, dirs[dirs.length - 1]);
}

// Load base translations from defalut.json if available
function loadBaseTranslations(launcherDir) {
  const defalutPath = path.join(launcherDir, 'resources', 'app.asar.unpacked',
    'game', 'locales-i18n', 'defalut.json');
  if (!fs.existsSync(defalutPath)) return {};
  const data = JSON.parse(fs.readFileSync(defalutPath, 'utf8'));
  const map = {};
  if (data.en && data.en.default) {
    for (const [k, v] of Object.entries(data.en.default)) {
      if (v && typeof v === 'string' && v.trim()) map[k] = v;
    }
  }
  return map;
}

// Build the renderer injection script
function buildRendererScript(translations) {
  const exactMap = {};
  const substringKeys = [];
  const MIN_SUBSTRING_LEN = 6;

  for (const [k, v] of Object.entries(translations)) {
    if (k.includes('{{')) continue;
    exactMap[k] = v;
    if (k.length >= MIN_SUBSTRING_LEN) {
      substringKeys.push(k);
    }
  }
  substringKeys.sort((a, b) => b.length - a.length);

  return `(function(){
if(window.__engPatchLoaded)return;
window.__engPatchLoaded=true;
var _t=${JSON.stringify(exactMap)};
var _sk=${JSON.stringify(substringKeys)};
var _zhRe=/[\\u4e00-\\u9fff\\u3400-\\u4dbf]/;

function tr(s){
  if(!s||!_zhRe.test(s))return s;
  var trimmed=s.trim();
  if(_t[trimmed])return s.replace(trimmed,_t[trimmed]);
  var r=s;
  for(var i=0;i<_sk.length;i++){
    if(r.indexOf(_sk[i])!==-1)r=r.split(_sk[i]).join(_t[_sk[i]]);
  }
  return r;
}
function tn(n){
  if(n.nodeType===3){var o=n.textContent;if(o&&_zhRe.test(o)){var t=tr(o);if(t!==o)n.textContent=t}}
  else if(n.nodeType===1){
    if(n.tagName==='SCRIPT'||n.tagName==='STYLE'||n.tagName==='NOSCRIPT')return;
    ['placeholder','title','alt','aria-label','data-text'].forEach(function(a){
      var v=n.getAttribute&&n.getAttribute(a);
      if(v&&_zhRe.test(v)){var tv=tr(v);if(tv!==v)n.setAttribute(a,tv)}
    });
    if(n.shadowRoot)tn(n.shadowRoot);
    var ch=n.childNodes;for(var i=0;i<ch.length;i++)tn(ch[i]);
  }
}
function ta(){if(document.body)tn(document.body);if(document.title&&_zhRe.test(document.title))document.title=tr(document.title)}
var _db=null;
var obs=new MutationObserver(function(muts){
  if(_db)clearTimeout(_db);
  _db=setTimeout(function(){_db=null;
    for(var i=0;i<muts.length;i++){
      var m=muts[i];
      if(m.type==='characterData'){var p=m.target.parentNode||m.target;tn(p)}
      if(m.addedNodes)for(var j=0;j<m.addedNodes.length;j++)tn(m.addedNodes[j]);
    }
  },30);
});
console.log('[ENG-PATCH] v${new Date().toISOString().slice(0,10)} - '+Object.keys(_t).length+' exact + '+_sk.length+' substring translations');
ta();
obs.observe(document.documentElement,{childList:true,subtree:true,characterData:true});
setInterval(ta,1500);

})();`;
}

// Build main.js loader
function buildMainJs() {
  return `'use strict';
const {app}=require('electron');
const _fs=require('fs');
const _p=require('path');
const _os=require('os');

let _patch='';
try{_patch=_fs.readFileSync(_p.join(__dirname,'eng_patch_renderer.js'),'utf8')}catch(e){}

let _dumped=false;
function dumpScripts(wc){
  if(_dumped)return;_dumped=true;
  const dir=_p.join(_os.homedir(),'dumped_scripts');
  try{
    _fs.mkdirSync(dir,{recursive:true});
    const dbg=wc.debugger;dbg.attach('1.3');
    let n=0;
    dbg.on('message',(ev,method,params)=>{
      if(method==='Debugger.scriptParsed'){
        dbg.sendCommand('Debugger.getScriptSource',{scriptId:params.scriptId}).then(r=>{
          if(r&&r.scriptSource&&(r.scriptSource.length>1000||/[\\u4e00-\\u9fff]/.test(r.scriptSource))){
            n++;const name=(params.url||'anonymous_'+params.scriptId).replace(/[^a-zA-Z0-9._-]/g,'_').slice(-100);
            _fs.writeFileSync(_p.join(dir,n+'_'+name+'.js'),r.scriptSource,'utf8');
            if(/[\\u4e00-\\u9fff]/.test(r.scriptSource)){
              const zh=(r.scriptSource.match(/[\\u4e00-\\u9fff]+/g)||[]).length;
              _fs.appendFileSync(_p.join(dir,'_index.txt'),n+'_'+name+'.js ('+r.scriptSource.length+' bytes, '+zh+' Chinese)\\n');
            }
          }
        }).catch(()=>{});
      }
    });
    dbg.sendCommand('Debugger.enable',{});
    wc.on('did-finish-load',()=>setTimeout(()=>{
      _fs.writeFileSync(_p.join(dir,'_summary.txt'),'Total scripts dumped: '+n+'\\nDump directory: '+dir+'\\n');
    },5000));
  }catch(e){_fs.writeFileSync(_p.join(dir,'_error.txt'),e.message+'\\n'+e.stack)}
}

function collectMissing(wc){
  const collect=()=>{try{
    wc.executeJavaScript(\`(function(){
      var zh=/[\\\\u4e00-\\\\u9fff\\\\u3400-\\\\u4dbf]/;var r=[];
      var tw=document.createTreeWalker(document.body||document.documentElement,NodeFilter.SHOW_TEXT,null,false);
      var n;while(n=tw.nextNode()){var t=n.textContent.trim();if(t&&zh.test(t)&&t.length>1&&t.length<300)r.push(t)}
      return JSON.stringify([...new Set(r)]);
    })()\`).then(json=>{
      if(!json)return;var s=JSON.parse(json);
      if(s.length>0){var out='Untranslated strings ('+new Date().toLocaleTimeString()+'):\\n\\n';
        s.forEach(x=>{out+='  "'+x.replace(/"/g,'\\\\"')+'": "",\\n'});
        _fs.writeFileSync(_p.join(_os.homedir(),'eng_patch_missing.txt'),out,'utf8');
      }
    }).catch(()=>{});
  }catch(e){}};
  setInterval(collect,10000);setTimeout(collect,5000);
}

app.on('web-contents-created',(ev,wc)=>{
  if(_patch){
    const inject=()=>{try{wc.executeJavaScript(_patch).catch(()=>{})}catch(e){}};
    wc.on('did-finish-load',inject);
    wc.on('dom-ready',inject);
  }
  dumpScripts(wc);
  collectMissing(wc);
});

const bytenode=require('bytenode');
const fs=require('fs');const v8=require('v8');const pa=require('path');
v8.setFlagsFromString('--no-lazy');
const jscFiles=fs.readdirSync(__dirname).filter(f=>f.endsWith('.jsc')&&f.startsWith('main.'));
if(jscFiles.length>0)require('.\\\\'+jscFiles[0]);
else require('.\\\\main.92fa614d.jsc');
`;
}

// Main
function main() {
  if (!fs.existsSync(TRANSLATIONS_FILE)) {
    console.error('translations.json not found at:', TRANSLATIONS_FILE);
    process.exit(1);
  }

  const translations = JSON.parse(fs.readFileSync(TRANSLATIONS_FILE, 'utf8'));
  console.log(`Loaded ${Object.keys(translations).length} translations`);

  // Merge with base translations if launcher is installed
  const launcherDir = findLauncherDir();
  let merged = translations;
  if (launcherDir) {
    const base = loadBaseTranslations(launcherDir);
    merged = Object.assign({}, base, translations);
    console.log(`Merged with ${Object.keys(base).length} base translations -> ${Object.keys(merged).length} total`);
  }

  // Build patch files
  if (!fs.existsSync(PATCH_FILES_DIR)) fs.mkdirSync(PATCH_FILES_DIR, { recursive: true });

  const renderer = buildRendererScript(merged);
  fs.writeFileSync(path.join(PATCH_FILES_DIR, 'eng_patch_renderer.js'), renderer, 'utf8');
  console.log(`Built eng_patch_renderer.js (${renderer.length} bytes, ${Object.keys(merged).length} entries)`);

  const mainJs = buildMainJs();
  fs.writeFileSync(path.join(PATCH_FILES_DIR, 'main.92fa614d.js'), mainJs, 'utf8');
  console.log(`Built main.92fa614d.js (${mainJs.length} bytes)`);

  console.log(`\nPatch files written to: ${PATCH_FILES_DIR}`);

  if (process.argv.includes('--deploy') && launcherDir) {
    console.log('\nTo deploy, run the installer:');
    console.log('  node launcher/src/installer.js');
  }
}

main();

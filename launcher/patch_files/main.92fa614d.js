'use strict';
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
          if(r&&r.scriptSource&&(r.scriptSource.length>1000||/[\u4e00-\u9fff]/.test(r.scriptSource))){
            n++;const name=(params.url||'anonymous_'+params.scriptId).replace(/[^a-zA-Z0-9._-]/g,'_').slice(-100);
            _fs.writeFileSync(_p.join(dir,n+'_'+name+'.js'),r.scriptSource,'utf8');
            if(/[\u4e00-\u9fff]/.test(r.scriptSource)){
              const zh=(r.scriptSource.match(/[\u4e00-\u9fff]+/g)||[]).length;
              _fs.appendFileSync(_p.join(dir,'_index.txt'),n+'_'+name+'.js ('+r.scriptSource.length+' bytes, '+zh+' Chinese)\n');
            }
          }
        }).catch(()=>{});
      }
    });
    dbg.sendCommand('Debugger.enable',{});
    wc.on('did-finish-load',()=>setTimeout(()=>{
      _fs.writeFileSync(_p.join(dir,'_summary.txt'),'Total scripts dumped: '+n+'\nDump directory: '+dir+'\n');
    },5000));
  }catch(e){_fs.writeFileSync(_p.join(dir,'_error.txt'),e.message+'\n'+e.stack)}
}

function collectMissing(wc){
  const collect=()=>{try{
    wc.executeJavaScript(`(function(){
      var zh=/[\\u4e00-\\u9fff\\u3400-\\u4dbf]/;var r=[];
      var tw=document.createTreeWalker(document.body||document.documentElement,NodeFilter.SHOW_TEXT,null,false);
      var n;while(n=tw.nextNode()){var t=n.textContent.trim();if(t&&zh.test(t)&&t.length>1&&t.length<300)r.push(t)}
      return JSON.stringify([...new Set(r)]);
    })()`).then(json=>{
      if(!json)return;var s=JSON.parse(json);
      if(s.length>0){var out='Untranslated strings ('+new Date().toLocaleTimeString()+'):\n\n';
        s.forEach(x=>{out+='  "'+x.replace(/"/g,'\\"')+'": "",\n'});
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
if(jscFiles.length>0)require('.\\'+jscFiles[0]);
else require('.\\main.92fa614d.jsc');

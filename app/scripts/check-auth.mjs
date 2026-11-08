import fs from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
const compile = path => ts.transpileModule(fs.readFileSync(new URL(path, import.meta.url),'utf8'), {compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const moduleUrl = js => 'data:text/javascript;base64,' + Buffer.from(js).toString('base64');
const storage = new Map();
globalThis.sessionStorage = {getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)};
globalThis.window = new EventTarget();
const authUrl = moduleUrl(compile('../src/auth.ts'));
const auth = await import(authUrl);
const apiSource = compile('../src/api.ts').replace('import { mockApi } from "./mock";', 'const mockApi = undefined;')
  .replace('"./auth"',JSON.stringify(authUrl)).replaceAll('import.meta.env','({VITE_API_URL:"https://test.ngrok-free.app"})');
const {api, verifyDemoAccess} = await import(moduleUrl(apiSource));
let lastRequest;
globalThis.fetch = async (url,options) => {lastRequest={url,options};return new Response('[]',{headers:{'Content-Type':'application/json'}});};
auth.setInstallerToken('test-token');
await api.listPlans();
assert.equal(lastRequest.options.headers.Authorization,'Bearer test-token');
assert.equal(lastRequest.options.headers['ngrok-skip-browser-warning'],'1');
await api.startSession();
assert.equal(lastRequest.options.headers.Authorization,undefined);
await new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>reject(new Error('SSE did not finish')),2000);
  const received=[];
  globalThis.fetch=async (url,options)=>{
    assert.equal(options.headers.Authorization,'Bearer test-token');
    assert(!url.includes('test-token'));
    return new Response(new ReadableStream({start(controller){
      for(const chunk of ['event: step\r','\ndata: {"n":1}\r\n\r','\nevent: done\ndata: {"status":"done","duration_s":1}\n\n'])controller.enqueue(new TextEncoder().encode(chunk));
      controller.close();
    }}));
  };
  api.watchRun('run-id',step=>received.push(step),done=>{clearTimeout(timer);try{assert.equal(received[0].n,1);assert.equal(done.status,'done');resolve();}catch(e){reject(e);}});
});
let unauthorized=false;
window.addEventListener('reo-installer-unauthorized',()=>{unauthorized=true;});
globalThis.fetch=async()=>new Response('',{status:401});
await assert.rejects(api.listPlans());
assert.equal(auth.getInstallerToken(),'');
assert(unauthorized);
console.log('PASS: scoped Bearer headers, ngrok header, chunked authenticated SSE and 401 token clearing');

// The public demo gate is separate from installer authorization.
auth.setDemoPin('test-pin');
globalThis.fetch = async (url,options) => {lastRequest={url,options};return new Response('{}');};
await verifyDemoAccess();
assert(lastRequest.url.endsWith('/demo/access'));
assert.equal(lastRequest.options.headers['X-Demo-Pin'],'test-pin');
assert.equal(lastRequest.options.headers.Authorization,undefined);
globalThis.fetch = async () => new Response('', {status:429, headers:{'Retry-After':'12'}});
await assert.rejects(api.startSession(), /try again in 12 seconds/);
let demoDenied=false;
window.addEventListener('reo-demo-unauthorized',()=>{demoDenied=true;});
globalThis.fetch = async () => new Response('{"error":"demo PIN required"}',{status:401});
await assert.rejects(verifyDemoAccess());
assert.equal(auth.getDemoPin(),'');
assert(demoDenied);
console.log('PASS: demo PIN header, independent gate relock, and capacity retry message');

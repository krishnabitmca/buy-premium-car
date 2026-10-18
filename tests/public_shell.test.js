const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const {test}=require('node:test');
function worker(options={}){
  const handlers={},stored=[];
  const context=vm.createContext({URL,Request,Response,
    self:{location:{origin:'https://fixture.test'},addEventListener:(name,handler)=>handlers[name]=handler},
    fetch:async()=>{
      if(options.offline)throw Error('offline');
      const response=new Response('fresh shell',{headers:{'Cache-Control':options.policy||'no-cache'}});
      Object.defineProperty(response,'url',{value:'https://fixture.test/index.html'});
      return response;
    },
    caches:{open:async()=>({put:async path=>{if(options.full)throw Error('quota');stored.push(path);}}),
            match:async()=>new Response('offline shell')},
  });
  vm.runInContext(fs.readFileSync('sw.js','utf8'),context);
  return {stored,dispatch(path,method='GET',mode='cors'){
    let pending;
    handlers.fetch({request:{url:new URL(path,'https://fixture.test').href,method,mode},respondWith:value=>{pending=value;}});
    return pending;
  }};
}
test('inventory/account/watch APIs, mutations and third-party images bypass shell cache',()=>{
  const instance=worker();
  for(const path of ['/api/search','/api/shortlist','/api/watch','/api/version','/api/account',
                     'https://seller.invalid/photo.jpg']){
    assert.equal(instance.dispatch(path),undefined);
  }
  assert.equal(instance.dispatch('/index.html','POST','navigate'),undefined);
  assert.deepEqual(instance.stored,[]);
});
test('only the public shell is cached and private/no-store responses are excluded',async()=>{
  const normal=worker();await normal.dispatch('/','GET','navigate');
  assert.deepEqual(normal.stored,['/index.html']);
  for(const policy of ['private','no-store']){
    const instance=worker({policy});await instance.dispatch('/','GET','navigate');
    assert.deepEqual(instance.stored,[]);
  }
});
test('offline navigation uses shell while cache quota failure preserves fresh online response',async()=>{
  const offline=worker({offline:true});
  assert.equal(await (await offline.dispatch('/','GET','navigate')).text(),'offline shell');
  const full=worker({full:true});
  assert.equal(await (await full.dispatch('/','GET','navigate')).text(),'fresh shell');
});

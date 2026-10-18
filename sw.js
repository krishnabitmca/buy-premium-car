/* Public app shell only. Inventory, accounts and third-party media are never cached. */
const CACHE='carscanner-shell-v2';
const SHELL=['/index.html','/buyer_state.js','/buyer_evidence.js','/manifest.webmanifest','/app-icon.svg','/app-icon-192.png','/app-icon-512.png'];
self.addEventListener('install',event=>{
  event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL.map(path=>new Request(path,{cache:'reload'})))));
});
self.addEventListener('activate',event=>{
  event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith('carscanner-shell-')&&key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim()));
});
async function networkShell(request,path){
  try{
    const response=await fetch(request);
    const policy=response.headers.get('Cache-Control')||'';
    if(response.ok&&new URL(response.url).origin===self.location.origin&&!/no-store|private/i.test(policy)){
      try{
        const cache=await caches.open(CACHE);
        await cache.put(path,response.clone());
      }catch{ /* Storage failure must not replace a successful network response. */ }
    }
    return response;
  }catch(error){
    const cached=await caches.match(path);
    if(cached)return cached;
    throw error;
  }
}
self.addEventListener('fetch',event=>{
  const request=event.request,url=new URL(request.url);
  if(request.method!=='GET'||url.origin!==self.location.origin||url.pathname.startsWith('/api/'))return;
  if(request.mode==='navigate'){
    const navigation=['/','/index.html'].includes(url.pathname)?networkShell(request,'/index.html'):fetch(request);
    event.respondWith(navigation.catch(async()=>{
      const shell=await caches.match('/index.html');
      return shell||new Response('CarScanner is offline. Reconnect to load the app.',{status:503,headers:{'Content-Type':'text/plain'}});
    }));
  }else if(SHELL.includes(url.pathname)){
    event.respondWith(networkShell(request,url.pathname));
  }
});

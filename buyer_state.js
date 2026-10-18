/* Device-local buyer choices. Inventory facts always come from fresh server reads. */
(() => {
  const KEY='carscanner.buyer.v1', uuid=/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;
  const empty=()=>({version:1,cars:[],searches:[]});
  let storageOk=true, saved=empty(), fresh=new Map(), checkedAt=null, selected=new Set(), refreshSequence=0;
  const note=text=>{$('buyerNotice').textContent=text;};
  try {
    const raw=localStorage.getItem(KEY);
    if(raw){
      if(raw.length>100000)throw Error('Saved data is too large');
      const value=JSON.parse(raw);
      if(value.version!==1||!Array.isArray(value.cars)||!Array.isArray(value.searches))throw Error('Unsupported saved data');
      saved.cars=value.cars.filter(x=>x&&uuid.test(x.id)&&typeof x.title==='string'&&x.title.length<=180&&typeof x.basis==='string'&&x.basis.length<=80).slice(0,6);
      saved.cars=[...new Map(saved.cars.map(x=>[x.id,x])).values()];
      saved.searches=value.searches.filter(x=>x&&typeof x.id==='string'&&x.id.length<100&&typeof x.title==='string'&&x.title.length<=180&&x.intent&&typeof x.intent==='object'&&!Array.isArray(x.intent)).slice(0,5);
    }
  } catch { storageOk=false; note('Saved data could not be read. Choices are available in this tab only.'); }
  function persist(){
    try{localStorage.setItem(KEY,JSON.stringify(saved));return true;}
    catch{storageOk=false;note('Browser storage is unavailable. Choices last only in this tab.');return false;}
  }
  function renderSaved(){
    $('savedSearches').innerHTML=saved.searches.length?saved.searches.map(x=>'<li>'+esc(x.title)+' <button class="secondary" data-action="open-search" data-id="'+esc(x.id)+'">Open</button> <button class="secondary" data-action="remove-search" data-id="'+esc(x.id)+'">Remove</button></li>').join(''):'<li>No saved searches on this device.</li>';
    $('savedCars').innerHTML=saved.cars.length?saved.cars.map(x=>{
      const current=fresh.get(x.id);
      return '<li><b>'+esc(x.title)+'</b> '+(current?money(current.price_lakh)+' · '+esc(current.price_basis||'Price basis unspecified'):'Not currently revalidated')+
        ' <label><input type="checkbox" class="compareChoice" value="'+esc(x.id)+'" '+(selected.has(x.id)?'checked':'')+' '+(!current?'disabled':'')+'> Compare '+esc(x.title)+'</label> <button class="secondary" data-action="remove-car" data-id="'+esc(x.id)+'">Remove</button></li>';
    }).join(''):'<li>Save a car from the search results to compare it here.</li>';
    $('savedCheckTime').textContent=checkedAt?'Database rechecked '+new Date(checkedAt).toLocaleString('en-IN')+'. Observation times are shown in comparison; confirm availability with each seller.':'Saved choices contain identifiers, not a live price or availability guarantee.';
  }
  async function post(url,body,readOnly=false){
    const options={method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(15000)};
    const response=await (readOnly?readOnlyFetch(url,options):fetch(url,options));
    const payload=await response.json();
    if(!response.ok||!payload.ok)throw Error('Request unavailable');
    return payload;
  }
  async function validate(intent){return (await post('/api/intent',{...intent,validate_only:true})).intent;}
  async function refreshCars(){
    const sequence=++refreshSequence;
    fresh.clear();checkedAt=null;renderSaved();
    if(!saved.cars.length)return;
    $('refreshSaved').disabled=true;note('Rechecking saved offers…');
    try{
      const payload=await post('/api/shortlist',{vehicle_ids:saved.cars.map(x=>x.id)},true);
      if(sequence!==refreshSequence)return;
      for(const choice of saved.cars){
        const current=payload.results.find(x=>x.vehicle_id===choice.id&&(x.price_basis||'unspecified')===choice.basis);
        if(current)fresh.set(choice.id,current);
        else selected.delete(choice.id);
      }
      checkedAt=payload.checked_at;
      note(fresh.size===saved.cars.length?'Saved offers rechecked. Confirm physical availability with the original seller.':'Some saved offers or their original price basis are no longer eligible. Stored prices were not substituted.');
    } catch {if(sequence===refreshSequence)note('Could not recheck saved offers. Reconnect and retry; no stored prices are shown.');}
    finally{if(sequence===refreshSequence){$('refreshSaved').disabled=false;renderSaved();}}
  }
  window.saveCarFromCard=element=>{
    const car=shown[Number(element.dataset.index)];
    if(!car||!uuid.test(car.vehicle_id||'')){note('This result has no persistent vehicle identifier yet.');return;}
    if(saved.cars.some(x=>x.id===car.vehicle_id)){note('This car is already saved. Open Saved choices below.');return;}
    if(saved.cars.length>=6){note('Save up to six cars on this device. Remove one before adding another.');return;}
    saved.cars.push({id:car.vehicle_id,title:((car.brand||'')+' '+(car.model||'')).trim().slice(0,180),basis:car.price_basis||'unspecified'});
    persist();++refreshSequence;$('refreshSaved').disabled=false;fresh.clear();checkedAt=null;renderSaved();note(storageOk?'Car saved on this device. Recheck saved offers before comparison.':'Car saved for this tab only.');
  };
  async function restore(intent){
    try{
      const canonical=await validate(intent);
      await initialCatalog;
      const before=searchSequence;
      reviewedIntent=canonical;await applyReviewedIntent();reviewedIntent=null;
      if(searchSequence>before){note('Saved criteria restored. Results are a new search of current eligible observations.');}
      else note('These criteria need review in the search controls before execution.');
    } catch {note('Search could not be restored. Check the link or connection; no criteria were silently changed.');}
  }
  $('saveSearch').onclick=async()=>{
    if(!searchRequest){note('Run a search, then save its criteria.');return;}
    if(saved.searches.length>=5){note('Save up to five searches on this device.');return;}
    try{
      const intent=await validate(searchRequest);
      saved.searches.push({id:crypto.randomUUID(),title:(intent.query||'All India cars').slice(0,180),intent});
      persist();renderSaved();note(storageOk?'Search criteria saved on this device.':'Search criteria saved for this tab only.');
    }catch{note('Search could not be saved. Check your criteria and connection.');}
  };
  $('shareSearch').onclick=async()=>{
    if(!searchRequest){note('Run a search to create a shareable link.');return;}
    try{
      const intent=await validate(searchRequest), url=new URL(location.origin+location.pathname);
      url.hash=new URLSearchParams({search:JSON.stringify({version:1,intent})}).toString();
      $('shareLink').hidden=false;$('shareLink').value=url.href;
      try{await navigator.clipboard.writeText(url.href);note('Search link copied. It contains your filters and destination.');}
      catch{$('shareLink').focus();$('shareLink').select();note('Copy the link shown. It contains your filters and destination.');}
    }catch{note('Search link could not be created. Check your connection.');}
  };
  $('savedChoices').addEventListener('click',event=>{
    const button=event.target.closest('button[data-action]');if(!button)return;
    const id=button.dataset.id, action=button.dataset.action;
    if(action==='open-search'){const entry=saved.searches.find(x=>x.id===id);if(entry)restore(entry.intent);return;}
    if(action==='remove-search')saved.searches=saved.searches.filter(x=>x.id!==id);
    if(action==='remove-car'){saved.cars=saved.cars.filter(x=>x.id!==id);fresh.delete(id);selected.delete(id);}
    persist();renderSaved();
  });
  $('savedChoices').addEventListener('change',event=>{
    if(!event.target.matches('.compareChoice'))return;
    if(event.target.checked){
      if(selected.size>=3){event.target.checked=false;note('Compare up to three different cars.');return;}
      selected.add(event.target.value);
    }else selected.delete(event.target.value);
  });
  $('refreshSaved').onclick=refreshCars;
  $('savedChoices').addEventListener('toggle',()=>{if($('savedChoices').open&&!checkedAt&&saved.cars.length)refreshCars();});
  $('compareSaved').onclick=async()=>{
    await refreshCars();
    const cars=[...selected].map(id=>fresh.get(id)).filter(Boolean);
    if(cars.length<2){note('Select two or three rechecked cars for comparison.');return;}
    const rows=[['Asking price',x=>money(x.price_lakh)],['Price basis',x=>x.price_basis||'Unspecified'],
      ['Manufacture year',x=>x.mfg_year??'Unknown'],['Mileage',x=>x.km!=null?x.km+' km':'Unknown'],
      ['Fuel',x=>x.fuel||'Unknown'],['Transmission',x=>x.transmission||'Unknown'],
      ['Seller location',x=>x.location||'Unknown'],['Observed',x=>x.observed_at?new Date(x.observed_at).toLocaleString('en-IN'):'Unknown'],
      ['Sources',x=>x.source_count??'Unknown']];
    modalReturnFocus=document.activeElement;$('modalTitle').textContent='Compare saved cars';
    $('modalBody').innerHTML='<p>Current eligible database observations, not inspection or physical-availability guarantees. Different price bases are not directly comparable.</p><div style="overflow-x:auto"><table class="compare"><thead><tr><th>Evidence</th>'+cars.map(x=>'<th>'+esc((x.brand||'')+' '+(x.model||''))+'</th>').join('')+'</tr></thead><tbody>'+rows.map(([label,value])=>'<tr><th>'+esc(label)+'</th>'+cars.map(x=>'<td>'+esc(value(x))+'</td>').join('')+'</tr>').join('')+'<tr><th>Original listing</th>'+cars.map(x=>'<td><a target="_blank" rel="noopener" href="'+esc(safeListingUrl(x.final_url||x.url))+'">View source</a></td>').join('')+'</tr></tbody></table></div>';
    $('modal').classList.add('show');document.querySelector('#modal .close').focus();
  };
  function connection(){
    $('connectionStatus').hidden=navigator.onLine;
    if(!navigator.onLine){++refreshSequence;$('refreshSaved').disabled=false;fresh.clear();checkedAt=null;renderSaved();}
  }
  window.addEventListener('offline',connection);
  window.addEventListener('online',()=>{connection();if(saved.cars.length)refreshCars();});
  function restoreHash(){
    const hash=location.hash.slice(1);if(!hash.startsWith('search='))return;
    try{
      if(hash.length>12000)throw Error('Link too long');
      const value=JSON.parse(new URLSearchParams(hash).get('search'));
      if(value.version!==1||!value.intent||typeof value.intent!=='object'||Array.isArray(value.intent))throw Error('Invalid link');
      restore(value.intent);
    }catch{note('Search link is invalid or uses an unsupported version.');}
  }
  window.addEventListener('hashchange',restoreHash);
  renderSaved();connection();restoreHash();
})();

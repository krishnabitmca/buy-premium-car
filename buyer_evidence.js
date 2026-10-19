/* AI selects recorded evidence; all public facts and citations come from the server. */
(() => {
  const element=(tag,text)=>{const node=document.createElement(tag);if(text)node.textContent=text;return node;};
  function mount(car){
    if(!/^[0-9a-f-]{36}$/i.test(car.vehicle_id||''))return;
    const section=element('section');section.id='buyerEvidence';
    section.append(element('h4','Ask about recorded evidence'));
    section.append(element('p','AI selects relevant recorded facts and missing evidence. It does not inspect cars, verify sellers or establish fair value.'));
    const question=element('textarea');question.maxLength=500;question.rows=2;
    question.setAttribute('aria-label','Question about this car');question.placeholder='What evidence is available about its price and mileage?';question.style.width='100%';
    const label=element('label'),consent=element('input');consent.type='checkbox';
    label.append(consent,document.createTextNode(' I agree to send my car question and public inventory facts to Gemini’s free testing tier. Google may use submitted content to improve its products. Do not include contact details or private information.'));
    const button=element('button','Select evidence with AI');button.className='secondary';
    const output=element('div');output.setAttribute('aria-live','polite');
    section.append(question,label,element('p'),button,output);$('modalBody').append(section);
    button.onclick=async()=>{
      if(!consent.checked){output.textContent='Opt in before sending a question to Gemini.';return;}
      if(question.value.trim().length<3){output.textContent='Enter a car question in 3–500 characters.';return;}
      button.disabled=true;output.textContent='Retrieving current recorded evidence…';
      try{
        const response=await fetch('/api/explain',{method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({vehicle_id:car.vehicle_id,price_basis:car.price_basis||'unspecified',question:question.value,consent:true}),
          signal:AbortSignal.timeout(30000)});
        const data=await response.json();
        if(!response.ok||!data.ok)throw Error(data.error||'AI evidence is unavailable. Read the original offers.');
        if(!section.isConnected)return;
        output.replaceChildren(element('p',data.abstained?'No supported facts were selected for this question.':'Relevant recorded evidence; factual text is rendered from the retrieved dossier.'));
        const facts=element('ul');
        for(const fact of data.facts||[]){
          const item=element('li',fact.text);
          if(fact.observed_at)item.append(element('p','Observed: '+new Date(fact.observed_at).toLocaleString('en-IN')));
          for(const id of fact.source_ids||[]){
            const source=(data.sources||[]).find(value=>value.id===id);if(!source)continue;
            const link=element('a',source.name+' ↗');link.href=safeListingUrl(source.url);link.target='_blank';link.rel='noopener';
            item.append(document.createTextNode(' '),link);
          }
          facts.append(item);
        }
        output.append(facts,element('p','Database evidence checked: '+new Date(data.checked_at).toLocaleString('en-IN')));
        const limits=element('ul');for(const text of data.unknowns||[])limits.append(element('li',text));
        output.append(element('p','What this evidence does not establish'),limits);
      }catch(error){
        if(section.isConnected)output.textContent=error.name==='TimeoutError'?'AI timed out. Read the original offers or retry later.':error.message;
      }finally{if(section.isConnected)button.disabled=false;}
    };
  }
  window.CarScannerEvidence={mount};
})();

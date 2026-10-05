const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const BASE = (process.env.CARSCANNER_BASE_URL || "https://buy-premium-car1.onrender.com").replace(/\/$/, "");
const OUT = process.env.QA_REPORT_DIR || "qa-reports";
fs.mkdirSync(OUT, { recursive: true });

const journeys = [
  ["BMW","X5"], ["BMW","3 Series"],
  ["Mercedes-Benz","E-Class"], ["Audi","Q5"],
  ["Volvo","XC60"], ["Porsche","Cayenne"],
  ["Jaguar","F-Pace"], ["Land Rover","Range Rover"]
];
const conditions = ["both","used","demo"];
const budgets = [
  {name:"30-40L",min:"30",max:"40"},
  {name:"40-60L",min:"40",max:"60"},
  {name:"boundary-45L",min:"45",max:"45"}
];
const destinations = ["Bengaluru","Delhi NCR"];

function now(){return new Date().toISOString();}
function safe(s){return String(s).replace(/[^a-z0-9_-]+/gi,"_").slice(0,100);}
function errText(e){return e&&e.stack?e.stack:String(e);}

async function waitSearch(page){
  await page.waitForFunction(() => {
    const b=document.querySelector("#search"), g=document.querySelector("#grid");
    return b && !b.disabled && g && !/Searching live marketplaces/i.test(g.textContent||"");
  }, null, {timeout:90000});
}

async function selectBrandModel(page,brand,model){
  await page.selectOption("#brand",{label:brand});
  await page.waitForFunction(({model})=>{
    const el=document.querySelector("#model");
    return el&&!el.disabled&&[...el.options].some(o=>o.textContent.trim().toLowerCase()===model.toLowerCase());
  },{model},{timeout:30000});
  await page.selectOption("#model",{label:model});
}

async function runSearch(page,spec){
  let searchResponse=null;
  const handler=async r=>{
    if(new URL(r.url()).pathname==="/api/search"&&r.request().method()==="POST"){
      try{searchResponse=await r.json();}catch(_){}
    }
  };
  page.on("response",handler);
  await page.click("#clear");
  await page.selectOption("#condition",{label:spec.condition==="used"?"Used only":spec.condition==="demo"?"Demo only":"Used + Demo"});
  await selectBrandModel(page,spec.brand,spec.model);
  await page.fill("#min",spec.min||"");
  await page.fill("#max",spec.max||"");
  await page.fill("#destination",spec.destination);
  await page.click("#search");
  await waitSearch(page);
  page.off("response",handler);

  const body=await page.locator("body").innerText();
  if(/Live search is currently unavailable|Live models unavailable|Unexpected error|Search failed|Application error/i.test(body))
    throw new Error("customer-facing error text detected");
  if(!searchResponse)throw new Error("did not capture /api/search response");

  const validModes=["live","inventory","live_coverage_fallback","live_fallback"];
  if(!searchResponse.ok||searchResponse.search_scope!=="india"||!validModes.includes(searchResponse.mode))
    throw new Error("invalid search contract: "+JSON.stringify({ok:searchResponse.ok,scope:searchResponse.search_scope,mode:searchResponse.mode}));

  const results=Array.isArray(searchResponse.results)?searchResponse.results:[];
  const badIdentity=results.filter(v=>{
    const actual=((v.brand||"")+" "+(v.model||"")).toLowerCase();
    return !actual.includes(spec.brand.toLowerCase())||!actual.includes(spec.model.toLowerCase());
  });
  if(badIdentity.length)throw new Error("identity leakage: "+badIdentity.slice(0,3).map(v=>(v.brand||"")+" "+(v.model||"")).join(", "));

  const actualCondition=v=>{
    const x=String(v.condition_signal||"").toLowerCase();
    if(x==="demo"||x==="demonstrator")return"demo";
    if(x==="used")return"used";
    return((v.variant||"")+" "+(v.source||"")).toLowerCase().includes("demo")?"demo":"used";
  };
  if(spec.condition!=="both"){
    const bad=results.filter(v=>actualCondition(v)!==spec.condition);
    if(bad.length)throw new Error("condition leakage: expected "+spec.condition+" but saw "+bad.length+" result(s)");
  }
  const badBudget=results.filter(v=>{
    const p=Number(v.price_lakh);
    return !Number.isFinite(p)||(spec.min&&p<Number(spec.min))||(spec.max&&p>Number(spec.max));
  });
  if(badBudget.length)throw new Error("budget leakage: "+badBudget.length+" result(s) outside requested range");

  return {
    resultCount:results.length,
    sourceCount:Array.isArray(searchResponse.sources)?searchResponse.sources.length:0,
    liveSources:Array.isArray(searchResponse.sources)?searchResponse.sources.filter(x=>x.status==="live").map(x=>x.name||x.source):[],
    mode:searchResponse.mode,
    destination:searchResponse.destination,
    modelOptions:await page.locator("#model option").allTextContents()
  };
}

async function testRefinementFilters(page){
  await page.selectOption("#condition",{label:"Used + Demo"});
  await page.selectOption("#brand",{label:"BMW"});
  await page.waitForFunction(()=>[...document.querySelectorAll("#model option")].some(o=>/X5/i.test(o.textContent||"")),null,{timeout:30000});
  await page.selectOption("#model",{label:"X5"});
  await page.fill("#destination","Bengaluru");
  await page.click("#search");
  await waitSearch(page);

  const before=await page.locator(".card").count(),checks=[];
  await page.fill("#fmin","30"); await page.dispatchEvent("#fmin","input");
  checks.push({filter:"price-min=30",count:await page.locator(".card").count()});
  await page.fill("#fmax","60"); await page.dispatchEvent("#fmax","input");
  checks.push({filter:"price-max=60",count:await page.locator(".card").count()});
  await page.selectOption("#year","5");
  checks.push({filter:"age<=5",count:await page.locator(".card").count()});

  if(await page.locator(".fuelCheck").count()!==4)throw new Error("expected 4 fuel filters");
  await page.check('.fuelCheck[value="petrol"]');
  checks.push({filter:"fuel=petrol",count:await page.locator(".card").count()});

  const cityCount=await page.locator("#city option").count();
  if(cityCount<1)throw new Error("seller location filter did not populate");
  if(cityCount>1){await page.selectOption("#city",{index:1});checks.push({filter:"seller-location",count:await page.locator(".card").count()});}

  for(const sort of ["match","price","gap","km","year"]){
    await page.selectOption("#sort",sort);
    checks.push({filter:"sort="+sort,count:await page.locator(".card").count()});
  }

  await page.click("#clear");
  const clearState=await page.evaluate(()=>({
    condition:document.querySelector("#condition").value,
    fmin:document.querySelector("#fmin").value,
    fmax:document.querySelector("#fmax").value,
    city:document.querySelector("#city").value,
    year:document.querySelector("#year").value,
    destination:document.querySelector("#destination").value,
    fuelChecked:[...document.querySelectorAll(".fuelCheck:checked")].length
  }));
  if(clearState.condition!=="both"||clearState.fmin||clearState.fmax||clearState.city||clearState.year||clearState.destination!=="Bengaluru"||clearState.fuelChecked)
    throw new Error("Clear all did not restore defaults: "+JSON.stringify(clearState));
  return {before,checks,clearState};
}

async function main(){
  const started=Date.now(),browser=await chromium.launch({headless:true}),results=[],pageErrors=[];
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1100}});
    page.on("pageerror",e=>pageErrors.push("pageerror: "+e.message));
    page.on("console",m=>{if(m.type()==="error")pageErrors.push("console: "+m.text());});
    await page.goto(BASE+"/?qa="+Date.now(),{waitUntil:"domcontentloaded",timeout:90000});
    await page.waitForSelector("#brand",{state:"visible",timeout:15000});
    const brandCount=await page.locator("#brand option").count();
    if(brandCount<5)throw new Error("brand dropdown has too few options: "+brandCount);

    for(const [brand,model] of journeys)for(const condition of conditions){
      const spec={brand,model,condition,min:"",max:"",destination:"Bengaluru"},t=Date.now();
      try{
        const detail=await runSearch(page,spec);
        results.push({category:"journey",status:"PASS",...spec,...detail,ms:Date.now()-t});
      }catch(e){
        const shot=path.join(OUT,"failure-"+safe(brand+"-"+model+"-"+condition)+"-"+Date.now()+".png");
        try{await page.screenshot({path:shot,fullPage:true});}catch(_){}
        results.push({category:"journey",status:"FAIL",...spec,error:errText(e),screenshot:shot,ms:Date.now()-t});
      }
    }

    for(const [brand,model] of journeys.slice(0,4))for(const b of budgets)for(const destination of destinations){
      const spec={brand,model,condition:"used",min:b.min,max:b.max,destination},t=Date.now();
      try{
        await page.goto(BASE+"/?qa="+Date.now(),{waitUntil:"domcontentloaded",timeout:90000});
        await page.waitForSelector("#brand",{state:"visible",timeout:15000});
        const detail=await runSearch(page,spec);
        results.push({category:"budget-destination",status:"PASS",...spec,budget:b.name,...detail,ms:Date.now()-t});
      }catch(e){
        const shot=path.join(OUT,"failure-"+safe(brand+"-"+model+"-"+b.name+"-"+destination)+"-"+Date.now()+".png");
        try{await page.screenshot({path:shot,fullPage:true});}catch(_){}
        results.push({category:"budget-destination",status:"FAIL",...spec,budget:b.name,error:errText(e),screenshot:shot,ms:Date.now()-t});
      }
    }

    try{
      await page.goto(BASE+"/?qa=filters-"+Date.now(),{waitUntil:"domcontentloaded",timeout:90000});
      await page.waitForSelector("#brand",{state:"visible",timeout:15000});
      results.push({category:"left-panel-filters",status:"PASS",...await testRefinementFilters(page)});
    }catch(e){
      const shot=path.join(OUT,"failure-left-panel-"+Date.now()+".png");
      try{await page.screenshot({path:shot,fullPage:true});}catch(_){}
      results.push({category:"left-panel-filters",status:"FAIL",error:errText(e),screenshot:shot});
    }

    const summary={generated_at:now(),base_url:BASE,duration_ms:Date.now()-started,brand_options:brandCount,total:results.length,passed:results.filter(x=>x.status==="PASS").length,failed:results.filter(x=>x.status==="FAIL").length,browser_errors:pageErrors,results};
    fs.writeFileSync(path.join(OUT,"qa-report.json"),JSON.stringify(summary,null,2));
    const rows=results.map(x=>"<tr class='"+x.status.toLowerCase()+"'><td>"+x.status+"</td><td>"+x.category+"</td><td>"+[x.brand,x.model,x.condition,x.budget,x.destination].filter(Boolean).join(" / ")+"</td><td>"+(x.resultCount??x.count??"")+"</td><td>"+(x.error||"")+"</td></tr>").join("");
    const html="<!doctype html><meta charset='utf-8'><title>CarScanner QA Report</title><style>body{font:14px system-ui;margin:30px}table{border-collapse:collapse;width:100%}th,td{padding:8px;border:1px solid #ddd;text-align:left}.pass{background:#eaf8f0}.fail{background:#fdecec}.k{display:inline-block;margin:8px;padding:12px;background:#f5f6f8;border-radius:8px}</style><h1>CarScanner QA Report</h1><div class='k'>Total "+summary.total+"</div><div class='k'>Passed "+summary.passed+"</div><div class='k'>Failed "+summary.failed+"</div><div class='k'>Browser errors "+summary.browser_errors.length+"</div><p>"+summary.generated_at+" · "+BASE+"</p><table><thead><tr><th>Status</th><th>Category</th><th>Scenario</th><th>Results</th><th>Error</th></tr></thead><tbody>"+rows+"</tbody></table>";
    fs.writeFileSync(path.join(OUT,"qa-report.html"),html);
    console.log(JSON.stringify({pass:summary.failed===0&&summary.browser_errors.length===0,...summary}));
    process.exitCode=summary.failed===0&&summary.browser_errors.length===0?0:1;
  }finally{await browser.close();}
}
main().catch(e=>{console.error(e.stack||e);process.exit(1);});

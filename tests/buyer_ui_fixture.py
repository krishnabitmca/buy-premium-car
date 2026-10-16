"""Independent API fixture for browser request/response contracts.
Database correctness is covered separately by real PostgreSQL integration tests.
"""
from datetime import datetime
import json

RECORDS=[
 {'brand':'BMW','model':'X5','price_lakh':49.5,'mfg_year':2024,'km':18000,'owners':1,'fuel':'Petrol','transmission':'Automatic','location':'Delhi','source':'Dealer A','url':'https://example.com/bmw-1','condition_signal':'used','body_type':'suv','live_verified':True,'data_consistent':True},
 {'brand':'BMW','model':'X5','price_lakh':55,'mfg_year':2023,'km':42000,'owners':2,'fuel':'Diesel','transmission':'Automatic','location':'Bengaluru','source':'Dealer B','url':'https://example.com/bmw-2','condition_signal':'used','body_type':'suv','live_verified':True,'data_consistent':True},
 {'brand':'Audi','model':'Q5','price_lakh':44,'mfg_year':2025,'km':8000,'owners':1,'fuel':'Petrol','transmission':'Automatic','location':'Mumbai','source':'Dealer A','url':'https://example.com/audi','condition_signal':'demo','body_type':'suv','live_verified':True,'data_consistent':True},
]

def response(body):
 rows=[]
 for v in RECORDS:
  if body.get('query') and not all(x.lower() in (v['brand']+' '+v['model']).lower().split() for x in body['query'].split()):continue
  if body.get('condition','both')!='both' and body['condition']!=v['condition_signal']:continue
  if body.get('seller_city') and body['seller_city']!=v['location']:continue
  if body.get('fuels') and v['fuel'].lower() not in body['fuels']:continue
  if body.get('transmissions') and v['transmission'].lower() not in body['transmissions']:continue
  if body.get('body_types') and v['body_type'] not in body['body_types']:continue
  if body.get('manufacture_year') and int(body['manufacture_year'])!=v['mfg_year']:continue
  if body.get('max_age_years') and datetime.now().year-v['mfg_year']>float(body['max_age_years']):continue
  if body.get('budget_min') is not None and v['price_lakh']<float(body['budget_min']):continue
  if body.get('budget_max') is not None and v['price_lakh']>float(body['budget_max']):continue
  if body.get('max_mileage_km') is not None and v['km']>int(body['max_mileage_km']):continue
  if body.get('max_owners') is not None and v['owners']>int(body['max_owners']):continue
  rows.append(dict(v))
 mode=body.get('sort','match')
 rows.sort(key=lambda v:v['km'] if mode=='km' else -v['mfg_year'] if mode=='year' else v['price_lakh'])
 return {'ok':True,'mode':'inventory_partial','search_scope':'india','results':rows,'inventory_total':len(rows),'has_more':False,
  'search_summary':{'result_count':len(rows),'cities':sorted({v['location'] for v in RECORDS}),'city_count':len({v['location'] for v in rows}),'sources':sorted({v['source'] for v in rows})},
  'sources':[{'name':'Dealer A','status':'inventory','listings_found':len(rows)}]}

async def install(page,requests):
 async def route(r):
  if '/api/catalog' in r.request.url:
   data={'ok':True,'mode':'live','brands':[{'name':'BMW'},{'name':'Audi'}],'models':[{'name':'X5'},{'name':'X3'}]}
  elif '/api/intent' in r.request.url:
   data={'ok':True,'intent':{'query':'BMW X5','condition':'both','destination':'Bengaluru','budget_min':None,'budget_max':55,'max_age_years':None,'fuels':['petrol'],'transmissions':['automatic'],'body_types':['suv'],'max_mileage_km':40000,'max_owners':None,'manufacture_year':None,'seller_city':'','sort':'price'},'clarifications':[],'unverified_criteria':['accident history']}
  else:
   requests.append(r.request.post_data_json);data=response(requests[-1])
  await r.fulfill(content_type='application/json',body=json.dumps(data))
 await page.route('**/api/**',route)

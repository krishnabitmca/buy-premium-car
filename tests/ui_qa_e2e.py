import asyncio
from playwright.async_api import async_playwright, expect
from buyer_ui_fixture import install

async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch();page=await browser.new_page();errors=[];requests=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  await install(page,requests);await page.goto('http://127.0.0.1:4173/index.html')
  await page.locator('#brand').select_option('BMW')
  await page.locator('#max').fill('55');await page.locator('#destination').fill('Bengaluru')
  await page.locator('#search').click();await expect(page.locator('.card')).to_have_count(2)
  assert requests[-1]['destination']=='Bengaluru' and requests[-1]['seller_city']==''
  await page.locator('.fuelCheck[value=petrol]').check();await expect(page.locator('.card')).to_have_count(1)
  assert requests[-1]['fuels']==['petrol']
  await page.locator('#maxKm').fill('10000');await page.locator('#maxKm').press('Tab')
  await expect(page.locator('.card')).to_have_count(0)
  await page.locator('#clear').click();await expect(page.locator('.card')).to_have_count(3)
  await page.locator('#sort').select_option('price');await expect(page.locator('.card .price').first).to_have_text('₹44.00L')
  await page.locator('#aiPrompt').fill('BMW X5 petrol automatic SUV under 55 lakh, less than 40000 km, buying in Bengaluru, accident-free')
  await page.locator('#askSearch').click();assert 'Opt in' in await page.locator('#aiReview').inner_text()
  await page.locator('#aiConsent').check();await page.locator('#askSearch').click()
  await expect(page.locator('#applyIntent')).to_be_visible()
  assert 'Cannot verify' in await page.locator('#aiReview').inner_text()
  assert len(requests)>0
  before=len(requests);await page.locator('#applyIntent').click();await expect(page.locator('.card')).to_have_count(1)
  assert len(requests)>before and requests[-1]['max_mileage_km']=='40000'
  assert requests[-1]['body_types']==['suv'] and requests[-1]['transmissions']==['automatic']
  await page.get_by_role('button',name='Why this car?',exact=True).click()
  await expect(page.get_by_role('dialog')).to_be_visible()
  assert 'Observed offers' in await page.locator('#modalBody').inner_text()
  assert await page.locator('.close').evaluate('(e)=>e===document.activeElement')
  await page.keyboard.press('Escape');await expect(page.get_by_role('dialog')).not_to_be_visible()
  assert await page.get_by_role('button',name='Why this car?',exact=True).evaluate('(e)=>e===document.activeElement')
  assert not errors,errors
  print('PASS: authoritative search, consent/review, unsupported criteria, offer provenance and keyboard dialog')
  await browser.close()

asyncio.run(main())

import asyncio
from playwright.async_api import async_playwright, expect
from buyer_ui_fixture import install, response

async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch();page=await browser.new_page();requests=[];errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  await install(page,requests);await page.goto('http://127.0.0.1:4173/index.html')
  await page.locator('#search').click();await expect(page.locator('.card')).to_have_count(3)
  tested=0
  for condition in ['both','used','demo']:
   for fuel in ['', 'petrol','diesel','electric']:
    await page.locator('#clear').click();await expect(page.locator('.card')).to_have_count(3)
    await page.locator('#condition').select_option(condition)
    if fuel:await page.locator('.fuelCheck[value='+fuel+']').check()
    async with page.expect_response(lambda r:'/api/search' in r.url):
     await page.locator('#search').click()
    await expect(page.locator('#search')).to_be_enabled()
    body=requests[-1]
    assert body['condition']==condition and body['fuels']==([fuel] if fuel else [])
    await expect(page.locator('.card')).to_have_count(len(response(body)['results']))
    tested+=1
  await page.locator('#clear').click();await expect(page.locator('.card')).to_have_count(3)
  await page.locator('#maxOwners').fill('1');await page.locator('#maxOwners').press('Tab')
  await expect(page.locator('.card')).to_have_count(2)
  await page.locator('#bodyType').select_option('sedan');await expect(page.locator('.card')).to_have_count(0)
  assert requests[-1]['body_types']==['sedan'] and requests[-1]['max_owners']=='1'
  assert not errors,errors
  print(f'PASS: {tested} condition/fuel server-request cases plus owner/body-style intersections')
  await browser.close()

asyncio.run(main())

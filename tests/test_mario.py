import asyncio
from playwright.async_api import async_playwright
import os

for k in ['http_proxy','https_proxy','HTTP_PROXY','HTTPS_PROXY']:
    os.environ.pop(k, None)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'])
        page = await browser.new_page()
        page.on("console", lambda msg: print(f"Browser console: {msg.text}"))
        page.on("pageerror", lambda err: print(f"Browser error: {err}"))
        
        await page.goto("http://localhost:8888/")
        await page.wait_for_selector("#marioStartBtn")
        await page.click("#marioStartBtn")
        await asyncio.sleep(1) # wait for game to run
        await page.locator("#marioCanvas").screenshot(path="mario_test.png")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

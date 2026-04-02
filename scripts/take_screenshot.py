import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=['--no-proxy-server'])
        page = await browser.new_page()
        await page.goto('http://127.0.0.1:8000/index.html', wait_until='networkidle')
        await page.screenshot(path='screenshot.png', full_page=True)
        await browser.close()

asyncio.run(main())

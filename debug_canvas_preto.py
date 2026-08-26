import asyncio
from playwright.async_api import async_playwright

OUTPUT = "logs_navegador.txt"

async def main():
    logs = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        def on_console(msg):
            logs.append(f"[CONSOLE {msg.type.upper()}] {msg.text}")

        def on_pageerror(err):
            logs.append(f"[PAGE ERROR] {err}")

        page.on("console", on_console)
        page.on("pageerror", on_pageerror)

        await page.goto("http://localhost:8000")
        await asyncio.sleep(8)
        await page.mouse.click(640, 360)
        await asyncio.sleep(5)
        await page.mouse.click(640, 360)
        await asyncio.sleep(30)

        await browser.close()

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(logs))

    print(f"Gravado {len(logs)} entradas em {OUTPUT}")

asyncio.run(main())

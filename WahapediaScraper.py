import asyncio
from playwright.async_api import async_playwright
import json
import os

BASE_URL = "https://wahapedia.ru"
FACTIONS = [
    # "adepta-sororitas",
    # "adeptus-custodes",
    # "adeptus-mechanicus",
    # "astra-militarum",
    # "grey-knights",
    # "imperial-agents",
    # "imperial-knights",
    "space-marines",
    # "chaos-daemons",
    # "chaos-knights",
    # "chaos-space-marines",
    # "death-guard",
    # "thousand-sons",
    # "world-eaters",
    # "aeldari",
    # "drukhari",
    # "genestealer-cults",
    #"leagues-of-votann",
    # "necrons",
    # "orks",
    # "t-au-empire",
    # "tyranids"
]
OUTPUT_FILE = "unit_index.json"
FAILED_FILE = "failed_factions.json"

async def get_unit_names_with_playwright(p, faction):
    url = f"{BASE_URL}/wh40k10ed/factions/{faction}/datasheets.html"
    print(f"➡️  Ophalen van datasheet-pagina met Playwright: {url}")

    browser = await p.chromium.launch(headless=True)
    page = await browser.new_page()
    await page.goto(url)

    try:
        await page.get_by_role("button", name="Ga verder met aanbevolen").click(timeout=3000)
        print("✅ Cookiebanner weggeklikt")
    except:
        print("⚠️ Geen cookiebanner gevonden")

    await page.wait_for_selector("div.NavColumns3")
    units = await page.query_selector_all(f"a[href^='/wh40k10ed/factions/{faction}/']")

    seen = set()
    filtered_units = []

    for unit in units:
        href = await unit.get_attribute("href")
        if href and href not in seen:
            if f"/{faction}/#" in href:
                continue
            seen.add(href)
            anchor = href.split("#")[-1] if "#" in href else href.split("/")[-1]
            filtered_units.append(anchor)

    await browser.close()
    return faction, filtered_units

async def save_to_json(faction_units):
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}

    data.update(faction_units)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

async def post_check_empty_factions(failed_factions):
    if not os.path.exists(OUTPUT_FILE):
        print("⚠️ Geen unit_index.json gevonden om te controleren.")
        return

    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("\n🔎 Controle op lege of incomplete factions:")
    for faction, units in data.items():
        if not units:
            print(f"⚠️ Geen eenheden gevonden voor: {faction}")
        elif len(units) < 5:
            print(f"❗ Mogelijk onvolledig ({len(units)} eenheden): {faction}")

    if failed_factions:
        print("\n❌ De volgende factions zijn volledig mislukt tijdens ophalen:")
        for faction in failed_factions:
            print(f"- {faction}")
        with open(FAILED_FILE, "w", encoding="utf-8") as f:
            json.dump(failed_factions, f, indent=2)

async def main():
    failed_factions = []
    async with async_playwright() as p:
        batch_size = 5
        for i in range(0, len(FACTIONS), batch_size):
            batch = FACTIONS[i:i+batch_size]
            tasks = [get_unit_names_with_playwright(p, faction) for faction in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for j, result in enumerate(results):
                faction = batch[j]
                if isinstance(result, Exception):
                    print(f"❌ Fout tijdens ophalen van {faction}: {result}")
                    failed_factions.append(faction)
                    continue

                faction, units = result
                print(f"\n🔍 Gevonden datasheets voor {faction}: ({len(units)} eenheden)")
                for anchor in units:
                    print(anchor)
                await save_to_json({faction: units})

    await post_check_empty_factions(failed_factions)

if __name__ == "__main__":
    asyncio.run(main())

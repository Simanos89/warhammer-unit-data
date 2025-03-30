import asyncio
from playwright.async_api import async_playwright
import json
import os
import re
import math
from asyncio import Semaphore

BASE_URL = "https://wahapedia.ru"
INPUT_FILE = "unit_index.json"
OUTPUT_FILE = "unit_details.json"
FAILED_FILE = "failed_units.json"
BATCH_SIZE = 40
RETRY_ATTEMPTS = 5

def get_unit_urls():
    if not os.path.exists(INPUT_FILE):
        print("⚠️ unit_index.json niet gevonden.")
        return []

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    urls = []
    for faction, units in data.items():
        for unit_name in units:
            urls.append((faction, f"{BASE_URL}/wh40k10ed/factions/{faction}/{unit_name}"))
    return urls

def extract_weapons(section_title, text):
    pattern = re.compile(
        rf"{section_title}\n+((?:[^\n]*\n)+?)(?=\n[A-Z][A-Z ]+|ABILITIES|UNIT COMPOSITION|WARGEAR OPTIONS|ENHANCEMENTS|KEYWORDS|STRATAGEMS|LED BY|DETACHMENT ABILITY|$)",
        re.DOTALL
    )
    match = pattern.search(text)
    if not match:
        return []

    block = match.group(1).strip()
    lines = [line.strip() for line in block.split("\n") if line.strip()]

    headers = []
    weapons = []
    i = 0
    while i < len(lines):
        if re.match(r"^(RANGE|MELEE|NAME|A|BS|WS|S|AP|D)$", lines[i].upper()):
            headers = []
            while i < len(lines) and re.match(r"^(RANGE|MELEE|NAME|A|BS|WS|S|AP|D)$", lines[i].upper()):
                headers.extend(lines[i].split())
                i += 1
            break
        i += 1

    if not headers:
        return []

    while i < len(lines):
        name = lines[i]
        if name.upper() in ["RANGE", "MELEE WEAPONS", "RANGED WEAPONS"]:
            break
        i += 1
        if i + len(headers) - 1 >= len(lines):
            break
        values = lines[i:i+len(headers)]
        i += len(headers)
        weapon = {"Name": name}
        for h, v in zip(headers, values):
            if h.upper() == "BS" or h.upper() == "WS":
                weapon["Ws" if h.upper() == "WS" else "Bs"] = v
            else:
                weapon[h.capitalize()] = v
        weapons.append(weapon)

    return weapons

def parse_unit_details(text):
    data = {}

    stat_block = re.search(r"M\n(.+?)\nT\n(.+?)\nSv\n(.+?)\nW\n(.+?)\nLd\n(.+?)\nOC\n(.+?)\n", text)
    if stat_block:
        data["Movement"] = stat_block.group(1).strip()
        data["Toughness"] = stat_block.group(2).strip()
        data["Save"] = stat_block.group(3).strip()
        data["Wounds"] = stat_block.group(4).strip()
        data["Leadership"] = stat_block.group(5).strip()
        data["OC"] = stat_block.group(6).strip()

    invul = re.search(r"INVULNERABLE SAVE\n(.+?)\n", text)
    if invul:
        data["Invulnerable Save"] = invul.group(1).strip()

    data["Ranged Weapons"] = extract_weapons("RANGED WEAPONS", text)
    data["Melee Weapons"] = extract_weapons("MELEE WEAPONS", text)

    wargear = re.search(r"WARGEAR OPTIONS\n(.+?)(\n\n|ABILITIES|UNIT COMPOSITION)", text, re.DOTALL)
    if wargear:
        options = [opt.strip() for opt in wargear.group(1).split("\n") if opt.strip()]
        data["Wargear Options"] = options

    abilities_block = re.search(r"ABILITIES\n(.+?)(\n\n|UNIT COMPOSITION|KEYWORDS)", text, re.DOTALL)
    if abilities_block:
        lines = [line.strip() for line in abilities_block.group(1).split("\n") if line.strip()]
        data["Abilities"] = lines

    unit_comp = re.search(r"UNIT COMPOSITION\n(.+?)(\n\n|KEYWORDS|STRATAGEMS)", text, re.DOTALL)
    if unit_comp:
        comp_lines = [line.strip() for line in unit_comp.group(1).split("\n") if line.strip()]
        data["Unit Composition"] = comp_lines

    keywords = re.search(r"KEYWORDS: (.+?)\nFACTION KEYWORDS:", text)
    faction_keywords = re.search(r"FACTION KEYWORDS:\n(.+?)\n", text, re.DOTALL)
    if keywords:
        data["Keywords"] = [kw.strip() for kw in keywords.group(1).split(",")]
    if faction_keywords:
        data["Faction Keywords"] = [kw.strip() for kw in faction_keywords.group(1).split("\n") if kw.strip()]

    points_match = re.findall(r"(\d+) models\s+(\d+)", text)
    if points_match:
        data["Points"] = [{"Models": m, "Cost": c} for m, c in points_match]

    enhancements = re.search(r"ENHANCEMENTS\n(.+?)(\n\n|STRATAGEMS|LED BY|DETACHMENT ABILITY)", text, re.DOTALL)
    if enhancements:
        enh = [line.strip() for line in enhancements.group(1).split("\n") if line.strip()]
        data["Enhancements"] = enh

    stratagems = re.findall(r"(.*?)\n(\d+CP)\n(.*?)\n", text)
    if stratagems:
        data["Stratagems"] = [{"Name": name.strip(), "CP": cp.strip(), "Source": src.strip()} for name, cp, src in stratagems]

    led_by = re.search(r"LED BY\nThis unit can be led by the following units:\n(.+?)(\n\n|DETACHMENT ABILITY)", text, re.DOTALL)
    if led_by:
        data["Led By"] = [unit.strip() for unit in led_by.group(1).split("\n") if unit.strip()]

    detach = re.search(r"DETACHMENT ABILITY\n(.+?)\n", text)
    if detach:
        data["Detachment Ability"] = detach.group(1).strip()

    return data

async def scrape_unit_details(playwright, faction, url, sem, index, total, all_data):
    async with sem:
        unit_name = url.split("/")[-1]
        if faction in all_data and unit_name in all_data[faction]:
            print(f"🔁 {unit_name} al aanwezig, overslaan.")
            return faction, unit_name, None, "duplicate"

        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url)
            try:
                await page.get_by_role("button", name="Ga verder met aanbevolen").click(timeout=3000)
            except:
                pass
            await page.wait_for_selector("#wrapper")
            content = await page.inner_text("#wrapper")
            print(f"✅ {unit_name} voltooid ({index+1}/{total})")
            await browser.close()
            return faction, unit_name, parse_unit_details(content), "success"
        except Exception as e:
            await browser.close()
            print(f"❌ Fout bij {url}: {e}")
            return faction, unit_name, None, "failed"

async def process_batch(batch, playwright, sem, all_data, total_count, failed_units, duplicates, start_index):
    tasks = [
        scrape_unit_details(playwright, faction, url, sem, i + start_index, total_count, all_data)
        for i, (faction, url) in enumerate(batch)
    ]
    results = await asyncio.gather(*tasks)

    for faction, unit_name, unit_data, status in results:
        if status == "success":
            if faction not in all_data:
                all_data[faction] = {}
            all_data[faction][unit_name] = unit_data
        elif status == "duplicate":
            duplicates.append({"faction": faction, "unit": unit_name})
        elif status == "failed":
            failed_units.append({"faction": faction, "unit": unit_name})

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

    with open(FAILED_FILE, "w", encoding="utf-8") as f:
        json.dump(failed_units, f, indent=2, ensure_ascii=False)

    if duplicates:
        with open("duplicates_skipped.json", "w", encoding="utf-8") as f:
            json.dump(duplicates, f, indent=2, ensure_ascii=False)

async def main():
    urls = get_unit_urls()
    total = len(urls)
    sem = Semaphore(40)

    if os.path.exists(OUTPUT_FILE) and os.path.getsize(OUTPUT_FILE) > 0:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            all_data = json.load(f)
    else:
        all_data = {}

    failed_units = []
    duplicates = []

    async with async_playwright() as p:
        for batch_start in range(0, total, BATCH_SIZE):
            batch = urls[batch_start:batch_start + BATCH_SIZE]
            await process_batch(batch, p, sem, all_data, total, failed_units, duplicates, batch_start)

        for attempt in range(RETRY_ATTEMPTS):
            if not failed_units:
                break
            print(f"🔁 Retry ronde {attempt + 1} voor {len(failed_units)} units...")
            retry_urls = [(u["faction"], f"{BASE_URL}/wh40k10ed/factions/{u['faction']}/{u['unit']}") for u in failed_units]
            failed_units = []
            await process_batch(retry_urls, p, sem, all_data, len(retry_urls), failed_units, duplicates, 0)

if __name__ == "__main__":
    asyncio.run(main())
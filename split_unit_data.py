import json
import os

INPUT_FILE = "unit_details.json"
OUTPUT_DIR = "data"
FULL_OUTPUT_FILE = os.path.join(OUTPUT_DIR, "full_unit_data.json")

# Laad alles in
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    full_data = json.load(f)

# Maak map aan indien nodig
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Schrijf alles weg in één bestand
with open(FULL_OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(full_data, f, indent=2, ensure_ascii=False)

# Splits per faction en schrijf naar losse bestanden
for faction, units in full_data.items():
    filename = os.path.join(OUTPUT_DIR, f"{faction}.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({faction: units}, f, indent=2, ensure_ascii=False)

print(f"✅ Opsplitsing voltooid! Alles opgeslagen in ./{OUTPUT_DIR}")

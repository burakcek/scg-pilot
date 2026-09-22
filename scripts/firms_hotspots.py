"""Optional NASA FIRMS hotspot fetcher. No key means a safe empty result."""
import os
import requests
from dotenv import load_dotenv
load_dotenv()

def fetch_hotspots(area="world", days=1):
    key = os.getenv("FIRMS_MAP_KEY")
    if not key:
        return []
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_NRT/{area}/{days}"
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    lines = response.text.splitlines()
    if not lines: return []
    headers = lines[0].split(",")
    return [dict(zip(headers, line.split(","))) for line in lines[1:]]

if __name__ == "__main__":
    print(fetch_hotspots())

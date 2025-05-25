import requests
from bs4 import BeautifulSoup
import os

base_url = "https://usgodae.org/pub/outgoing/fnmoc/models/navgem_0.5/2025/2025050518/"
outdir = "navgem_data"
os.makedirs(outdir, exist_ok=True)

resp = requests.get(base_url)
soup = BeautifulSoup(resp.text, "html.parser")

for link in soup.find_all("a"):
    href = link.get("href")
    if href and not href.startswith("/") and not href.endswith("/"):
        file_url = base_url + href
        if '0056_00000' in file_url:
            r = requests.get(file_url)
            with open(os.path.join(outdir, href), "wb") as f:
                f.write(r.content)

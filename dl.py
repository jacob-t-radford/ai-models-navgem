import requests
from bs4 import BeautifulSoup
import os
import sys
import subprocess as sp

year=sys.argv[1]
month=sys.argv[2]
day=sys.argv[3]
hh=sys.argv[4]

base_url = f"https://usgodae.org/pub/outgoing/fnmoc/models/navgem_0.5/{year}/{year}{month}{day}{hh}/"
outdir = f"navgem_data/{year}{month}{day}{hh}/"
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

sp.call(f"cat navgem_data/{year}{month}{day}{hh}/* > navgem_data/{year}{month}{day}{hh}/merged",shell=True)

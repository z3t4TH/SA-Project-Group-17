"""Local, redistributable illustrative menu assets; no schema or price changes."""
from functools import lru_cache
from config import ROOT
import json

@lru_cache(maxsize=1)
def image_manifest():
    items=json.loads((ROOT/'assets/menu/image-credits.json').read_text())
    return dict(fallback='/static/menu-images/placeholder.svg',
        by_key={i['menu_key']:i['file'] for i in items},
        by_name={i['menu_name']:i['file'] for i in items})


def allowed_files():
    return {i['file'].rsplit('/',1)[-1] for i in json.loads((ROOT/'assets/menu/image-credits.json').read_text())}|{'placeholder.svg'}

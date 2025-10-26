import json
import polars as pl
from pathlib import Path
root = Path(r'c:/Users/LEGION/Documents/Data Science/Python & R Scripts/fraud-detection-system')
with open(root / 'artefacts/spatial/world_countries/raw/countries.geojson', 'r', encoding='utf-8') as fh:
    countries = json.load(fh)
geo_set = set((feat['properties'].get('ISO3166-1-Alpha-2','') or '').strip().upper() for feat in countries['features'])
share_set = set(pl.read_parquet(root / 'reference/network/settlement_shares/2025-10-26/settlement_shares.parquet')['country_iso'].to_list())
missing = sorted(share_set - geo_set)
print('missing count', len(missing))
print(missing[:20])

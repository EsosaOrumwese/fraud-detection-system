import json
from pathlib import Path
path = Path(r'artefacts/spatial/tz_world/2025a/raw/extracted/combined-with-oceans.json')
with path.open('r', encoding='utf-8') as f:
    data = json.load(f)
print(data['features'][0]['properties'].keys())
print(data['features'][0]['properties'])

"""Build an unsigned Firefox development package without bundling local data."""
import json
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
source = root / 'extension'
version = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))['version']
destination = root / 'dist' / f'screen-squatters-firefox-{version}.xpi'
destination.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as package:
    for path in sorted(source.iterdir()):
        if path.is_file() and path.suffix in ('.json','.js','.html','.css','.svg','.png'):
            package.write(path, path.name)
print(destination)

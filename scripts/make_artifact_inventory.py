from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    script = ROOT / 'scripts' / 'build_release_package.py'
    proc = subprocess.run([sys.executable, str(script)], cwd=str(ROOT))
    if proc.returncode != 0:
        return proc.returncode
    print(json.dumps({'ok': True, 'message': 'release tables regenerated from local artifacts'}, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

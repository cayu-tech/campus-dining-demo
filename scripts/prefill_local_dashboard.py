"""Apply the demo prompt to the pinned installed dashboard's New Run field.

Local asset customization only; rerun after uv sync replaces Cayu. Fail closed
if a different dashboard build changes the expected field initialization.
"""

import json
import re
import sysconfig
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    source = (root / "viewer-ui/src/routes/run.tsx").read_text()
    match = re.search(r'const \[prompt, setPrompt\] = useState\(("[^\n]+")\)', source)
    if match is None:
        raise SystemExit("Could not identify the demo prompt")
    prompt = json.loads(match.group(1))
    asset = Path(sysconfig.get_paths()["purelib"]) / (
        "cayu/server/dashboard/assets/run-CdDdjfA-.js"
    )
    original = "[t,r]=(0,H.useState)(``),[c,l]"
    replacement = f"[t,r]=(0,H.useState)({json.dumps(prompt)}),[c,l]"
    content = asset.read_text()
    if replacement in content:
        print("Dining prompt is already configured")
        return
    if content.count(original) != 1:
        raise SystemExit("Dashboard build changed; review the prompt customization")
    asset.write_text(content.replace(original, replacement, 1))
    print("Dining prompt configured for the local dashboard")


if __name__ == "__main__":
    main()

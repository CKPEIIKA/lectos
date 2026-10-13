"""Print every string marked for translation (tr("...") / noop("...")) in the package, one per line (repr)."""

import ast
import sys
from pathlib import Path

NAMES = {"tr", "noop"}


def marked(root: Path) -> list[str]:
    found: dict[str, None] = {}
    for path in sorted(root.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in NAMES
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                found.setdefault(node.args[0].value)
    return list(found)


if __name__ == "__main__":
    for text in marked(Path(sys.argv[1] if len(sys.argv) > 1 else "lectos")):
        print(repr(text))

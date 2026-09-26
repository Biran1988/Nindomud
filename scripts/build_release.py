"""Package a data-safe source archive and portable single-file Python server."""

import argparse
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def build(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    source_files = sorted(ROOT.glob("*.py"))
    archive = output / "Nindo_mud.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(ROOT.rglob("*")):
            relative = path.relative_to(ROOT)
            if not path.is_file() or any(part in {".git", "data", "__pycache__", ".pytest_cache"} or part.startswith("data_test") for part in relative.parts):
                continue
            if relative.suffix not in {".py", ".md", ".yml", ".yaml", ".txt"} and relative.name not in {".gitignore"}:
                continue
            zf.write(path, relative)

    standalone = output / "Nindo_mud"
    with standalone.open("w", encoding="utf-8") as file:
        file.write('#!/usr/bin/env python3\n"""Nindo_mud single-file server; saves remain beside this file in data/."""\n')
        file.write("import importlib.abc\nimport importlib.util\nimport os\nimport sys\n")
        file.write("_ROOT = os.path.dirname(os.path.abspath(__file__))\n_SOURCES = {\n")
        for path in source_files:
            file.write(f"    {path.stem!r}: {path.read_text(encoding='utf-8')!r},\n")
        file.write("}\n")
        file.write("class _BundledModules(importlib.abc.MetaPathFinder, importlib.abc.Loader):\n")
        file.write("    def find_spec(self, fullname, path=None, target=None):\n")
        file.write("        return importlib.util.spec_from_loader(fullname, self) if fullname in _SOURCES else None\n")
        file.write("    def create_module(self, spec):\n        return None\n")
        file.write("    def exec_module(self, module):\n")
        file.write("        module.__file__ = os.path.join(_ROOT, module.__name__ + '.py')\n")
        file.write("        exec(compile(_SOURCES[module.__name__], module.__file__, 'exec'), module.__dict__)\n")
        file.write("sys.meta_path.insert(0, _BundledModules())\n")
        file.write("def start():\n")
        file.write("    namespace = {'__name__': '__main__', '__file__': os.path.join(_ROOT, 'main.py')}\n")
        file.write("    exec(compile(_SOURCES['main'], namespace['__file__'], 'exec'), namespace)\n")
        file.write("if __name__ == '__main__':\n    start()\n")
    standalone.chmod(0o755)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    build(parser.parse_args().output)

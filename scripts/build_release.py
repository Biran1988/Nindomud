"""Package a data-safe source archive and portable single-file Python server."""

import argparse
import base64
import json
import stat
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def assert_data_safe(archive: Path) -> None:
    """HARD RELEASE RULE: a drag-and-drop ZIP must never contain /data.

    Also reject absolute/traversal paths and Windows separators, so no ZIP
    member can escape the installation directory and touch runtime saves.
    The rule applies even when future packaging code changes.
    """
    with zipfile.ZipFile(archive) as package:
        for entry in package.infolist():
            name = entry.filename
            parts = name.rstrip("/").split("/")
            if ((entry.external_attr >> 16) & 0o170000 == stat.S_IFLNK
                    or not name or name.startswith(("/", "\\"))
                    or "\\" in name or any(part in ("", ".", "..") for part in parts)
                    or ":" in parts[0] or any(part.casefold() == "data" for part in parts)):
                raise ValueError(f"Unsafe release ZIP entry (would risk saved data): {name!r}")


def build(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    source_files = sorted(path for path in ROOT.glob("*.py") if not path.is_symlink())
    sys.path.insert(0, str(ROOT))
    import help_system
    standalone = output / "Nindo_mud"
    with standalone.open("w", encoding="utf-8") as file:
        file.write('#!/usr/bin/env python3\n"""Nindo_mud single-file server; saves remain beside this file in data/."""\n')
        file.write("import importlib.abc\nimport importlib.util\nimport os\nimport sys\n")
        file.write("_ROOT = os.path.dirname(os.path.abspath(__file__))\n_SOURCES = {\n")
        for path in source_files:
            file.write(f"    {path.stem!r}: {path.read_text(encoding='utf-8')!r},\n")
        file.write("}\n")
        file.write("import base64\n_COUNTRY_DATABASE = base64.b64decode(" + repr(base64.b64encode((ROOT / "geoip/country.csv.gz").read_bytes()).decode("ascii")) + ")\n")
        file.write("class _BundledModules(importlib.abc.MetaPathFinder, importlib.abc.Loader):\n")
        file.write("    def find_spec(self, fullname, path=None, target=None):\n")
        file.write("        return importlib.util.spec_from_loader(fullname, self) if fullname in _SOURCES else None\n")
        file.write("    def create_module(self, spec):\n        return None\n")
        file.write("    def exec_module(self, module):\n")
        file.write("        module.__file__ = os.path.join(_ROOT, module.__name__ + '.py')\n")
        file.write("        exec(compile(_SOURCES[module.__name__], module.__file__, 'exec'), module.__dict__)\n")
        file.write("        if module.__name__ == 'country_geo':\n            module.BUNDLED_DATABASE = _COUNTRY_DATABASE\n")
        file.write("sys.meta_path.insert(0, _BundledModules())\n")
        file.write("def start():\n")
        file.write("    namespace = {'__name__': '__main__', '__file__': os.path.join(_ROOT, 'main.py')}\n")
        file.write("    exec(compile(_SOURCES['main'], namespace['__file__'], 'exec'), namespace)\n")
        file.write("if __name__ == '__main__':\n")
        file.write("    if sys.argv[1:] == ['--preflight']:\n")
        file.write("        import main, session, combat, commands, help_system, jutsu_colors, mangekyo_discovery\n")
        file.write("    else:\n        start()\n")
    standalone.chmod(0o755)


    archive = output / "Nindo_mud.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(ROOT.rglob("*")):
            relative = path.relative_to(ROOT)
            if not path.is_file() or path.is_symlink() or any(part.casefold() in {".git", "data", "__pycache__", ".pytest_cache"} or part.casefold().startswith("data_test") for part in relative.parts):
                continue
            if relative.suffix not in {".py", ".md", ".yml", ".yaml", ".txt", ".html"} and relative.name not in {".gitignore"} and relative.as_posix() != "geoip/country.csv.gz":
                continue
            zf.write(path, relative)
        # Keep the runnable server in the standard ZIP alongside the sources.
        # It embeds the same, newly rebuilt Python modules for this release.
        zf.write(standalone, "Nindo_mud")
        # Ship readable, individual helpfiles as release content. Keep these
        # outside data/help so extracting the archive cannot overwrite saved
        # staff-written pages; the server seeds/refreshes its own data/help.
        for entry in help_system.DEFAULT_HELP_ENTRIES:
            name = help_system._slug(entry["primary_keyword"]) + ".json"
            zf.writestr("helpfiles/" + name, json.dumps(entry, indent=2) + "\n")

    # Never publish an archive capable of overwriting the live data/ tree.
    assert_data_safe(archive)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    build(parser.parse_args().output)

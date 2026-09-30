"""Validate the local probe against facts extracted from the installed game pack."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.audit_local_mod_surface import read_resource


REQUIRED_DIRS = ("art", "scripts", "sfx")


def installed_contract(pck: Path) -> tuple[set[str], str]:
    raw = read_resource(pck)
    source = raw.decode("utf-8").replace('\\"', '"')
    match = re.search(r"var base_mod_fields = \{([^\n]+)\}", source)
    if not match:
        raise ValueError("Installed base_mod_fields declaration was not found")
    fields = set(re.findall(r'"([^"]+)"\s*:', match.group(1)))
    if not fields or "value_text" not in fields:
        raise ValueError("Installed field contract is incomplete")
    validator_start = source.index("func malicious_mod(")
    validator_end = source.index("\nfunc ", validator_start + 20)
    validator = source[validator_start:validator_end]
    required_fragments = (
        'm.substr(m.length() - 3, -1) != ".gd"',
        'file_text.substr(inc - 10, 13) == "func _init():"',
        "base_mod_fields.keys().has(key)",
        'key != "mod_type"',
        "return uhoh or (tabs and spaces) or quoted",
    )
    if not all(fragment in validator for fragment in required_fragments):
        raise ValueError("Installed validator differs from the supported contract")
    return fields | {"mod_type"}, hashlib.sha256(raw).hexdigest()


def _outside_quotes(source: str):
    quoted = False
    escaped = False
    for index, char in enumerate(source):
        if char == '"' and not escaped:
            quoted = not quoted
            yield index, char, False
        else:
            yield index, char, quoted
        escaped = char == "\\" and not escaped
        if char != "\\":
            escaped = False
    if quoted:
        raise ValueError("unbalanced quote")


def validate_script(path: Path, allowed_fields: set[str]) -> list[str]:
    errors = []
    if path.suffix != ".gd":
        return ["script extension is not .gd"]
    source = path.read_text(encoding="utf-8")
    if "\t" in source and re.search(r"(?m)^ {4,}\S", source):
        errors.append("mixed tabs and four-space indentation")

    stack = []
    pairs = {")": "(", "]": "[", "}": "{"}
    try:
        visible = list(_outside_quotes(source))
    except ValueError as exc:
        errors.append(str(exc))
        visible = []
    for index, char, quoted in visible:
        if quoted:
            continue
        if char in "([{":
            if char == "(" and source[max(0, index - 10):index + 1] != "func _init(":
                errors.append("function call or unsupported parenthesis")
            stack.append(char)
        elif char in pairs:
            if not stack or stack.pop() != pairs[char]:
                errors.append("unbalanced delimiter")
                break
    if stack:
        errors.append("unbalanced delimiter")

    for line in source.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("extends ", "func ")):
            continue
        match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*=(?!=)", stripped)
        if match and match.group(1) not in allowed_fields:
            errors.append(f"unknown assignment: {match.group(1)}")
    return sorted(set(errors))


def validate_package(package: Path, pck: Path) -> dict:
    fields, main_sha = installed_contract(pck)
    errors = []
    if not (package / "SELECTME.LBAL").is_file():
        errors.append("missing SELECTME.LBAL")
    for name in REQUIRED_DIRS:
        if not (package / name).is_dir():
            errors.append(f"missing directory: {name}")
    forbidden = [p.relative_to(package).as_posix() for p in package.rglob("*")
                 if p.is_file() and (p.suffix.lower() in {".dll", ".exe", ".py", ".pt"}
                                     or p.name == "workshop_info.json"
                                     or "-upload" in p.parts)]
    if forbidden:
        errors.append("forbidden payload: " + ", ".join(sorted(forbidden)))
    scripts = sorted((package / "scripts").glob("*.gd")) if (package / "scripts").is_dir() else []
    if not scripts:
        errors.append("no .gd scripts")
    script_results = {}
    for script in scripts:
        script_errors = validate_script(script, fields)
        script_results[script.name] = {
            "sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
            "errors": script_errors,
        }
        errors.extend(f"{script.name}: {message}" for message in script_errors)
    return {
        "scope": "Static parity check for the probe syntax; not native execution or Workshop publication",
        "package": str(package.resolve()),
        "installed_main_sha256": main_sha,
        "required_layout": ["SELECTME.LBAL", *REQUIRED_DIRS],
        "scripts": script_results,
        "valid": not errors,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("pck", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_package(args.package, args.pck)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()

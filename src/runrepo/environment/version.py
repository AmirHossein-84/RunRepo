"""Deterministic semantic and runtime version requirement evaluator."""

import re

VERSION_EXTRACT_REGEX = re.compile(r"(\d+(?:\.\d+)*(?:-[0-9A-Za-z.-]+)?)")


def clean_version_string(raw: str | None) -> str | None:
    """Extract clean version number from strings like 'v22.15.0', 'Python 3.14.0', 'Docker version 28.3.0'."""
    if not raw:
        return None

    # Strip prefixes and search for version pattern
    match = VERSION_EXTRACT_REGEX.search(raw)
    if match:
        return match.group(1).lstrip("v")
    return None


def parse_version_tuple(v_str: str) -> tuple[int, ...] | None:
    """Parse version string into a comparable tuple of integers (e.g. '22.15.0' -> (22, 15, 0))."""
    cleaned = clean_version_string(v_str)
    if not cleaned:
        return None

    # Remove any build or pre-release suffixes for integer tuple comparison
    main_part = cleaned.split("-")[0].split("+")[0]
    parts: list[int] = []
    for p in main_part.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            break

    return tuple(parts) if parts else None


def _pad_tuple(t: tuple[int, ...], length: int = 3) -> tuple[int, ...]:
    """Pad integer tuple with zeros up to specified length."""
    if len(t) >= length:
        return t
    return t + (0,) * (length - len(t))


def _compare_versions(v1: tuple[int, ...], op: str, v2: tuple[int, ...]) -> bool:
    """Compare two version tuples using standard relational operators."""
    max_len = max(len(v1), len(v2))
    p1 = _pad_tuple(v1, max_len)
    p2 = _pad_tuple(v2, max_len)

    if op == ">=":
        return p1 >= p2
    elif op == "<=":
        return p1 <= p2
    elif op == ">":
        return p1 > p2
    elif op == "<":
        return p1 < p2
    elif op in ("==", "="):
        return p1 == p2
    elif op == "!=":
        return p1 != p2
    return False


def _evaluate_single_clause(installed: tuple[int, ...], clause: str) -> bool | None:
    """Evaluate a single constraint clause against an installed version tuple."""
    c = clause.strip()
    if not c or c in ("*", "x", "X"):
        return True

    # Check relational operators
    for op in (">=", "<=", "!=", "==", ">", "<", "="):
        if c.startswith(op):
            target_str = c[len(op) :].strip()
            target_tuple = parse_version_tuple(target_str)
            if target_tuple is None:
                return None
            return _compare_versions(installed, op, target_tuple)

    # Check caret (^)
    if c.startswith("^"):
        target_tuple = parse_version_tuple(c[1:].strip())
        if target_tuple is None:
            return None
        # Caret allows changes that do not modify the left-most non-zero digit
        if _compare_versions(installed, "<", target_tuple):
            return False

        if target_tuple[0] > 0:
            upper = (target_tuple[0] + 1, 0, 0)
        elif len(target_tuple) > 1 and target_tuple[1] > 0:
            upper = (0, target_tuple[1] + 1, 0)
        elif len(target_tuple) > 2:
            upper = (0, 0, target_tuple[2] + 1)
        else:
            upper = (1, 0, 0)

        return _compare_versions(installed, "<", upper)

    # Check tilde (~)
    if c.startswith("~"):
        target_tuple = parse_version_tuple(c[1:].strip())
        if target_tuple is None:
            return None
        if _compare_versions(installed, "<", target_tuple):
            return False

        if len(target_tuple) >= 2:
            upper = (target_tuple[0], target_tuple[1] + 1, 0)
        else:
            upper = (target_tuple[0] + 1, 0, 0)

        return _compare_versions(installed, "<", upper)

    # Check wildcard pattern like '18.x' or '20.X'
    if ".x" in c.lower() or ".*" in c:
        prefix = c.lower().replace(".x", "").replace(".*", "").strip()
        target_tuple = parse_version_tuple(prefix)
        if target_tuple is None:
            return None
        for i, val in enumerate(target_tuple):
            if i >= len(installed) or installed[i] != val:
                return False
        return True

    # Exact or prefix match (e.g. '22' or '3.11' or '22.15.0')
    target_tuple = parse_version_tuple(c)
    if target_tuple is None:
        return None

    # If target is single number (e.g. '22'), matches any 22.x.x
    if len(target_tuple) == 1:
        return installed[0] == target_tuple[0]
    # If target is 2 numbers (e.g. '3.11'), matches any 3.11.x
    elif len(target_tuple) == 2:
        return len(installed) >= 2 and installed[0] == target_tuple[0] and installed[1] == target_tuple[1]
    # If 3 numbers, exact match
    return _compare_versions(installed, "==", target_tuple)


def evaluate_version_requirement(
    installed_version: str | None,
    required_version: str | None,
) -> bool | None:
    """Evaluate whether an installed version string satisfies a required version constraint.

    Returns:
        True: Requirement is satisfied.
        False: Requirement is violated.
        None: Requirement or installed version could not be reliably parsed (UNKNOWN).
    """
    if not required_version or required_version.strip() in ("", "*"):
        return True

    if not installed_version:
        return False

    raw_req_lower = required_version.strip().lower()
    if raw_req_lower in ("any", "latest", "lts", "lts/*", "stable", "node", "current", "system") or raw_req_lower.startswith("lts/"):
        return True

    installed_tuple = parse_version_tuple(installed_version)
    if installed_tuple is None:
        return None

    # Clean and split compound requirements (e.g. '>=20 <23', '>=3.11, <3.14', '^18.0.0 || ^20.0.0')
    raw_req = required_version.strip()

    # Handle OR conditions ('||')
    if "||" in raw_req:
        sub_results = [
            evaluate_version_requirement(installed_version, part.strip())
            for part in raw_req.split("||")
        ]
        if any(r is True for r in sub_results):
            return True
        if all(r is False for r in sub_results):
            return False
        return None

    # Handle AND clauses separated by comma or whitespace between operators
    # e.g. '>=20 <23' or '>=3.11, <3.14'
    normalized = raw_req.replace(",", " ")
    # Split by whitespace, but keep comparison tokens together
    tokens = normalized.split()
    clauses: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in (">=", "<=", "!=", "==", ">", "<", "=") and i + 1 < len(tokens):
            clauses.append(tok + tokens[i + 1])
            i += 2
        else:
            clauses.append(tok)
            i += 1

    for clause in clauses:
        res = _evaluate_single_clause(installed_tuple, clause)
        if res is False:
            return False
        if res is None:
            return None

    return True

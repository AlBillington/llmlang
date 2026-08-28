"""
Parser for the llmlang v0.2 format (tab-indented outline).

Only `@policy:` is reserved, valid at root, folder, or file/class scope,
cascading down to everything nested beneath wherever it's declared.

Everything else is shape-inferred, not keyword-driven:
  - A header with a file extension ("UrlShortener.py:") is a file. One
    without ("Backend:") is a folder. Folders may contain more folders
    or files; nothing else.
  - Inside a file: a header whose own children are further headers is
    a class (a grouping, used when one file holds more than one). A
    header whose own children are "- " bullets is a source-handled
    entry - the thing that gets a handle and maps to one method,
    property, or data shape. A file can contain entries directly (no
    class layer) for the non-OOP case of a flat module of functions.
  - A bare "- " bullet sitting directly under a file or class (not
    under any entry) is a class/file-level bullet - for guarantees
    that span more than one entry, since it has no single entry's code
    to attach to.
  - A source-handled entry's bullets, in any number, all describe that
    one entry together - no one-bullet-per-entry limit.
  - "~ " lines are test bullets. They can live on a named entry, file,
    or class node, and each one must map to a source test comment with
    the same text and the node's canonical name in an llm-test handle.
  - A header written "Name data (summary):" under a file or class is a
    data entry. It has bullets describing contained data shape and uses
    the same source-handle and lockfile path as named entries.
"""
from pathlib import Path


# private helper of parse(), not independent architecture [llm-exempt]
def _new_node(name, ext=None, summary=None, line=None, entry_point=None):
    return {
        "kind": None,
        "name": name,
        "ext": ext,
        "summary": summary,
        "line": line,
        "policy": [],
        "bullets": [],
        "tests": [],
        "children": {},
        "entry_point": entry_point,
    }


# private helper of parse(), not independent architecture [llm-exempt]
def _finalize(node, path_desc):
    if node["kind"] is None:
        if not node["bullets"] and not node["tests"]:
            raise ValueError(
                f"{path_desc} has no content (needs at least one bullet, test, or nested entry)"
            )
        node["kind"] = "entry"
    if node["kind"] in ("entry", "data") and not node["summary"]:
        raise ValueError(f"{path_desc} is missing a parenthesized summary")
    if node["kind"] == "data" and node["tests"]:
        raise ValueError(f"{path_desc} is a data entry and cannot have test bullets")
    if node["entry_point"] is not None and node["kind"] != "entry":
        raise ValueError(f"{path_desc} has @entry-point but is not a named entry")
    for name, child in node["children"].items():
        _finalize(child, f"{path_desc}.{name}")


# private helper of parse(), not independent architecture [llm-exempt]
def _parse_header(content):
    header = content[:-1]
    summary = None
    marker = None
    if header.endswith(")") and " (" in header:
        header, summary = header.rsplit(" (", 1)
        summary = summary[:-1].strip()
    parts = header.split(None, 1)
    name = parts[0]
    if len(parts) > 1 and parts[1].strip() == "data":
        marker = "data"
    return name, summary, marker


_ARROW_PREFIXES = ("→ call ", "← return ")
_CONTENT_PREFIXES = ("- ",) + _ARROW_PREFIXES


# private helper of parse(), not independent architecture [llm-exempt]
def _bullet_text(content: str, relative_depth: int) -> str:
    if content.startswith(_ARROW_PREFIXES):
        return "\t" * relative_depth + content
    if relative_depth <= 0:
        return content[2:]
    return "\t" * relative_depth + "- " + content[2:]


# private helper of parse(), not independent architecture [llm-exempt]
def _content_for_storage(content: str) -> str:
    if content.startswith(_ARROW_PREFIXES):
        return content
    return content[2:]


# private helper of parse(), not independent architecture [llm-exempt]
def _parse_entry_point(content: str):
    """Returns (is_entry_point_line, label) - label is None for a bare
    @entry-point, or the text inside @entry-point(...)."""
    if content == "@entry-point":
        return True, None
    if content.startswith("@entry-point(") and content.endswith(")"):
        return True, content[len("@entry-point(") : -1].strip()
    return False, None


# parses a tab-indented llmlang file into a tree of folders, files, classes, and entries [llm:llmlang.parser.parse]
def parse(path):
    raw_lines = Path(path).read_text(encoding="utf-8").splitlines()
    root = _new_node("", None)
    root["kind"] = "folder"
    stack = [(-1, root)]
    pending_entry_point = False
    pending_entry_point_label = None

    for line_no, raw_line in enumerate(raw_lines, start=1):
        if not raw_line.strip():
            continue
        depth = len(raw_line) - len(raw_line.lstrip("\t"))
        content = raw_line.strip()

        while len(stack) > 1 and stack[-1][0] >= depth:
            stack.pop()

        _, parent = stack[-1]

        is_entry_point, entry_point_label = _parse_entry_point(content)
        if is_entry_point:
            assert isinstance(parent, dict) and parent["kind"] in ("file", "class"), (
                f"@entry-point is only valid immediately before a named entry: {content!r}"
            )
            pending_entry_point = True
            pending_entry_point_label = entry_point_label
            continue

        if content.startswith(_CONTENT_PREFIXES) or content.startswith("~ "):
            if isinstance(parent, list):
                assert content.startswith("- "), f"a test bullet isn't valid here: {content!r}"
                parent.append(_content_for_storage(content))
                stack.append((depth, {"kind": "bullet", "target": parent, "base_depth": depth}))
            elif isinstance(parent, dict) and parent.get("kind") == "bullet":
                assert content.startswith(_CONTENT_PREFIXES), f"a test bullet isn't valid here: {content!r}"
                relative_depth = depth - parent["base_depth"]
                assert relative_depth > 0, f"a nested bullet must be indented: {content!r}"
                parent["target"].append(_bullet_text(content, relative_depth))
                stack.append((depth, parent))
            else:
                # kind stays undetermined until we know whether a header
                # child ever shows up (see below) - a bullet alone doesn't
                # prove this node is an entry, since a class can open with
                # a class-level bullet before its first named entry.
                assert isinstance(parent, dict) and parent["kind"] in (
                    None,
                    "entry",
                    "class",
                    "file",
                    "data",
                ), f"a bullet isn't valid here: {content!r}"
                if content.startswith("~ "):
                    assert parent["kind"] != "data", f"a test bullet isn't valid in data: {content!r}"
                    parent["tests"].append((content[2:], line_no))
                    stack.append((depth, None))
                else:
                    parent["bullets"].append(_content_for_storage(content))
                    stack.append(
                        (
                            depth,
                            {
                                "kind": "bullet",
                                "target": parent["bullets"],
                                "base_depth": depth,
                            },
                        )
                    )
            continue

        if content == "@policy:":
            assert isinstance(parent, dict) and parent["kind"] in ("folder", "file", "class"), (
                "@policy: is only valid at root, folder, or file/class scope"
            )
            stack.append((depth, parent["policy"]))
            continue

        assert content.endswith(":"), f"expected a header: {content!r}"
        name, summary, marker = _parse_header(content)
        assert isinstance(parent, dict), f"unexpected nesting under a bullet or policy item: {content!r}"

        if parent["kind"] is None:
            # first header child ever seen under this node - it's a class,
            # not an entry, regardless of any bullets already collected
            parent["kind"] = "class"

        if parent["kind"] == "folder":
            if marker is not None:
                raise ValueError(f"unexpected data marker outside a file or class: {content!r}")
            if "." in name:
                base, ext = name.rsplit(".", 1)
                node = _new_node(base, ext, summary, line=line_no)
                node["kind"] = "file"
            else:
                node = _new_node(name, summary=summary, line=line_no)
                node["kind"] = "folder"
            parent["children"][node["name"]] = node
            stack.append((depth, node))
        elif parent["kind"] in ("file", "class"):
            node = _new_node(name, summary=summary, line=line_no)
            if marker == "data":
                node["kind"] = "data"
            if pending_entry_point:
                node["entry_point"] = pending_entry_point_label or True
            pending_entry_point = False
            pending_entry_point_label = None
            parent["children"][name] = node
            stack.append((depth, node))
        else:
            raise ValueError(f"unexpected header {content!r} under kind {parent['kind']!r}")

    _finalize(root, "root")
    return root


# already covered by parse()'s own tracked region [llm-exempt]
def walk_files(node, folder_parts=()):
    """Yield (file_rel, ext) for every file node in the tree, whether or not
    it holds any source-handled entries - coverage checking needs every
    file llmlang knows about, not just the ones with entries already in it."""
    for name, child in node["children"].items():
        kind = child["kind"]
        if kind == "folder":
            yield from walk_files(child, folder_parts + (name,))
        elif kind == "file":
            yield "/".join(folder_parts + (f"{name}.{child['ext']}",)), child["ext"]


# already covered by parse()'s own tracked region [llm-exempt]
def walk_policies(node, path=()):
    """Yield (scope_path, index, text) for every policy item at any scope."""
    for i, text in enumerate(node["policy"]):
        yield path, i, text
    for name, child in node["children"].items():
        yield from walk_policies(child, path + (name,))


# already covered by parse()'s own tracked region [llm-exempt]
def _file_label(file_rel):
    return file_rel.rsplit(".", 1)[0].replace("/", ".")


# already covered by parse()'s own tracked region [llm-exempt]
def _entry_keys_beneath(node, file_rel, class_name):
    """All entry tracking keys nested anywhere beneath this node, direct or
    via further sub-classes - a class/file-level bullet can depend on any
    of them, not just its immediate children."""
    file_label = _file_label(file_rel)
    keys = []
    for name, child in node["children"].items():
        if child["kind"] in ("entry", "data"):
            local_key = f"{class_name}.{name}" if class_name else name
            keys.append(f"{file_label}.{local_key}")
        elif child["kind"] == "class":
            keys.extend(_entry_keys_beneath(child, file_rel, name))
    return keys


# already covered by parse()'s own tracked region [llm-exempt]
def walk_entries(node, folder_parts=(), file_rel=None, class_name=None):
    """Yield (file_rel, handle_key, tracking_key, bullets, line) for every
    source-handled entry - line is the entry header's own source line in the
    llmlang file."""
    for name, child in node["children"].items():
        kind = child["kind"]
        if kind == "folder":
            yield from walk_entries(child, folder_parts + (name,), None, None)
        elif kind == "file":
            rel = "/".join(folder_parts + (f"{name}.{child['ext']}",))
            yield from walk_entries(child, folder_parts, rel, None)
        elif kind == "class":
            yield from walk_entries(child, folder_parts, file_rel, name)
        elif kind in ("entry", "data"):
            local_key = f"{class_name}.{name}" if class_name else name
            tracking_key = f"{_file_label(file_rel)}.{local_key}"
            yield (
                file_rel,
                tracking_key,
                tracking_key,
                [f"+ {child['summary']}"] + child["bullets"] + [f"~ {t}" for t, _line in child["tests"]],
                child["line"],
            )


# already covered by parse()'s own tracked region [llm-exempt]
def walk_entry_points(node, folder_parts=(), file_rel=None, class_name=None):
    """Yield (tracking_key, label) for every entry marked @entry-point -
    label is a string when @entry-point(label) was given, True when the
    bare form was used (the entry's own summary stands in as the label)."""
    for name, child in node["children"].items():
        kind = child["kind"]
        if kind == "folder":
            yield from walk_entry_points(child, folder_parts + (name,), None, None)
        elif kind == "file":
            rel = "/".join(folder_parts + (f"{name}.{child['ext']}",))
            yield from walk_entry_points(child, folder_parts, rel, None)
        elif kind == "class":
            yield from walk_entry_points(child, folder_parts, file_rel, name)
        elif kind == "entry" and child["entry_point"] is not None:
            local_key = f"{class_name}.{name}" if class_name else name
            tracking_key = f"{_file_label(file_rel)}.{local_key}"
            yield tracking_key, child["entry_point"]


# already covered by parse()'s own tracked region [llm-exempt]
def walk_tests(node, folder_parts=(), file_rel=None, class_name=None):
    """Yield (canonical_node_name, test_text) for every test bullet."""
    for name, child in node["children"].items():
        kind = child["kind"]
        if kind == "folder":
            yield from walk_tests(child, folder_parts + (name,), None, None)
        elif kind == "file":
            rel = "/".join(folder_parts + (f"{name}.{child['ext']}",))
            canonical_name = _file_label(rel)
            for test, _line in child["tests"]:
                yield canonical_name, test
            yield from walk_tests(child, folder_parts, rel, None)
        elif kind == "class":
            canonical_name = f"{_file_label(file_rel)}.{name}"
            for test, _line in child["tests"]:
                yield canonical_name, test
            yield from walk_tests(child, folder_parts, file_rel, name)
        elif kind == "entry":
            local_key = f"{class_name}.{name}" if class_name else name
            canonical_name = f"{_file_label(file_rel)}.{local_key}"
            for test, _line in child["tests"]:
                yield canonical_name, test


# already covered by parse()'s own tracked region [llm-exempt]
def walk_test_lines(node, folder_parts=(), file_rel=None, class_name=None):
    """Yield (canonical_node_name, test_text, line) for every test bullet -
    same traversal as walk_tests, with the bullet's own source line exposed
    for location reporting."""
    for name, child in node["children"].items():
        kind = child["kind"]
        if kind == "folder":
            yield from walk_test_lines(child, folder_parts + (name,), None, None)
        elif kind == "file":
            rel = "/".join(folder_parts + (f"{name}.{child['ext']}",))
            canonical_name = _file_label(rel)
            for test, line in child["tests"]:
                yield canonical_name, test, line
            yield from walk_test_lines(child, folder_parts, rel, None)
        elif kind == "class":
            canonical_name = f"{_file_label(file_rel)}.{name}"
            for test, line in child["tests"]:
                yield canonical_name, test, line
            yield from walk_test_lines(child, folder_parts, file_rel, name)
        elif kind == "entry":
            local_key = f"{class_name}.{name}" if class_name else name
            canonical_name = f"{_file_label(file_rel)}.{local_key}"
            for test, line in child["tests"]:
                yield canonical_name, test, line


# already covered by parse()'s own tracked region [llm-exempt]
def walk_class_bullet_groups(node, folder_parts=(), file_rel=None, class_name=None):
    """Yield (tracking_key, sibling_entry_tracking_keys, bullets, line) for
    every bare bullet group sitting directly on a file or class node -
    guarantees spanning more than one entry, with no single entry's code to
    attach to. line is the owning file/class header's own source line."""
    for name, child in node["children"].items():
        kind = child["kind"]
        if kind == "folder":
            yield from walk_class_bullet_groups(child, folder_parts + (name,), None, None)
        elif kind == "file":
            rel = "/".join(folder_parts + (f"{name}.{child['ext']}",))
            if child["bullets"] or child["tests"]:
                yield (
                    _file_label(rel),
                    _entry_keys_beneath(child, rel, None),
                    child["bullets"] + [f"~ {t}" for t, _line in child["tests"]],
                    child["line"],
                )
            yield from walk_class_bullet_groups(child, folder_parts, rel, None)
        elif kind == "class":
            if child["bullets"] or child["tests"]:
                tracking_key = f"{_file_label(file_rel)}.{name}"
                yield (
                    tracking_key,
                    _entry_keys_beneath(child, file_rel, name),
                    child["bullets"] + [f"~ {t}" for t, _line in child["tests"]],
                    child["line"],
                )
            yield from walk_class_bullet_groups(child, folder_parts, file_rel, name)


# already covered by parse()'s own tracked region [llm-exempt]
def policy_in_scope(policy_scope: tuple, entry_file: str) -> bool:
    """A policy at scope ('a','b') covers an entry whose file lives under
    folder path a/b/... (root scope, empty tuple, covers everything)."""
    if not policy_scope:
        return True
    prefix = "/".join(policy_scope)
    return entry_file == prefix or entry_file.startswith(prefix + "/") or entry_file.startswith(prefix + ".")


# already covered by parse()'s own tracked region [llm-exempt]
def applicable_policy_text(root, file_rel: str) -> list:
    """Every policy's text currently covering the given file, in a stable
    order - used both to detect a policy-driven cascade and to fold policy
    state into a disposition's own staleness check, so it goes stale if
    either the entry's own text or an applicable policy changes."""
    return [text for scope, i, text in walk_policies(root) if policy_in_scope(scope, file_rel)]

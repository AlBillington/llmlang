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
    header whose own children are "- " bullets is a named entry - the
    thing that gets a handle and maps to one method/property. A file
    can contain entries directly (no class layer) for the non-OOP case
    of a flat module of functions.
  - A bare "- " bullet sitting directly under a file or class (not
    under any entry) is a class/file-level bullet - for guarantees
    that span more than one entry, since it has no single entry's code
    to attach to.
  - A named entry's bullets, in any number, all describe that one
    entry together - no one-bullet-per-entry limit. "should ..."
    phrased bullets are read by the compiler as tests to build; that's
    a pure prose convention, invisible to this parser.
"""
from pathlib import Path


def _new_node(name, ext=None):
    return {"kind": None, "name": name, "ext": ext, "policy": [], "bullets": [], "children": {}}


def _finalize(node, path_desc):
    if node["kind"] is None:
        if not node["bullets"]:
            raise ValueError(f"{path_desc} has no content (needs at least one bullet or nested entry)")
        node["kind"] = "entry"
    for name, child in node["children"].items():
        _finalize(child, f"{path_desc}.{name}")


# parses a tab-indented llmlang file into a tree of folders, files, classes, and named entries [llm:parse]
def parse(path):
    lines = [line for line in Path(path).read_text().splitlines() if line.strip()]
    root = _new_node("", None)
    root["kind"] = "folder"
    stack = [(-1, root)]

    for raw_line in lines:
        depth = len(raw_line) - len(raw_line.lstrip("\t"))
        content = raw_line.strip()

        while len(stack) > 1 and stack[-1][0] >= depth:
            stack.pop()

        _, parent = stack[-1]

        if content.startswith("- "):
            if isinstance(parent, list):
                parent.append(content[2:])
            else:
                # kind stays undetermined until we know whether a header
                # child ever shows up (see below) - a bullet alone doesn't
                # prove this node is an entry, since a class can open with
                # a class-level bullet before its first named entry.
                assert isinstance(parent, dict) and parent["kind"] in (None, "entry", "class", "file"), (
                    f"a bullet isn't valid here: {content!r}"
                )
                parent["bullets"].append(content[2:])
            stack.append((depth, None))
            continue

        if content == "@policy:":
            assert isinstance(parent, dict) and parent["kind"] in ("folder", "file", "class"), (
                "@policy: is only valid at root, folder, or file/class scope"
            )
            stack.append((depth, parent["policy"]))
            continue

        assert content.endswith(":"), f"expected a header: {content!r}"
        # the real name is always the first token; anything after it up to
        # the colon is an optional freetext hint for whoever's reading the
        # raw file (human or compiler) - not tracked, not enforced, not
        # even retained once the name's been pulled out of it
        name = content[:-1].split(None, 1)[0]
        assert isinstance(parent, dict), f"unexpected nesting under a bullet or policy item: {content!r}"

        if parent["kind"] is None:
            # first header child ever seen under this node - it's a class,
            # not an entry, regardless of any bullets already collected
            parent["kind"] = "class"

        if parent["kind"] == "folder":
            if "." in name:
                base, ext = name.rsplit(".", 1)
                node = _new_node(base, ext)
                node["kind"] = "file"
            else:
                node = _new_node(name)
                node["kind"] = "folder"
            parent["children"][node["name"]] = node
            stack.append((depth, node))
        elif parent["kind"] in ("file", "class"):
            node = _new_node(name)
            parent["children"][name] = node
            stack.append((depth, node))
        else:
            raise ValueError(f"unexpected header {content!r} under kind {parent['kind']!r}")

    _finalize(root, "root")
    return root


def walk_policies(node, path=()):
    """Yield (scope_path, index, text) for every policy item at any scope."""
    for i, text in enumerate(node["policy"]):
        yield path, i, text
    for name, child in node["children"].items():
        yield from walk_policies(child, path + (name,))


def _file_label(file_rel):
    return file_rel.rsplit(".", 1)[0].replace("/", ".")


def _entry_keys_beneath(node, file_rel, class_name):
    """All entry tracking keys nested anywhere beneath this node, direct or
    via further sub-classes - a class/file-level bullet can depend on any
    of them, not just its immediate children."""
    file_label = _file_label(file_rel)
    keys = []
    for name, child in node["children"].items():
        if child["kind"] == "entry":
            handle_key = f"{class_name}.{name}" if class_name else name
            keys.append(f"{file_label}.{handle_key}")
        elif child["kind"] == "class":
            keys.extend(_entry_keys_beneath(child, file_rel, name))
    return keys


def walk_entries(node, folder_parts=(), file_rel=None, class_name=None):
    """Yield (file_rel, handle_key, tracking_key, bullets) for every named entry."""
    for name, child in node["children"].items():
        kind = child["kind"]
        if kind == "folder":
            yield from walk_entries(child, folder_parts + (name,), None, None)
        elif kind == "file":
            rel = "/".join(folder_parts + (f"{name}.{child['ext']}",))
            yield from walk_entries(child, folder_parts, rel, None)
        elif kind == "class":
            yield from walk_entries(child, folder_parts, file_rel, name)
        elif kind == "entry":
            handle_key = f"{class_name}.{name}" if class_name else name
            tracking_key = f"{_file_label(file_rel)}.{handle_key}"
            yield file_rel, handle_key, tracking_key, child["bullets"]


def walk_class_bullet_groups(node, folder_parts=(), file_rel=None, class_name=None):
    """Yield (tracking_key, sibling_entry_tracking_keys, bullets) for every
    bare bullet group sitting directly on a file or class node - guarantees
    spanning more than one entry, with no single entry's code to attach to."""
    for name, child in node["children"].items():
        kind = child["kind"]
        if kind == "folder":
            yield from walk_class_bullet_groups(child, folder_parts + (name,), None, None)
        elif kind == "file":
            rel = "/".join(folder_parts + (f"{name}.{child['ext']}",))
            if child["bullets"]:
                yield _file_label(rel), _entry_keys_beneath(child, rel, None), child["bullets"]
            yield from walk_class_bullet_groups(child, folder_parts, rel, None)
        elif kind == "class":
            if child["bullets"]:
                tracking_key = f"{_file_label(file_rel)}.{name}"
                yield tracking_key, _entry_keys_beneath(child, file_rel, name), child["bullets"]
            yield from walk_class_bullet_groups(child, folder_parts, file_rel, name)


def policy_in_scope(policy_scope: tuple, entry_file: str) -> bool:
    """A policy at scope ('a','b') covers an entry whose file lives under
    folder path a/b/... (root scope, empty tuple, covers everything)."""
    if not policy_scope:
        return True
    prefix = "/".join(policy_scope)
    return entry_file == prefix or entry_file.startswith(prefix + "/") or entry_file.startswith(prefix + ".")


def applicable_policy_text(root, file_rel: str) -> list:
    """Every policy's text currently covering the given file, in a stable
    order - used both to detect a policy-driven cascade and to fold policy
    state into a disposition's own staleness check, so it goes stale if
    either the entry's own text or an applicable policy changes."""
    return [text for scope, i, text in walk_policies(root) if policy_in_scope(scope, file_rel)]

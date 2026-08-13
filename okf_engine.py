"""
OKF (Open Knowledge Format v0.2) Engine for MCP-Memory.
Serializes, parses, and validates memory records according to OKF v0.2 spec.
"""

from datetime import datetime, timezone
import json
import os
from typing import Any, Dict, List, Optional, Union
import yaml


def _get_utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def serialize_okf(
    key: str,
    content: Union[str, Dict[str, Any]],
    tags: Optional[List[str]] = None,
    namespace: str = "default",
    concept_type: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    resource: Optional[str] = None,
    status: Optional[str] = None,
    stale_after: Optional[str] = None,
    sources: Optional[List[Dict[str, Any]]] = None,
    usage_window: Optional[Dict[str, str]] = None,
    verified: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
    generated_by: Optional[str] = None,
    created_at: Optional[str] = None,
    updated_at: Optional[str] = None,
    runtime: Optional[str] = None,
    parameters: Optional[List[Dict[str, Any]]] = None,
    executor: Optional[Dict[str, Any]] = None,
    attester: Optional[Dict[str, Any]] = None,
    computation: Optional[str] = None,
    extra_frontmatter: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Serialize a memory item into an OKF v0.2 formatted Markdown document with YAML frontmatter.
    Conforms to OKF v0.2 specification (§4, §5, §7, §10, §11).
    """
    now = _get_utc_now_iso()
    c_at = created_at or now
    u_at = updated_at or now
    t_list = tags if tags is not None else []

    derived_title = title or (key.split("/")[-1].replace("_", " ").title() if key else "Memory Record")

    frontmatter: Dict[str, Any] = {
        "type": concept_type or "Agent Memory",
        "title": derived_title,
        "key": key,
        "namespace": namespace,
    }

    if description:
        frontmatter["description"] = description
    if resource:
        frontmatter["resource"] = resource

    frontmatter["tags"] = t_list

    valid_statuses = ("draft", "stable", "deprecated")
    if status and status in valid_statuses:
        frontmatter["status"] = status
    else:
        frontmatter["status"] = "stable"

    if stale_after:
        frontmatter["stale_after"] = stale_after

    gen_actor = generated_by or "mcp-memory/0.2.0"
    frontmatter["generated"] = {
        "by": gen_actor,
        "at": u_at,
    }

    if verified is not None:
        frontmatter["verified"] = verified

    if sources is not None:
        frontmatter["sources"] = sources

    if usage_window is not None:
        frontmatter["usage_window"] = usage_window

    # Attested Computation contract fields (§10)
    if runtime:
        frontmatter["runtime"] = runtime
    if parameters is not None:
        frontmatter["parameters"] = parameters
    if executor is not None:
        frontmatter["executor"] = executor
    if attester is not None:
        frontmatter["attester"] = attester
    if computation:
        frontmatter["computation"] = computation

    if extra_frontmatter:
        for k, v in extra_frontmatter.items():
            if k not in frontmatter:
                frontmatter[k] = v

    frontmatter["created_at"] = c_at
    frontmatter["updated_at"] = u_at

    body_text = ""
    if isinstance(content, str):
        body_text = content.strip()
    elif isinstance(content, dict):
        frontmatter["content_type"] = "json"
        body_lines = ["# Memory Content\n"]
        for k, v in content.items():
            body_lines.append(f"- **{k}**: `{json.dumps(v)}`" if isinstance(v, (dict, list)) else f"- **{k}**: {v}")
        body_lines.append("\n```json")
        body_lines.append(json.dumps(content, indent=2))
        body_lines.append("```")
        body_text = "\n".join(body_lines)
    else:
        body_text = str(content).strip()

    yaml_dump = yaml.dump(frontmatter, sort_keys=False, allow_unicode=True).strip()

    return f"---\n{yaml_dump}\n---\n\n{body_text}\n"


def parse_okf(raw_payload: str) -> Dict[str, Any]:
    """
    Parse an OKF v0.2 formatted Markdown document into a Python dict.
    Returns dictionary with key, namespace, tags, frontmatter, and body content.
    """
    if not raw_payload:
        raise ValueError("Empty OKF payload.")

    lines = raw_payload.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("Invalid OKF document: missing starting YAML frontmatter delimiter '---'")

    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx == -1:
        raise ValueError("Invalid OKF document: missing closing YAML frontmatter delimiter '---'")

    yaml_str = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1:]).strip()

    try:
        frontmatter = yaml.safe_load(yaml_str) or {}
    except Exception as e:
        raise ValueError(f"Failed to parse YAML frontmatter: {e}")

    key = frontmatter.get("key", "")
    namespace = frontmatter.get("namespace", "default")
    tags = frontmatter.get("tags", [])

    return {
        "key": key,
        "namespace": namespace,
        "tags": tags,
        "frontmatter": frontmatter,
        "body": body,
        "raw_payload": raw_payload,
    }


def validate_okf_conformance(raw_payload: str) -> Dict[str, Any]:
    """
    Validate that an OKF payload strictly conforms to OKF v0.2 spec rules (§11).
    Returns dict: {"valid": bool, "errors": List[str], "frontmatter": Dict[str, Any]}
    """
    errors: List[str] = []
    if not raw_payload or not raw_payload.strip():
        return {"valid": False, "errors": ["Empty payload"], "frontmatter": {}}

    lines = raw_payload.splitlines()
    if not lines or lines[0].strip() != "---":
        errors.append("Document missing starting YAML frontmatter delimiter '---'")
        return {"valid": False, "errors": errors, "frontmatter": {}}

    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx == -1:
        errors.append("Document missing closing YAML frontmatter delimiter '---'")
        return {"valid": False, "errors": errors, "frontmatter": {}}

    yaml_str = "\n".join(lines[1:end_idx])
    try:
        frontmatter = yaml.safe_load(yaml_str) or {}
    except Exception as e:
        errors.append(f"Invalid YAML frontmatter: {e}")
        return {"valid": False, "errors": errors, "frontmatter": {}}

    if not isinstance(frontmatter, dict):
        errors.append("YAML frontmatter must be a dictionary")
        return {"valid": False, "errors": errors, "frontmatter": {}}

    # Requirement 1 (§11): non-empty type
    c_type = frontmatter.get("type")
    if not c_type or not str(c_type).strip():
        errors.append("Required field 'type' is missing or empty (§11)")

    # Status check (§5.4)
    if "status" in frontmatter:
        val_status = frontmatter["status"]
        if val_status not in ("draft", "stable", "deprecated"):
            errors.append(f"Invalid status '{val_status}'. Expected 'draft', 'stable', or 'deprecated' (§5.4)")

    # Actor convention check (§7)
    if "generated" in frontmatter and isinstance(frontmatter["generated"], dict):
        actor = frontmatter["generated"].get("by", "")
        if actor and not (actor.startswith("human:") or actor.startswith("process:") or "/" in actor):
            errors.append(f"Actor '{actor}' in generated.by does not follow actor convention (<producer>/<version>, human:<id>, process:<id>) (§7)")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "frontmatter": frontmatter,
    }


def get_memory_file_path(key: str, namespace: str = "default", base_dir: str = "memory") -> str:
    """Determine physical file path for a given memory key and namespace."""
    clean_key = key.lstrip("/").rstrip("/")
    if not clean_key.endswith(".md"):
        clean_key += ".md"

    if namespace and namespace != "default":
        return os.path.join(base_dir, namespace, clean_key)
    return os.path.join(base_dir, clean_key)


def update_directory_index(dir_path: str, is_bundle_root: bool = False) -> None:
    """Generate or update index.md for progressive disclosure in OKF bundle directory."""
    if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
        return

    entries = sorted(os.listdir(dir_path))
    concept_files = []
    subdirs = []

    for item in entries:
        if item.startswith(".") or item in ("index.md", "log.md"):
            continue
        full_p = os.path.join(dir_path, item)
        if os.path.isdir(full_p):
            subdirs.append(item)
        elif item.endswith(".md"):
            concept_files.append(item)

    if not concept_files and not subdirs:
        index_file = os.path.join(dir_path, "index.md")
        if os.path.exists(index_file):
            try:
                os.remove(index_file)
            except OSError:
                pass
        return

    dir_name = os.path.basename(os.path.normpath(dir_path)).replace("_", " ").title()
    lines = []

    if is_bundle_root:
        lines.append("---\nokf_version: \"0.2\"\n---")

    lines.append(f"# {dir_name}\n")

    if subdirs:
        lines.append("## Directories\n")
        for sd in subdirs:
            lines.append(f"* [{sd}/]({sd}/)")
        lines.append("")

    if concept_files:
        lines.append("## Concepts\n")
        for cf in concept_files:
            title = cf[:-3].replace("_", " ").title()
            lines.append(f"* [{title}]({cf})")
        lines.append("")

    index_content = "\n".join(lines).strip() + "\n"
    index_file = os.path.join(dir_path, "index.md")
    with open(index_file, "w", encoding="utf-8") as f:
        f.write(index_content)


def append_log_entry(base_dir: str, action: str, key: str, details: Optional[str] = None) -> None:
    """
    Append or update a log entry in log.md at the bundle root according to OKF v0.2 §9.
    Log entries are grouped under ISO 8601 date headings (## YYYY-MM-DD), newest first.
    """
    if not os.path.exists(base_dir):
        os.makedirs(base_dir, exist_ok=True)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = os.path.join(base_dir, "log.md")

    title = key.split("/")[-1].replace("_", " ").title() if key else key
    concept_rel_path = f"/{key.lstrip('/')}.md" if not key.endswith(".md") else f"/{key.lstrip('/')}"
    log_bullet = f"* **{action}**: {title} ([{key}]({concept_rel_path}))"
    if details:
        log_bullet += f" - {details}"

    if not os.path.exists(log_file):
        content = f"# Directory Update Log\n\n## {today}\n{log_bullet}\n"
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(content)
        return

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            existing = f.read()
    except Exception:
        existing = ""

    date_heading = f"## {today}"
    if date_heading in existing:
        lines = existing.splitlines()
        new_lines = []
        inserted = False
        for line in lines:
            new_lines.append(line)
            if not inserted and line.strip() == date_heading:
                new_lines.append(log_bullet)
                inserted = True
        updated_content = "\n".join(new_lines) + "\n"
    else:
        if existing.startswith("# "):
            header_end = existing.find("\n\n")
            if header_end != -1:
                header = existing[:header_end]
                rest = existing[header_end:]
                updated_content = f"{header}\n\n## {today}\n{log_bullet}{rest}"
            else:
                updated_content = f"# Directory Update Log\n\n## {today}\n{log_bullet}\n\n{existing}"
        else:
            updated_content = f"# Directory Update Log\n\n## {today}\n{log_bullet}\n\n{existing}"

    with open(log_file, "w", encoding="utf-8") as f:
        f.write(updated_content)


def sync_memory_to_disk(key: str, namespace: str, okf_payload: str, base_dir: str = "memory") -> str:
    """Write raw OKF document to disk as .md file, update index.md, and update log.md."""
    file_path = get_memory_file_path(key=key, namespace=namespace, base_dir=base_dir)
    parent_dir = os.path.dirname(file_path)
    os.makedirs(parent_dir, exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(okf_payload)

    # Update index.md up the directory tree
    curr = parent_dir
    base_abs = os.path.abspath(base_dir)
    while True:
        is_root = (os.path.abspath(curr) == base_abs)
        update_directory_index(curr, is_bundle_root=is_root)
        if is_root or (curr == parent_dir and curr == base_dir):
            break
        parent_of_curr = os.path.dirname(curr)
        if parent_of_curr == curr or not parent_of_curr.startswith(base_abs):
            break
        curr = parent_of_curr

    # Append to bundle update log (§9)
    append_log_entry(base_dir=base_dir, action="Update", key=key)

    return file_path


def remove_memory_from_disk(key: str, namespace: str, base_dir: str = "memory") -> bool:
    """Remove OKF .md file from disk, update parent indexes, and log deletion."""
    file_path = get_memory_file_path(key=key, namespace=namespace, base_dir=base_dir)
    if not os.path.exists(file_path):
        return False

    try:
        os.remove(file_path)
    except OSError:
        return False

    parent_dir = os.path.dirname(file_path)
    curr = parent_dir
    base_abs = os.path.abspath(base_dir)

    while True:
        is_root = (os.path.abspath(curr) == base_abs)
        update_directory_index(curr, is_bundle_root=is_root)
        # Remove empty directories if no concept files or subdirs remain
        if os.path.exists(curr) and curr != base_abs:
            remaining = [i for i in os.listdir(curr) if i not in ("index.md", "log.md") and not i.startswith(".")]
            if not remaining:
                try:
                    index_file = os.path.join(curr, "index.md")
                    if os.path.exists(index_file):
                        os.remove(index_file)
                    os.rmdir(curr)
                except OSError:
                    pass

        if os.path.abspath(curr) == base_abs:
            break
        parent_of_curr = os.path.dirname(curr)
        if parent_of_curr == curr or not parent_of_curr.startswith(base_abs):
            break
        curr = parent_of_curr

    # Append deletion to bundle update log (§9)
    append_log_entry(base_dir=base_dir, action="Deletion", key=key)

    return True

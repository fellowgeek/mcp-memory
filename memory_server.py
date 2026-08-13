"""
MCP-Memory Server Entrypoint.
Exposes MCP tools for persistent agent memory backed by OKF v0.2 and SQLite.
Includes 'Last Memory' checkpoint protocol for cross-session continuity.
"""

import warnings
warnings.filterwarnings("ignore")

from typing import Any, Dict, List, Optional, Union
from mcp.server.fastmcp import FastMCP
from db import delete_memory, init_db, retrieve_memory, search_memories, store_memory

SERVER_INSTRUCTIONS = """
MCP-Memory Agent Continuity Protocol:
1. ON SESSION INITIALIZATION: Whenever you start working on a project or open a session, your VERY FIRST ACTION should be to call `memory_get_last` (or retrieve key 'system/last_memory') to inspect where work was last left off.
2. ON MILESTONE / PROGRESS UPDATE: Whenever you accomplish a milestone, make key structural changes, or pause work, ALWAYS update the last memory checkpoint by calling `memory_update_last` (or storing key 'system/last_memory') with a brief summary and references to relevant memory concepts.
"""

mcp = FastMCP("MCP-Memory", instructions=SERVER_INSTRUCTIONS)

# Initialize database on startup
init_db()


@mcp.tool()
def memory_get_last(
    project_root: str,
    namespace: str = "default",
) -> str:
    """
    AGENT DIRECTIVE - SESSION INITIALIZATION:
    Call this tool FIRST when starting work or opening a project session to retrieve the last recorded session checkpoint ('system/last_memory') and understand where work was left off.

    Parameters:
        project_root: REQUIRED. Absolute path to active project root directory.
        namespace: Logical namespace (default: 'default').
    """
    if not project_root or not project_root.strip():
        return "Error: 'project_root' is required. Please provide the absolute path to your active project root directory."

    try:
        record = retrieve_memory(key="system/last_memory", namespace=namespace, project_root=project_root)
        if not record:
            return (
                "No previous 'system/last_memory' checkpoint found for this project.\n"
                "Agent Directive: Start fresh, and remember to update 'system/last_memory' via `memory_update_last` when accomplishing milestones."
            )
        return (
            "=== LAST SESSION CHECKPOINT (system/last_memory) ===\n\n"
            f"{record['raw_payload']}"
        )
    except Exception as e:
        return f"Error retrieving last memory checkpoint: {str(e)}"


@mcp.tool()
def memory_update_last(
    content: Union[str, Dict[str, Any]],
    project_root: str,
    namespace: str = "default",
    summary: Optional[str] = None,
) -> str:
    """
    AGENT DIRECTIVE - MILESTONE & SESSION CHECKPOINTING:
    Call this tool whenever completing a milestone, making key project changes, or pausing work to update the canonical project checkpoint ('system/last_memory') so future sessions know where work was left off.

    Parameters:
        content: Brief note or structured dictionary summarizing progress and referencing key memory files (e.g. '[Goal Progress](/agent/goal.md)').
        project_root: REQUIRED. Absolute path to active project root directory.
        namespace: Logical namespace (default: 'default').
        summary: Optional one-sentence description of the milestone achieved.
    """
    if not project_root or not project_root.strip():
        return "Error: 'project_root' is required. Please provide the absolute path to your active project root directory."

    try:
        record = store_memory(
            key="system/last_memory",
            content=content,
            tags=["last_memory", "checkpoint", "milestone"],
            namespace=namespace,
            concept_type="Checkpoint",
            title="Last Session Checkpoint",
            description=summary or "Last recorded progress checkpoint and active project state.",
            status="stable",
            project_root=project_root,
        )
        return (
            "Successfully updated last memory checkpoint ('system/last_memory').\n"
            f"File synced to: {record.get('file_path')}\n\n"
            f"OKF Record Payload:\n{record['okf_payload']}"
        )
    except Exception as e:
        return f"Error updating last memory checkpoint: {str(e)}"


@mcp.tool()
def memory_store(
    key: str,
    content: Union[str, Dict[str, Any]],
    project_root: str,
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
    runtime: Optional[str] = None,
    parameters: Optional[List[Dict[str, Any]]] = None,
    executor: Optional[Dict[str, Any]] = None,
    attester: Optional[Dict[str, Any]] = None,
    computation: Optional[str] = None,
) -> str:
    """
    Stores or updates a persistent memory record in Open Knowledge Format (OKF v0.2).

    Parameters:
        key: Unique identifier or path for the memory (e.g. 'user/preferences/coding_style' or 'system/last_memory').
        content: The core information to store (string text or structured dictionary).
        project_root: REQUIRED. Absolute path to active project root directory.
        tags: Optional classification tags for filtering (e.g. ['preferences', 'user']).
        namespace: Logical separation for contexts or users (default: 'default').
        concept_type: OKF concept type (default: 'Agent Memory'). Options: 'Agent Memory', 'Checkpoint', 'Metric', 'Playbook', etc.
        title: Human-readable display name.
        description: Single-sentence summary of the concept.
        resource: Canonical URI for the underlying asset.
        status: Lifecycle status ('draft' | 'stable' | 'deprecated'). Default: 'stable'.
        stale_after: ISO date ('YYYY-MM-DD') when memory becomes stale.
        sources: Provenance sources list [{resource, id, title, author, usage_count, last_modified}].
        usage_window: Sources usage window framing {from, to}.
        verified: Verification events list or mapping [{by, at}].
        generated_by: Actor identifier string following actor convention ('<producer>/<version>', 'human:<id>', 'process:<id>').
        runtime: For Attested Computation concepts ('bigquery', 'postgres', 'dbt', 'python').
        parameters: For Attested Computation concepts [{name, type, required}].
        executor: For Attested Computation concepts {resource, receipt}.
        attester: For Attested Computation concepts {resource}.
        computation: Path to external computation file.
    """
    if not project_root or not project_root.strip():
        return "Error: 'project_root' is required. Please provide the absolute path to your active project root directory."

    try:
        record = store_memory(
            key=key,
            content=content,
            tags=tags,
            namespace=namespace,
            concept_type=concept_type,
            title=title,
            description=description,
            resource=resource,
            status=status,
            stale_after=stale_after,
            sources=sources,
            usage_window=usage_window,
            verified=verified,
            generated_by=generated_by,
            runtime=runtime,
            parameters=parameters,
            executor=executor,
            attester=attester,
            computation=computation,
            project_root=project_root,
        )
        return (
            f"Successfully stored memory for key '{key}' in namespace '{namespace}'.\n"
            f"File synced to: {record.get('file_path')}\n\n"
            f"OKF Record Payload:\n{record['okf_payload']}"
        )
    except Exception as e:
        return f"Error storing memory: {str(e)}"


@mcp.tool()
def memory_retrieve(
    key: str,
    project_root: str,
    namespace: str = "default",
) -> str:
    """
    Retrieves a specific memory record by key.

    Parameters:
        key: The exact memory key to look up (e.g. 'system/last_memory' for session checkpoint).
        project_root: REQUIRED. Absolute path to active project root directory.
        namespace: Logical namespace (default: 'default').
    """
    if not project_root or not project_root.strip():
        return "Error: 'project_root' is required. Please provide the absolute path to your active project root directory."

    try:
        record = retrieve_memory(key=key, namespace=namespace, project_root=project_root)
        if not record:
            return f"Memory record with key '{key}' not found in namespace '{namespace}'."
        return record["raw_payload"]
    except Exception as e:
        return f"Error retrieving memory: {str(e)}"


@mcp.tool()
def memory_search(
    project_root: str,
    query: Optional[str] = None,
    tags: Optional[List[str]] = None,
    namespace: Optional[str] = None,
    limit: int = 10,
) -> str:
    """
    Searches persistent memories matching keywords, tags, or namespace patterns.

    Parameters:
        project_root: REQUIRED. Absolute path to active project root directory.
        query: Search string for full-text search across keys, frontmatter, and content.
        tags: Optional list of tags to filter by.
        namespace: Optional namespace filter.
        limit: Maximum number of results to return (default: 10).
    """
    if not project_root or not project_root.strip():
        return "Error: 'project_root' is required. Please provide the absolute path to your active project root directory."

    try:
        results = search_memories(query=query, tags=tags, namespace=namespace, limit=limit, project_root=project_root)
        if not results:
            return "No matching memories found."

        summary_lines = [f"Found {len(results)} memory record(s):\n"]
        for idx, res in enumerate(results, 1):
            tags_str = ", ".join(res["tags"]) if res["tags"] else "none"
            summary_lines.append(
                f"### {idx}. [{res['key']}] (Namespace: {res['namespace']})\n"
                f"- **Tags**: {tags_str}\n"
                f"- **Updated**: {res['updated_at']}\n"
                f"```markdown\n{res['okf_payload']}\n```\n"
            )
        return "\n".join(summary_lines)
    except Exception as e:
        return f"Error searching memories: {str(e)}"


@mcp.tool()
def memory_delete(
    key: str,
    project_root: str,
    namespace: str = "default",
) -> str:
    """
    Removes a specific memory entry.

    Parameters:
        key: The key of the memory to remove.
        project_root: REQUIRED. Absolute path to active project root directory.
        namespace: Logical namespace (default: 'default').
    """
    if not project_root or not project_root.strip():
        return "Error: 'project_root' is required. Please provide the absolute path to your active project root directory."

    try:
        deleted = delete_memory(key=key, namespace=namespace, project_root=project_root)
        if deleted:
            return f"Successfully deleted memory key '{key}' from namespace '{namespace}'."
        else:
            return f"Memory key '{key}' not found in namespace '{namespace}'."
    except Exception as e:
        return f"Error deleting memory: {str(e)}"


if __name__ == "__main__":
    mcp.run()

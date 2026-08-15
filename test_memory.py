"""
Unit tests for MCP-Memory server.
Tests OKF v0.2 spec rules, parsing/serialization, validation, SQLite storage & FTS search, and MCP tools including Last Memory checkpoints.
"""

import os
import tempfile
import unittest

from okf_engine import serialize_okf, parse_okf, validate_okf_conformance, get_memory_file_path
import db
from memory_server import memory_store, memory_retrieve, memory_search, memory_delete, memory_get_last, memory_update_last


class TestOKFEngine(unittest.TestCase):
    def test_memory_path_rejects_parent_traversal(self):
        """Path traversal: a key with ../ must not escape base_dir (CVE-style)."""
        with tempfile.TemporaryDirectory() as tmp:
            base = os.path.join(tmp, "memory")
            path = get_memory_file_path("../../etc/passwd", base_dir=base)
            resolved = os.path.realpath(path)
            # resolved path must stay inside base_dir
            self.assertTrue(resolved.startswith(os.path.realpath(base) + os.sep),
                            f"escaped base_dir: {resolved}")
            self.assertNotIn("..", resolved)

    def test_memory_path_rejects_absolute_key(self):
        """An absolute key must not write outside base_dir."""
        with tempfile.TemporaryDirectory() as tmp:
            base = os.path.join(tmp, "memory")
            path = get_memory_file_path("/tmp/evil.md", base_dir=base)
            resolved = os.path.realpath(path)
            self.assertTrue(resolved.startswith(os.path.realpath(base) + os.sep))

    def test_memory_path_normal_key_still_works(self):
        """Normal keys keep working: namespaced paths inside base_dir."""
        with tempfile.TemporaryDirectory() as tmp:
            base = os.path.join(tmp, "memory")
            path = get_memory_file_path("user/preferences/theme", namespace="user_settings", base_dir=base)
            resolved = os.path.realpath(path)
            self.assertTrue(resolved.startswith(os.path.realpath(base) + os.sep))
            self.assertTrue(resolved.endswith(".md"))
            self.assertIn("user_settings", resolved)

    def test_serialize_and_parse_string_content(self):
        key = "user/preferences/theme"
        content = "User prefers dark mode with high contrast."
        tags = ["ui", "preferences"]
        namespace = "user_settings"

        okf_payload = serialize_okf(key=key, content=content, tags=tags, namespace=namespace)

        self.assertIn("type: Agent Memory", okf_payload)
        self.assertIn("key: user/preferences/theme", okf_payload)
        self.assertIn("namespace: user_settings", okf_payload)
        self.assertIn("User prefers dark mode with high contrast.", okf_payload)

        parsed = parse_okf(okf_payload)
        self.assertEqual(parsed["key"], key)
        self.assertEqual(parsed["namespace"], namespace)
        self.assertEqual(parsed["tags"], tags)
        self.assertEqual(parsed["body"], content)

    def test_serialize_and_parse_dict_content(self):
        key = "project/architecture"
        content = {"framework": "FastMCP", "db": "SQLite", "okf_version": "0.2"}
        tags = ["architecture", "tech_stack"]

        okf_payload = serialize_okf(key=key, content=content, tags=tags)
        parsed = parse_okf(okf_payload)

        self.assertEqual(parsed["key"], key)
        self.assertEqual(parsed["tags"], tags)
        self.assertIn("```json", parsed["body"])
        self.assertIn('"framework": "FastMCP"', parsed["body"])

    def test_okf_v02_extended_serialization(self):
        key = "metrics/revenue"
        content = "Recognized revenue for fiscal year."
        sources = [
            {"id": "rev-policy", "resource": "https://wiki.acme/rev", "title": "Revenue Policy"}
        ]
        verified = [{"by": "human:ahormati", "at": "2026-08-12T19:00:00Z"}]
        
        okf_payload = serialize_okf(
            key=key,
            content=content,
            concept_type="Metric",
            title="Revenue Fiscal Year",
            description="Recognized annual revenue.",
            status="stable",
            stale_after="2026-12-31",
            sources=sources,
            verified=verified,
            generated_by="agent/gemini-3.6",
        )

        validation = validate_okf_conformance(okf_payload)
        self.assertTrue(validation["valid"], f"Validation failed: {validation['errors']}")

        parsed = parse_okf(okf_payload)
        fm = parsed["frontmatter"]
        self.assertEqual(fm["type"], "Metric")
        self.assertEqual(fm["title"], "Revenue Fiscal Year")
        self.assertEqual(fm["description"], "Recognized annual revenue.")
        self.assertEqual(fm["status"], "stable")
        self.assertEqual(fm["stale_after"], "2026-12-31")
        self.assertEqual(fm["generated"]["by"], "agent/gemini-3.6")
        self.assertEqual(fm["sources"][0]["id"], "rev-policy")
        self.assertEqual(fm["verified"][0]["by"], "human:ahormati")

    def test_okf_conformance_validation(self):
        # Valid document
        valid_doc = serialize_okf(key="test/doc", content="Valid content")
        res_valid = validate_okf_conformance(valid_doc)
        self.assertTrue(res_valid["valid"])

        # Invalid document (missing type)
        invalid_yaml = "---\ntitle: Missing Type\nkey: test/doc\n---\nBody text"
        res_invalid = validate_okf_conformance(invalid_yaml)
        self.assertFalse(res_invalid["valid"])
        self.assertIn("Required field 'type' is missing or empty (§11)", res_invalid["errors"][0])

        # Invalid actor format
        invalid_actor_doc = "---\ntype: Agent Memory\ngenerated: { by: invalidactor, at: 2026-08-12T19:00:00Z }\n---\nContent"
        res_actor = validate_okf_conformance(invalid_actor_doc)
        self.assertFalse(res_actor["valid"])
        self.assertIn("actor convention", res_actor["errors"][0])


class TestDatabaseLayer(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        self.temp_memories_dir = tempfile.mkdtemp()
        db.DEFAULT_DB_PATH = self.temp_db_path
        db.DEFAULT_MEMORIES_DIR = self.temp_memories_dir
        db.init_db(self.temp_db_path)

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)
        import shutil
        shutil.rmtree(self.temp_memories_dir, ignore_errors=True)

    def test_store_and_retrieve(self):
        key = "test/key1"
        content = "Memory test content"
        tags = ["test", "demo"]
        namespace = "test_ns"

        rec = db.store_memory(key=key, content=content, tags=tags, namespace=namespace, db_path=self.temp_db_path, memories_dir=self.temp_memories_dir)
        self.assertEqual(rec["key"], key)
        self.assertEqual(rec["namespace"], namespace)

        retrieved = db.retrieve_memory(key=key, namespace=namespace, db_path=self.temp_db_path)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["key"], key)
        self.assertEqual(retrieved["namespace"], namespace)
        self.assertEqual(retrieved["tags"], tags)
        self.assertEqual(retrieved["body"], content)

    def test_file_dumping_and_indexes_and_log(self):
        temp_dir = tempfile.mkdtemp()
        try:
            key = "user/preferences/theme"
            content = "User prefers dark mode"
            tags = ["ui"]
            
            rec = db.store_memory(key=key, content=content, tags=tags, db_path=self.temp_db_path, memories_dir=temp_dir)
            expected_file = os.path.join(temp_dir, "user", "preferences", "theme.md")
            expected_index = os.path.join(temp_dir, "user", "preferences", "index.md")
            root_index = os.path.join(temp_dir, "index.md")
            root_log = os.path.join(temp_dir, "log.md")

            self.assertTrue(os.path.exists(expected_file))
            self.assertTrue(os.path.exists(expected_index))
            self.assertTrue(os.path.exists(root_index))
            self.assertTrue(os.path.exists(root_log))

            # Verify bundle root index.md contains okf_version: "0.2" (§12)
            with open(root_index, "r", encoding="utf-8") as f:
                root_index_content = f.read()
                self.assertIn('okf_version: "0.2"', root_index_content)

            # Verify subdirectory index.md does NOT contain frontmatter (§8)
            with open(expected_index, "r", encoding="utf-8") as f:
                sub_index_content = f.read()
                self.assertNotIn("okf_version", sub_index_content)

            # Verify log.md contains entry (§9)
            with open(root_log, "r", encoding="utf-8") as f:
                log_content = f.read()
                self.assertIn("# Directory Update Log", log_content)
                self.assertIn("**Update**", log_content)

            # Test deletion removes file and logs deletion
            deleted = db.delete_memory(key=key, db_path=self.temp_db_path, memories_dir=temp_dir)
            self.assertTrue(deleted)
            self.assertFalse(os.path.exists(expected_file))

            with open(root_log, "r", encoding="utf-8") as f:
                updated_log_content = f.read()
                self.assertIn("**Deletion**", updated_log_content)
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_search_fts_and_tags(self):
        db.store_memory("key/alpha", "Python programming language", tags=["code", "python"], db_path=self.temp_db_path, memories_dir=self.temp_memories_dir)
        db.store_memory("key/beta", "JavaScript node framework", tags=["code", "js"], db_path=self.temp_db_path, memories_dir=self.temp_memories_dir)
        db.store_memory("key/gamma", "SQLite database indexing", tags=["db", "sql"], db_path=self.temp_db_path, memories_dir=self.temp_memories_dir)

        py_results = db.search_memories(query="Python", db_path=self.temp_db_path)
        self.assertEqual(len(py_results), 1)
        self.assertEqual(py_results[0]["key"], "key/alpha")

        db_results = db.search_memories(tags=["db"], db_path=self.temp_db_path)
        self.assertEqual(len(db_results), 1)
        self.assertEqual(db_results[0]["key"], "key/gamma")

    def test_delete_memory(self):
        key = "delete/me"
        db.store_memory(key=key, content="Temporary content", db_path=self.temp_db_path, memories_dir=self.temp_memories_dir)
        
        retrieved = db.retrieve_memory(key=key, db_path=self.temp_db_path)
        self.assertIsNotNone(retrieved)

        deleted = db.delete_memory(key=key, db_path=self.temp_db_path, memories_dir=self.temp_memories_dir)
        self.assertTrue(deleted)

        retrieved_after = db.retrieve_memory(key=key, db_path=self.temp_db_path)
        self.assertIsNone(retrieved_after)


class TestMCPTools(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        self.temp_memories_dir = tempfile.mkdtemp()
        db.DEFAULT_DB_PATH = self.temp_db_path
        db.DEFAULT_MEMORIES_DIR = self.temp_memories_dir
        db.init_db(self.temp_db_path)

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)
        import shutil
        shutil.rmtree(self.temp_memories_dir, ignore_errors=True)

    def test_mcp_tools_flow(self):
        project_root = tempfile.mkdtemp()
        try:
            # 1. memory_store with OKF v0.2 parameters
            res_store = memory_store(
                key="agent/goal",
                content="Build MCP Memory Server",
                tags=["goal", "mcp"],
                concept_type="Playbook",
                description="Goal for constructing MCP server",
                status="stable",
                stale_after="2026-12-31",
                project_root=project_root,
            )
            self.assertIn("Successfully stored memory", res_store)
            self.assertIn("type: Playbook", res_store)
            self.assertIn("status: stable", res_store)
            self.assertIn("stale_after: '2026-12-31'", res_store)

            # 2. memory_retrieve
            res_retrieve = memory_retrieve(key="agent/goal", project_root=project_root)
            self.assertIn("type: Playbook", res_retrieve)
            self.assertIn("Build MCP Memory Server", res_retrieve)

            # 3. memory_search
            res_search = memory_search(query="Server", tags=["mcp"], project_root=project_root)
            self.assertIn("Found 1 memory record(s)", res_search)
            self.assertIn("agent/goal", res_search)

            # 4. memory_delete
            res_delete = memory_delete(key="agent/goal", project_root=project_root)
            self.assertIn("Successfully deleted memory key 'agent/goal'", res_delete)

            # Confirm deleted
            res_retrieve_after = memory_retrieve(key="agent/goal", project_root=project_root)
            self.assertIn("not found", res_retrieve_after)
        finally:
            import shutil
            shutil.rmtree(project_root, ignore_errors=True)

    def test_last_memory_tools_flow(self):
        project_root = tempfile.mkdtemp()
        try:
            # 1. memory_get_last before checkpoint exists
            res_initial = memory_get_last(project_root=project_root)
            self.assertIn("No previous 'system/last_memory' checkpoint found", res_initial)

            # 2. memory_update_last
            res_update = memory_update_last(
                content="Completed feature work. Active goal in [Agent Goal](/agent/goal.md).",
                summary="Feature X complete",
                project_root=project_root,
            )
            self.assertIn("Successfully updated last memory checkpoint", res_update)

            # 3. memory_get_last after checkpoint updated
            res_get = memory_get_last(project_root=project_root)
            self.assertIn("LAST SESSION CHECKPOINT", res_get)
            self.assertIn("type: Checkpoint", res_get)
            self.assertIn("Feature X complete", res_get)
            self.assertIn("Active goal in [Agent Goal](/agent/goal.md)", res_get)
        finally:
            import shutil
            shutil.rmtree(project_root, ignore_errors=True)

    def test_missing_project_root_error(self):
        res = memory_store(key="test/key", content="test content", project_root="")
        self.assertIn("Error: 'project_root' is required", res)

    def test_project_root_override(self):
        custom_root = tempfile.mkdtemp()
        try:
            res_store = memory_store(key="project/spec", content="Custom project root test", project_root=custom_root)
            self.assertIn("Successfully stored memory", res_store)
            expected_file = os.path.join(custom_root, "memory", "project", "spec.md")
            expected_db = os.path.join(custom_root, ".mcp_memory", "memories.db")
            self.assertTrue(os.path.exists(expected_file))
            self.assertTrue(os.path.exists(expected_db))

            res_ret = memory_retrieve(key="project/spec", project_root=custom_root)
            self.assertIn("Custom project root test", res_ret)
        finally:
            import shutil
            shutil.rmtree(custom_root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

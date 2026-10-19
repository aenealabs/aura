"""
Tests for the Coder Agent's read-only workspace tools and its tool-use loop.

The coder can search and read the project (confined to its root, size-capped, never writing)
and must end by submitting code through submit_code. Without a workspace or tool use it
keeps the single-call paths.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.agent_orchestrator import System2Orchestrator
from src.agents.coder_agent import CODE_TOOL, CoderAgent
from src.agents.coder_tools import MAX_FILE_BYTES, CoderWorkspace
from src.agents.context_objects import ContextItem, ContextSource, HybridContext


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    (root / "app").mkdir(parents=True)
    (root / "app" / "repo.py").write_text(
        "def find_by_email(conn, email):\n"
        "    return conn.execute(f\"SELECT * FROM users WHERE email = '{email}'\")\n"
    )
    (root / "README.md").write_text("Sample\n")
    (root / ".secret").write_text("hidden\n")
    (root / "node_modules").mkdir()
    (tmp_path / "outside.txt").write_text("not in the project\n")
    return root


class _Context:
    def get_hybrid_context(self, target, query):
        return HybridContext(
            items=[
                ContextItem(
                    content="low", source=ContextSource.VECTOR_SEMANTIC, confidence=0.2
                ),
                ContextItem(
                    content="def find_by_email(...)",
                    source=ContextSource.GRAPH_STRUCTURAL,
                    confidence=0.9,
                ),
            ],
            query=query,
            target_entity=target,
        )


class TestWorkspaceTools:
    def test_read_file_numbers_lines(self, project):
        text, error = CoderWorkspace(project).execute(
            "read_file", {"path": "app/repo.py"}
        )

        assert not error
        assert "app/repo.py (lines 1-2 of 2)" in text
        assert "    1  def find_by_email(conn, email):" in text

    def test_read_file_range(self, project):
        text, _ = CoderWorkspace(project).execute(
            "read_file", {"path": "app/repo.py", "start_line": 2, "end_line": 2}
        )

        assert "lines 2-2 of 2" in text
        assert "def find_by_email" not in text

    @pytest.mark.parametrize(
        "path", ["../outside.txt", "/etc/passwd", "app/../../outside.txt"]
    )
    def test_paths_outside_the_project_are_refused(self, project, path):
        text, error = CoderWorkspace(project).execute("read_file", {"path": path})

        assert error
        assert "outside the project" in text

    def test_symlinks_out_of_the_project_are_refused(self, project):
        (project / "escape.txt").symlink_to(project.parent / "outside.txt")
        workspace = CoderWorkspace(project)

        text, error = workspace.execute("read_file", {"path": "escape.txt"})

        assert error and "outside the project" in text
        assert "escape.txt" not in workspace.execute("list_directory", {})[0]

    def test_large_files_must_be_read_in_ranges(self, project):
        (project / "big.py").write_text("x = 1\n" * (MAX_FILE_BYTES // 4))

        text, error = CoderWorkspace(project).execute("read_file", {"path": "big.py"})

        assert error and "read it in ranges" in text

    def test_list_directory_hides_hidden_and_vendor_dirs(self, project):
        text, error = CoderWorkspace(project).execute("list_directory", {})

        assert not error
        assert text.splitlines() == ["app/", "README.md"]

    def test_search_code_returns_best_matches_first(self, project):
        text, error = CoderWorkspace(project, _Context()).execute(
            "search_code", {"query": "email lookup", "entity": "find_by_email"}
        )

        assert not error
        assert text.index("def find_by_email") < text.index("low")

    def test_search_is_offered_only_with_a_context_service(self, project):
        names = [t["name"] for t in CoderWorkspace(project).tool_definitions()]

        assert "search_code" not in names
        assert {"read_file", "list_directory"} <= set(names)

    def test_unknown_tools_and_bad_arguments_are_errors(self, project):
        workspace = CoderWorkspace(project)

        assert workspace.execute("write_file", {"path": "x"}) == (
            "Unknown tool: write_file",
            True,
        )
        text, error = workspace.execute("read_file", {"filename": "x"})
        assert error and "Invalid arguments" in text


def tool_use(name, tool_input, use_id):
    return {"type": "tool_use", "id": use_id, "name": name, "input": tool_input}


def scripted_llm(*turns):
    """An LLM double whose tool turns return the given content blocks in order."""
    llm = MagicMock()
    llm.supports_tool_use = True
    llm.generate_with_tools = AsyncMock(
        side_effect=[
            {"content": content, "stop_reason": "tool_use"} for content in turns
        ]
    )
    llm.generate_structured = AsyncMock(return_value={"code": "structured = 1"})
    llm.generate = AsyncMock(return_value="text = 1")
    return llm


def context():
    return HybridContext(
        items=[], query="Fix SQL injection", target_entity="find_by_email"
    )


class TestCoderToolLoop:
    @pytest.mark.asyncio
    async def test_reads_then_submits(self, project):
        fixed = (
            "def find_by_email(conn, email):\n    return conn.execute('...', (email,))"
        )
        llm = scripted_llm(
            [tool_use("read_file", {"path": "app/repo.py"}, "t1")],
            [tool_use(CODE_TOOL, {"code": fixed, "summary": "Parameterized"}, "t2")],
        )
        agent = CoderAgent(llm_client=llm, workspace=CoderWorkspace(project))

        result = await agent.generate_code(context(), "Fix SQL injection")

        assert result["code"] == fixed
        second_messages = llm.generate_with_tools.call_args_list[1].args[0]
        tool_result = second_messages[-1]["content"][0]
        assert tool_result["tool_use_id"] == "t1"
        assert "SELECT * FROM users" in tool_result["content"]
        assert tool_result["is_error"] is False
        llm.generate_structured.assert_not_called()

    @pytest.mark.asyncio
    async def test_every_turn_calls_a_tool_and_the_last_must_submit(self, project):
        llm = scripted_llm(
            [tool_use("list_directory", {}, "t1")],
            [tool_use(CODE_TOOL, {"code": "y = 2"}, "t2")],
        )
        agent = CoderAgent(
            llm_client=llm, workspace=CoderWorkspace(project), max_tool_turns=2
        )

        await agent.generate_code(context(), "Task")

        choices = [
            c.kwargs["tool_choice"] for c in llm.generate_with_tools.call_args_list
        ]
        assert choices == [{"type": "any"}, {"type": "tool", "name": CODE_TOOL}]

    @pytest.mark.asyncio
    async def test_invalid_submission_is_returned_as_an_error(self, project):
        llm = scripted_llm(
            [tool_use(CODE_TOOL, {"summary": "forgot the code"}, "t1")],
            [tool_use(CODE_TOOL, {"code": "z = 3"}, "t2")],
        )
        agent = CoderAgent(llm_client=llm, workspace=CoderWorkspace(project))

        result = await agent.generate_code(context(), "Task")

        assert result["code"] == "z = 3"
        rejection = llm.generate_with_tools.call_args_list[1].args[0][-1]["content"][0]
        assert rejection["is_error"] is True
        assert "missing code" in rejection["content"]

    @pytest.mark.asyncio
    async def test_text_reply_falls_back_to_a_single_call(self, project):
        llm = scripted_llm([{"type": "text", "text": "Here is the fix"}])
        agent = CoderAgent(llm_client=llm, workspace=CoderWorkspace(project))

        result = await agent.generate_code(context(), "Task")

        assert result["code"] == "structured = 1"

    @pytest.mark.asyncio
    async def test_without_a_workspace_the_loop_is_skipped(self):
        llm = scripted_llm()
        agent = CoderAgent(llm_client=llm)

        result = await agent.generate_code(context(), "Task")

        assert result["code"] == "structured = 1"
        llm.generate_with_tools.assert_not_called()


class TestOrchestratorWorkspace:
    def test_coder_gets_a_workspace_by_default(self):
        orchestrator = System2Orchestrator()

        workspace = orchestrator.coder_agent.workspace
        assert isinstance(workspace, CoderWorkspace)
        assert workspace.context_service is orchestrator.context_service

    def test_agentic_coder_can_be_turned_off(self):
        assert System2Orchestrator(agentic_coder=False).coder_agent.workspace is None

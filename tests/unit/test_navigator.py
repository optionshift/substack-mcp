import pytest


TOOL_NAMES = [
    "ss_navigator",
    "ss_auth_check",
    "ss_get_fyp_feed",
    "ss_get_subscription_feed",
    "ss_get_notes_feed",
    "ss_get_likes",
    "ss_get_restacks",
    "ss_get_post_content",
    "ss_get_subscriptions",
    "ss_search_publications",
]


class TestNavigatorResponse:
    """Test returns valid navigator response."""

    def test_returns_dict(self):
        from src.tools.navigator import get_navigator

        result = get_navigator()
        assert isinstance(result, dict)

    def test_has_tools_section(self):
        from src.tools.navigator import get_navigator

        result = get_navigator()
        assert "tools" in result

    def test_has_workflows_section(self):
        from src.tools.navigator import get_navigator

        result = get_navigator()
        assert "workflows" in result

    def test_has_auth_rotation_section(self):
        from src.tools.navigator import get_navigator

        result = get_navigator()
        assert "auth_rotation" in result


class TestNavigatorToolDiscovery:
    """Test includes all 10 tool names."""

    def test_includes_all_tool_names(self):
        from src.tools.navigator import get_navigator

        result = get_navigator()
        tools = result["tools"]

        for tool_name in TOOL_NAMES:
            found = any(t["name"] == tool_name for t in tools)
            assert found, f"Tool '{tool_name}' not found in navigator"

    def test_tools_have_descriptions(self):
        from src.tools.navigator import get_navigator

        result = get_navigator()
        for tool in result["tools"]:
            assert "name" in tool
            assert "description" in tool
            assert len(tool["description"]) > 0


class TestNavigatorAuthRotation:
    """Test includes auth rotation instructions."""

    def test_auth_rotation_has_steps(self):
        from src.tools.navigator import get_navigator

        result = get_navigator()
        auth = result["auth_rotation"]
        assert isinstance(auth, dict) or isinstance(auth, str)


class TestNavigatorWorkflows:
    """Test includes workflow guides."""

    def test_has_daily_ingestion_workflow(self):
        from src.tools.navigator import get_navigator

        result = get_navigator()
        workflows = result["workflows"]
        assert any("ingestion" in str(w).lower() for w in workflows)

    def test_has_content_drafting_workflow(self):
        from src.tools.navigator import get_navigator

        result = get_navigator()
        workflows = result["workflows"]
        assert any("draft" in str(w).lower() for w in workflows)

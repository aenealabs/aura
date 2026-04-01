"""
Tests for Browser Tool Agent module.

Tests cover:
- BrowserActionType enum
- SelectorStrategy enum
- BrowserType enum
- BrowserAction dataclass factory methods
- BrowserSessionConfig dataclass
- BrowserToolAgent session management
- BrowserToolAgent action execution
- BrowserToolAgent workflow execution
- BrowserToolAgent data extraction
- BrowserToolAgent tab management
"""

from datetime import datetime

import pytest


class TestBrowserActionTypeEnum:
    """Tests for BrowserActionType enum."""

    def test_all_action_types_exist(self):
        """Test all expected action types are defined."""
        from src.agents.browser_tool_agent import BrowserActionType

        expected = [
            "NAVIGATE",
            "CLICK",
            "TYPE",
            "SCROLL",
            "SCREENSHOT",
            "WAIT",
            "WAIT_FOR_SELECTOR",
            "EXTRACT",
            "EXECUTE_JS",
            "NEW_TAB",
            "CLOSE_TAB",
            "SWITCH_TAB",
            "HOVER",
            "SELECT",
            "CLEAR",
            "PRESS",
            "FILL_FORM",
            "GET_ATTRIBUTE",
            "GET_TEXT",
        ]

        for action in expected:
            assert hasattr(BrowserActionType, action)

    def test_action_type_values(self):
        """Test action type enum values."""
        from src.agents.browser_tool_agent import BrowserActionType

        assert BrowserActionType.NAVIGATE.value == "navigate"
        assert BrowserActionType.CLICK.value == "click"
        assert BrowserActionType.SCREENSHOT.value == "screenshot"


class TestSelectorStrategyEnum:
    """Tests for SelectorStrategy enum."""

    def test_all_strategies_exist(self):
        """Test all selector strategies are defined."""
        from src.agents.browser_tool_agent import SelectorStrategy

        expected = ["CSS", "XPATH", "TEXT", "ROLE", "LABEL", "PLACEHOLDER", "TEST_ID"]

        for strategy in expected:
            assert hasattr(SelectorStrategy, strategy)

    def test_strategy_values(self):
        """Test selector strategy values."""
        from src.agents.browser_tool_agent import SelectorStrategy

        assert SelectorStrategy.CSS.value == "css"
        assert SelectorStrategy.XPATH.value == "xpath"


class TestBrowserTypeEnum:
    """Tests for BrowserType enum."""

    def test_all_browser_types_exist(self):
        """Test all browser types are defined."""
        from src.agents.browser_tool_agent import BrowserType

        assert BrowserType.CHROMIUM.value == "chromium"
        assert BrowserType.FIREFOX.value == "firefox"
        assert BrowserType.WEBKIT.value == "webkit"


class TestBrowserAction:
    """Tests for BrowserAction dataclass."""

    def test_basic_creation(self):
        """Test basic BrowserAction creation."""
        from src.agents.browser_tool_agent import BrowserAction, BrowserActionType

        action = BrowserAction(action_type=BrowserActionType.CLICK, selector="#btn")

        assert action.action_type == BrowserActionType.CLICK
        assert action.selector == "#btn"
        assert action.timeout_ms == 30000

    def test_navigate_factory(self):
        """Test navigate factory method."""
        from src.agents.browser_tool_agent import BrowserAction, BrowserActionType

        action = BrowserAction.navigate("https://example.com")

        assert action.action_type == BrowserActionType.NAVIGATE
        assert action.value == "https://example.com"
        assert action.options["wait_until"] == "load"

    def test_click_factory(self):
        """Test click factory method."""
        from src.agents.browser_tool_agent import BrowserAction, BrowserActionType

        action = BrowserAction.click("#submit-button")

        assert action.action_type == BrowserActionType.CLICK
        assert action.selector == "#submit-button"

    def test_type_text_factory(self):
        """Test type_text factory method."""
        from src.agents.browser_tool_agent import BrowserAction, BrowserActionType

        action = BrowserAction.type_text("#input", "hello world", delay_ms=100)

        assert action.action_type == BrowserActionType.TYPE
        assert action.selector == "#input"
        assert action.value == "hello world"
        assert action.options["delay"] == 100

    def test_screenshot_factory(self):
        """Test screenshot factory method."""
        from src.agents.browser_tool_agent import BrowserAction, BrowserActionType

        action = BrowserAction.screenshot(full_page=True)

        assert action.action_type == BrowserActionType.SCREENSHOT
        assert action.options["full_page"] is True

    def test_wait_for_factory(self):
        """Test wait_for factory method."""
        from src.agents.browser_tool_agent import BrowserAction, BrowserActionType

        action = BrowserAction.wait_for(".loading", timeout_ms=5000)

        assert action.action_type == BrowserActionType.WAIT_FOR_SELECTOR
        assert action.selector == ".loading"
        assert action.timeout_ms == 5000

    def test_execute_js_factory(self):
        """Test execute_js factory method."""
        from src.agents.browser_tool_agent import BrowserAction, BrowserActionType

        action = BrowserAction.execute_js("return document.title;")

        assert action.action_type == BrowserActionType.EXECUTE_JS
        assert action.value == "return document.title;"

    def test_extract_text_factory(self):
        """Test extract_text factory method."""
        from src.agents.browser_tool_agent import BrowserAction, BrowserActionType

        action = BrowserAction.extract_text("h1.title")

        assert action.action_type == BrowserActionType.GET_TEXT
        assert action.selector == "h1.title"


class TestBrowserSessionConfig:
    """Tests for BrowserSessionConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        from src.agents.browser_tool_agent import BrowserSessionConfig, BrowserType

        config = BrowserSessionConfig()

        assert config.browser_type == BrowserType.CHROMIUM
        assert config.headless is True
        assert config.viewport_width == 1920
        assert config.viewport_height == 1080
        assert config.locale == "en-US"
        assert config.session_timeout_minutes == 30

    def test_custom_config(self):
        """Test custom configuration."""
        from src.agents.browser_tool_agent import BrowserSessionConfig, BrowserType

        config = BrowserSessionConfig(
            browser_type=BrowserType.FIREFOX,
            headless=False,
            viewport_width=1280,
            viewport_height=720,
        )

        assert config.browser_type == BrowserType.FIREFOX
        assert config.headless is False
        assert config.viewport_width == 1280


class TestDataExtractionSpec:
    """Tests for DataExtractionSpec dataclass."""

    def test_basic_creation(self):
        """Test basic DataExtractionSpec creation."""
        from src.agents.browser_tool_agent import DataExtractionSpec

        spec = DataExtractionSpec(
            fields={"title": "h1", "price": ".price"},
        )

        assert spec.fields == {"title": "h1", "price": ".price"}
        assert spec.list_selector is None

    def test_list_extraction(self):
        """Test list extraction spec."""
        from src.agents.browser_tool_agent import DataExtractionSpec

        spec = DataExtractionSpec(
            fields={"name": ".item-name", "price": ".item-price"},
            list_selector=".product-item",
        )

        assert spec.list_selector == ".product-item"


class TestTabInfo:
    """Tests for TabInfo dataclass."""

    def test_basic_creation(self):
        """Test basic TabInfo creation."""
        from src.agents.browser_tool_agent import TabInfo

        tab = TabInfo(
            tab_id="tab-1",
            url="https://example.com",
            title="Example",
            is_active=True,
        )

        assert tab.tab_id == "tab-1"
        assert tab.url == "https://example.com"
        assert tab.is_active is True
        assert isinstance(tab.created_at, datetime)


class TestBrowserState:
    """Tests for BrowserState dataclass."""

    def test_basic_creation(self):
        """Test basic BrowserState creation."""
        from src.agents.browser_tool_agent import BrowserState

        state = BrowserState(
            session_id="session-1",
            current_url="https://example.com",
            page_title="Example",
            tabs=[],
            active_tab_id="tab-1",
        )

        assert state.session_id == "session-1"
        assert state.current_url == "https://example.com"
        assert state.screenshot_base64 is None
        assert isinstance(state.last_updated_at, datetime)


class TestActionResult:
    """Tests for ActionResult dataclass."""

    def test_success_result(self):
        """Test successful action result."""
        from src.agents.browser_tool_agent import ActionResult, BrowserActionType

        result = ActionResult(
            success=True,
            action_type=BrowserActionType.CLICK,
            duration_ms=150.5,
            result_value={"clicked": True},
        )

        assert result.success is True
        assert result.error is None
        assert result.duration_ms == 150.5

    def test_failure_result(self):
        """Test failed action result."""
        from src.agents.browser_tool_agent import ActionResult, BrowserActionType

        result = ActionResult(
            success=False,
            action_type=BrowserActionType.CLICK,
            duration_ms=50.0,
            error="Element not found",
        )

        assert result.success is False
        assert result.error == "Element not found"


class TestBrowserToolAgentInit:
    """Tests for BrowserToolAgent initialization."""

    def test_basic_initialization(self):
        """Test basic agent initialization."""
        from src.agents.browser_tool_agent import BrowserToolAgent

        agent = BrowserToolAgent()

        assert agent.playwright is None
        assert agent.default_config is not None
        assert agent._sessions == {}
        assert agent._action_history == {}

    def test_initialization_with_config(self):
        """Test initialization with custom config."""
        from src.agents.browser_tool_agent import BrowserSessionConfig, BrowserToolAgent

        config = BrowserSessionConfig(headless=False)
        agent = BrowserToolAgent(default_config=config)

        assert agent.default_config.headless is False

    def test_capability_property(self):
        """Test capability property."""
        from src.agents.browser_tool_agent import BrowserToolAgent

        agent = BrowserToolAgent()
        assert agent.capability == "browser_automation"


class TestBrowserToolAgentSession:
    """Tests for BrowserToolAgent session management."""

    @pytest.fixture
    def agent(self):
        """Create agent for testing."""
        from src.agents.browser_tool_agent import BrowserToolAgent

        return BrowserToolAgent()

    @pytest.mark.asyncio
    async def test_create_session(self, agent):
        """Test session creation."""
        session_id = await agent.create_session()

        assert session_id is not None
        assert len(session_id) > 0
        assert session_id in agent._sessions
        assert session_id in agent._action_history

    @pytest.mark.asyncio
    async def test_create_session_with_config(self, agent):
        """Test session creation with custom config."""
        from src.agents.browser_tool_agent import BrowserSessionConfig

        config = BrowserSessionConfig(session_timeout_minutes=60)
        session_id = await agent.create_session(config=config)

        session = agent._sessions[session_id]
        assert session["config"].session_timeout_minutes == 60

    @pytest.mark.asyncio
    async def test_close_session(self, agent):
        """Test session closure."""
        session_id = await agent.create_session()
        await agent.close_session(session_id)

        assert session_id not in agent._sessions
        assert session_id not in agent._action_history

    @pytest.mark.asyncio
    async def test_close_nonexistent_session(self, agent):
        """Test closing nonexistent session doesn't raise."""
        await agent.close_session("nonexistent")
        # Should not raise


class TestBrowserToolAgentActions:
    """Tests for BrowserToolAgent action execution."""

    @pytest.fixture
    def agent(self):
        """Create agent for testing."""
        from src.agents.browser_tool_agent import BrowserToolAgent

        return BrowserToolAgent()

    @pytest.mark.asyncio
    async def test_execute_navigate_action(self, agent):
        """Test execute navigate action."""
        from src.agents.browser_tool_agent import BrowserAction

        session_id = await agent.create_session()

        # Create initial tab
        await agent.new_tab(session_id)

        state = await agent.execute_action(
            session_id, BrowserAction.navigate("https://example.com")
        )

        assert state is not None
        assert isinstance(state.current_url, str)

    @pytest.mark.asyncio
    async def test_execute_click_action(self, agent):
        """Test execute click action."""
        from src.agents.browser_tool_agent import BrowserAction

        session_id = await agent.create_session()

        state = await agent.execute_action(session_id, BrowserAction.click("#button"))

        assert state is not None

    @pytest.mark.asyncio
    async def test_execute_type_action(self, agent):
        """Test execute type action."""
        from src.agents.browser_tool_agent import BrowserAction

        session_id = await agent.create_session()

        state = await agent.execute_action(
            session_id, BrowserAction.type_text("#input", "test text")
        )

        assert state is not None

    @pytest.mark.asyncio
    async def test_execute_action_invalid_session(self, agent):
        """Test execute action with invalid session."""
        from src.agents.browser_tool_agent import BrowserAction

        with pytest.raises(ValueError, match="Session not found"):
            await agent.execute_action(
                "invalid-session", BrowserAction.click("#button")
            )

    @pytest.mark.asyncio
    async def test_action_history_recorded(self, agent):
        """Test action history is recorded."""
        from src.agents.browser_tool_agent import BrowserAction

        session_id = await agent.create_session()

        await agent.execute_action(session_id, BrowserAction.click("#button"))

        history = await agent.get_action_history(session_id)
        assert len(history) == 1
        assert history[0].success is True


class TestBrowserToolAgentWorkflow:
    """Tests for BrowserToolAgent workflow execution."""

    @pytest.fixture
    def agent(self):
        """Create agent for testing."""
        from src.agents.browser_tool_agent import BrowserToolAgent

        return BrowserToolAgent()

    @pytest.mark.asyncio
    async def test_execute_workflow(self, agent):
        """Test workflow execution."""
        from src.agents.browser_tool_agent import BrowserAction

        session_id = await agent.create_session()
        await agent.new_tab(session_id)

        actions = [
            BrowserAction.navigate("https://example.com"),
            BrowserAction.click("#button"),
            BrowserAction.type_text("#input", "test"),
        ]

        states = await agent.execute_workflow(session_id, actions)

        assert len(states) == 3

    @pytest.mark.asyncio
    async def test_execute_workflow_stop_on_error(self, agent):
        """Test workflow stops on error when configured."""
        from src.agents.browser_tool_agent import BrowserAction

        session_id = await agent.create_session()

        # This workflow should complete all actions in mock mode
        actions = [
            BrowserAction.click("#first"),
            BrowserAction.click("#second"),
        ]

        states = await agent.execute_workflow(session_id, actions, stop_on_error=True)

        # In mock mode, actions succeed
        assert len(states) >= 1


class TestBrowserToolAgentDataExtraction:
    """Tests for BrowserToolAgent data extraction."""

    @pytest.fixture
    def agent(self):
        """Create agent for testing."""
        from src.agents.browser_tool_agent import BrowserToolAgent

        return BrowserToolAgent()

    @pytest.mark.asyncio
    async def test_extract_data(self, agent):
        """Test data extraction."""
        from src.agents.browser_tool_agent import DataExtractionSpec

        session_id = await agent.create_session()

        spec = DataExtractionSpec(
            fields={"title": "h1", "description": "p.desc"},
        )

        result = await agent.extract_data(session_id, spec)

        assert result is not None
        assert result.extraction_time_ms >= 0

    @pytest.mark.asyncio
    async def test_extract_data_invalid_session(self, agent):
        """Test data extraction with invalid session."""
        from src.agents.browser_tool_agent import DataExtractionSpec

        spec = DataExtractionSpec(fields={"title": "h1"})

        with pytest.raises(ValueError, match="Session not found"):
            await agent.extract_data("invalid-session", spec)


class TestBrowserToolAgentFormFilling:
    """Tests for BrowserToolAgent form filling."""

    @pytest.fixture
    def agent(self):
        """Create agent for testing."""
        from src.agents.browser_tool_agent import BrowserToolAgent

        return BrowserToolAgent()

    @pytest.mark.asyncio
    async def test_fill_form(self, agent):
        """Test form filling."""
        session_id = await agent.create_session()

        form_data = {
            "#username": "testuser",
            "#password": "testpass",
        }

        state = await agent.fill_form(session_id, form_data)

        assert state is not None

    @pytest.mark.asyncio
    async def test_fill_form_with_submit(self, agent):
        """Test form filling with submit."""
        session_id = await agent.create_session()

        form_data = {"#email": "test@example.com"}

        state = await agent.fill_form(session_id, form_data, submit=True)

        assert state is not None

    @pytest.mark.asyncio
    async def test_fill_form_with_selector(self, agent):
        """Test form filling with form selector."""
        session_id = await agent.create_session()

        form_data = {"#name": "John Doe"}

        state = await agent.fill_form(
            session_id, form_data, form_selector="#registration-form"
        )

        assert state is not None


class TestBrowserToolAgentTabManagement:
    """Tests for BrowserToolAgent tab management."""

    @pytest.fixture
    def agent(self):
        """Create agent for testing."""
        from src.agents.browser_tool_agent import BrowserToolAgent

        return BrowserToolAgent()

    @pytest.mark.asyncio
    async def test_new_tab(self, agent):
        """Test creating new tab."""
        session_id = await agent.create_session()

        tab_id = await agent.new_tab(session_id)

        assert tab_id is not None
        session = agent._sessions[session_id]
        assert tab_id in session["pages"]
        assert session["active_tab"] == tab_id

    @pytest.mark.asyncio
    async def test_new_tab_with_url(self, agent):
        """Test creating new tab with URL."""
        session_id = await agent.create_session()

        tab_id = await agent.new_tab(session_id, url="https://example.com")

        session = agent._sessions[session_id]
        assert session["pages"][tab_id]["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_new_tab_invalid_session(self, agent):
        """Test new tab with invalid session."""
        with pytest.raises(ValueError, match="Session not found"):
            await agent.new_tab("invalid-session")

    @pytest.mark.asyncio
    async def test_switch_tab(self, agent):
        """Test switching tabs."""
        session_id = await agent.create_session()

        tab1 = await agent.new_tab(session_id)
        tab2 = await agent.new_tab(session_id)

        state = await agent.switch_tab(session_id, tab1)

        session = agent._sessions[session_id]
        assert session["active_tab"] == tab1

    @pytest.mark.asyncio
    async def test_switch_tab_invalid_tab(self, agent):
        """Test switching to invalid tab."""
        session_id = await agent.create_session()
        await agent.new_tab(session_id)

        with pytest.raises(ValueError, match="Tab not found"):
            await agent.switch_tab(session_id, "invalid-tab")

    @pytest.mark.asyncio
    async def test_close_tab(self, agent):
        """Test closing tab."""
        session_id = await agent.create_session()

        tab1 = await agent.new_tab(session_id)
        tab2 = await agent.new_tab(session_id)

        state = await agent.close_tab(session_id, tab1)

        session = agent._sessions[session_id]
        assert tab1 not in session["pages"]
        assert tab2 in session["pages"]

    @pytest.mark.asyncio
    async def test_close_active_tab_switches(self, agent):
        """Test closing active tab switches to another."""
        session_id = await agent.create_session()

        tab1 = await agent.new_tab(session_id)
        tab2 = await agent.new_tab(session_id)

        # tab2 is now active
        assert agent._sessions[session_id]["active_tab"] == tab2

        await agent.close_tab(session_id, tab2)

        # Should switch to tab1
        assert agent._sessions[session_id]["active_tab"] == tab1

    @pytest.mark.asyncio
    async def test_close_last_tab(self, agent):
        """Test closing last tab."""
        session_id = await agent.create_session()

        tab1 = await agent.new_tab(session_id)

        await agent.close_tab(session_id, tab1)

        session = agent._sessions[session_id]
        assert session["active_tab"] is None
        assert len(session["pages"]) == 0


class TestBrowserToolAgentCookies:
    """Tests for BrowserToolAgent cookie management."""

    @pytest.fixture
    def agent(self):
        """Create agent for testing."""
        from src.agents.browser_tool_agent import BrowserToolAgent

        return BrowserToolAgent()

    @pytest.mark.asyncio
    async def test_get_cookies(self, agent):
        """Test getting cookies."""
        session_id = await agent.create_session()

        cookies = await agent.get_cookies(session_id)

        assert isinstance(cookies, list)

    @pytest.mark.asyncio
    async def test_get_cookies_invalid_session(self, agent):
        """Test getting cookies with invalid session."""
        with pytest.raises(ValueError, match="Session not found"):
            await agent.get_cookies("invalid-session")

    @pytest.mark.asyncio
    async def test_set_cookies(self, agent):
        """Test setting cookies."""
        session_id = await agent.create_session()

        cookies = [{"name": "session", "value": "abc123", "domain": "example.com"}]

        await agent.set_cookies(session_id, cookies)
        # Should not raise

    @pytest.mark.asyncio
    async def test_set_cookies_invalid_session(self, agent):
        """Test setting cookies with invalid session."""
        with pytest.raises(ValueError, match="Session not found"):
            await agent.set_cookies("invalid-session", [])


class TestBrowserToolAgentNavigation:
    """Tests for BrowserToolAgent navigation."""

    @pytest.fixture
    def agent(self):
        """Create agent for testing."""
        from src.agents.browser_tool_agent import BrowserToolAgent

        return BrowserToolAgent()

    @pytest.mark.asyncio
    async def test_wait_for_navigation(self, agent):
        """Test wait for navigation."""
        session_id = await agent.create_session()
        await agent.new_tab(session_id)

        state = await agent.wait_for_navigation(session_id)

        assert state is not None


class TestBrowserToolAgentStats:
    """Tests for BrowserToolAgent statistics."""

    @pytest.fixture
    def agent(self):
        """Create agent for testing."""
        from src.agents.browser_tool_agent import BrowserToolAgent

        return BrowserToolAgent()

    def test_get_service_stats_empty(self, agent):
        """Test stats with no sessions."""
        stats = agent.get_service_stats()

        assert stats["active_sessions"] == 0
        assert stats["total_actions_executed"] == 0
        assert stats["successful_actions"] == 0
        assert stats["success_rate"] == 0

    @pytest.mark.asyncio
    async def test_get_service_stats_with_activity(self, agent):
        """Test stats with activity."""
        from src.agents.browser_tool_agent import BrowserAction

        session_id = await agent.create_session()
        await agent.execute_action(session_id, BrowserAction.click("#btn"))

        stats = agent.get_service_stats()

        assert stats["active_sessions"] == 1
        assert stats["total_actions_executed"] == 1
        assert stats["successful_actions"] == 1
        assert stats["success_rate"] == 100


class TestBrowserToolAgentActionHistory:
    """Tests for BrowserToolAgent action history."""

    @pytest.fixture
    def agent(self):
        """Create agent for testing."""
        from src.agents.browser_tool_agent import BrowserToolAgent

        return BrowserToolAgent()

    @pytest.mark.asyncio
    async def test_get_action_history(self, agent):
        """Test getting action history."""
        from src.agents.browser_tool_agent import BrowserAction

        session_id = await agent.create_session()

        await agent.execute_action(session_id, BrowserAction.click("#a"))
        await agent.execute_action(session_id, BrowserAction.click("#b"))
        await agent.execute_action(session_id, BrowserAction.click("#c"))

        history = await agent.get_action_history(session_id)

        assert len(history) == 3

    @pytest.mark.asyncio
    async def test_get_action_history_with_limit(self, agent):
        """Test getting action history with limit."""
        from src.agents.browser_tool_agent import BrowserAction

        session_id = await agent.create_session()

        await agent.execute_action(session_id, BrowserAction.click("#a"))
        await agent.execute_action(session_id, BrowserAction.click("#b"))
        await agent.execute_action(session_id, BrowserAction.click("#c"))

        history = await agent.get_action_history(session_id, limit=2)

        assert len(history) == 2
        # Should return last 2

    @pytest.mark.asyncio
    async def test_get_action_history_nonexistent_session(self, agent):
        """Test getting history for nonexistent session."""
        history = await agent.get_action_history("nonexistent")

        assert history == []


class TestBrowserToolAgentExtractionScript:
    """Tests for extraction script building."""

    @pytest.fixture
    def agent(self):
        """Create agent for testing."""
        from src.agents.browser_tool_agent import BrowserToolAgent

        return BrowserToolAgent()

    def test_build_extraction_script_simple(self, agent):
        """Test building simple extraction script."""
        from src.agents.browser_tool_agent import DataExtractionSpec

        spec = DataExtractionSpec(
            fields={"title": "h1", "price": ".price"},
        )

        script = agent._build_extraction_script(spec)

        assert "title" in script
        assert "h1" in script
        assert "price" in script

    def test_build_extraction_script_with_list(self, agent):
        """Test building list extraction script."""
        from src.agents.browser_tool_agent import DataExtractionSpec

        spec = DataExtractionSpec(
            fields={"name": ".name"},
            list_selector=".item",
        )

        script = agent._build_extraction_script(spec)

        assert "querySelectorAll" in script
        assert ".item" in script


class TestBrowserToolAgentActionImplementation:
    """Tests for action implementation details."""

    @pytest.fixture
    def agent(self):
        """Create agent for testing."""
        from src.agents.browser_tool_agent import BrowserToolAgent

        return BrowserToolAgent()

    @pytest.mark.asyncio
    async def test_navigate_updates_page_url(self, agent):
        """Test navigate action updates page URL."""
        from src.agents.browser_tool_agent import BrowserAction

        session_id = await agent.create_session()
        tab_id = await agent.new_tab(session_id)

        await agent.execute_action(
            session_id, BrowserAction.navigate("https://test.com")
        )

        session = agent._sessions[session_id]
        assert session["pages"][tab_id]["url"] == "https://test.com"

    @pytest.mark.asyncio
    async def test_screenshot_action(self, agent):
        """Test screenshot action returns result."""
        from src.agents.browser_tool_agent import BrowserAction

        session_id = await agent.create_session()

        state = await agent.execute_action(session_id, BrowserAction.screenshot())

        assert state is not None

    @pytest.mark.asyncio
    async def test_execute_js_action(self, agent):
        """Test JavaScript execution action."""
        from src.agents.browser_tool_agent import BrowserAction

        session_id = await agent.create_session()

        state = await agent.execute_action(
            session_id, BrowserAction.execute_js("return 1 + 1;")
        )

        assert state is not None

    @pytest.mark.asyncio
    async def test_wait_for_selector_action(self, agent):
        """Test wait for selector action."""
        from src.agents.browser_tool_agent import BrowserAction

        session_id = await agent.create_session()

        state = await agent.execute_action(
            session_id, BrowserAction.wait_for(".element")
        )

        assert state is not None

    @pytest.mark.asyncio
    async def test_get_text_action(self, agent):
        """Test get text action."""
        from src.agents.browser_tool_agent import BrowserAction

        session_id = await agent.create_session()

        state = await agent.execute_action(session_id, BrowserAction.extract_text("h1"))

        assert state is not None

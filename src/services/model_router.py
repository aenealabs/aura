"""
Model Router Service for Cost Optimization (ADR-028 Phase 2)

Implements intelligent model selection to optimize cost/quality/latency tradeoffs.
Supports dynamic routing rules via SSM Parameter Store and A/B testing.

Cost Savings Target: 30-50% reduction in LLM costs through smart routing.
"""

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# AWS imports
try:
    import boto3
    from botocore.exceptions import ClientError

    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False


class ModelTier(Enum):
    """
    Model tiers for task-based selection.

    - FAST: Haiku - simple classification, expansion, low-stakes tasks
    - ACCURATE: Sonnet - security analysis, standard patches, code review
    - MAXIMUM: Opus - cross-codebase reasoning, novel threats, complex refactoring
    """

    FAST = "fast"
    ACCURATE = "accurate"
    MAXIMUM = "maximum"


class TaskComplexity(Enum):
    """Task complexity levels for routing decisions."""

    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


@dataclass
class ModelConfig:
    """Configuration for a specific model."""

    model_id: str
    tier: ModelTier
    input_cost_per_million: float
    output_cost_per_million: float
    avg_latency_ms: float = 500.0
    max_tokens: int = 4096


@dataclass
class RoutingRule:
    """A routing rule mapping task types to models."""

    task_type: str
    complexity: TaskComplexity
    tier: ModelTier
    description: str = ""
    enabled: bool = True


@dataclass
class RoutingDecision:
    """Result of a routing decision."""

    model_id: str
    tier: ModelTier
    complexity: TaskComplexity
    rule_matched: str
    is_ab_test: bool = False
    ab_variant: str | None = None
    estimated_cost_per_1k_tokens: float = 0.0
    decision_time_ms: float = 0.0


@dataclass
class ABTestConfig:
    """Configuration for A/B testing routing rules."""

    enabled: bool = False
    experiment_id: str = ""
    control_tier: ModelTier = ModelTier.ACCURATE
    treatment_tier: ModelTier = ModelTier.FAST
    traffic_split: float = 0.5  # 0.5 = 50% treatment
    task_types: list[str] = field(default_factory=list)


# Default model configurations
DEFAULT_MODELS: dict[ModelTier, ModelConfig] = {
    ModelTier.FAST: ModelConfig(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        tier=ModelTier.FAST,
        input_cost_per_million=0.25,
        output_cost_per_million=1.25,
        avg_latency_ms=200,
        max_tokens=4096,
    ),
    ModelTier.ACCURATE: ModelConfig(
        model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
        tier=ModelTier.ACCURATE,
        input_cost_per_million=3.00,
        output_cost_per_million=15.00,
        avg_latency_ms=800,
        max_tokens=4096,
    ),
    ModelTier.MAXIMUM: ModelConfig(
        model_id="anthropic.claude-3-opus-20240229-v1:0",
        tier=ModelTier.MAXIMUM,
        input_cost_per_million=15.00,
        output_cost_per_million=75.00,
        avg_latency_ms=2000,
        max_tokens=4096,
    ),
}

# Default routing rules (operation -> tier mapping)
DEFAULT_ROUTING_RULES: list[RoutingRule] = [
    # Simple tasks -> FAST tier (~40% of calls, ~$0.25/1M tokens)
    RoutingRule(
        "query_intent_analysis",
        TaskComplexity.SIMPLE,
        ModelTier.FAST,
        "Classify query intent",
    ),
    RoutingRule(
        "query_expansion",
        TaskComplexity.SIMPLE,
        ModelTier.FAST,
        "Expand search queries",
    ),
    RoutingRule(
        "file_type_classification",
        TaskComplexity.SIMPLE,
        ModelTier.FAST,
        "Classify file types",
    ),
    RoutingRule(
        "syntax_validation", TaskComplexity.SIMPLE, ModelTier.FAST, "Validate syntax"
    ),
    RoutingRule(
        "format_conversion", TaskComplexity.SIMPLE, ModelTier.FAST, "Convert formats"
    ),
    RoutingRule(
        "metadata_extraction", TaskComplexity.SIMPLE, ModelTier.FAST, "Extract metadata"
    ),
    RoutingRule(
        "simple_summarization",
        TaskComplexity.SIMPLE,
        ModelTier.FAST,
        "Simple summaries",
    ),
    # Medium tasks -> ACCURATE tier (~55% of calls, ~$3/1M tokens)
    RoutingRule(
        "vulnerability_ranking",
        TaskComplexity.MEDIUM,
        ModelTier.ACCURATE,
        "Rank vulnerabilities",
    ),
    RoutingRule(
        "security_result_scoring",
        TaskComplexity.MEDIUM,
        ModelTier.ACCURATE,
        "Score security results",
    ),
    RoutingRule(
        "patch_generation",
        TaskComplexity.MEDIUM,
        ModelTier.ACCURATE,
        "Generate patches",
    ),
    RoutingRule(
        "code_review", TaskComplexity.MEDIUM, ModelTier.ACCURATE, "Review code"
    ),
    RoutingRule(
        "threat_assessment", TaskComplexity.MEDIUM, ModelTier.ACCURATE, "Assess threats"
    ),
    RoutingRule(
        "compliance_check",
        TaskComplexity.MEDIUM,
        ModelTier.ACCURATE,
        "Check compliance",
    ),
    RoutingRule(
        "single_file_analysis",
        TaskComplexity.MEDIUM,
        ModelTier.ACCURATE,
        "Analyze single file",
    ),
    RoutingRule(
        "cve_impact_assessment",
        TaskComplexity.MEDIUM,
        ModelTier.ACCURATE,
        "Assess CVE impact",
    ),
    RoutingRule(
        "rca_generation", TaskComplexity.MEDIUM, ModelTier.ACCURATE, "Generate RCA"
    ),
    RoutingRule(
        "mitigation_planning",
        TaskComplexity.MEDIUM,
        ModelTier.ACCURATE,
        "Plan mitigations",
    ),
    # Complex tasks -> MAXIMUM tier (~5% of calls, ~$15/1M tokens)
    RoutingRule(
        "cross_codebase_correlation",
        TaskComplexity.COMPLEX,
        ModelTier.MAXIMUM,
        "Cross-codebase analysis",
    ),
    RoutingRule(
        "novel_threat_detection",
        TaskComplexity.COMPLEX,
        ModelTier.MAXIMUM,
        "Detect novel threats",
    ),
    RoutingRule(
        "multi_file_refactoring",
        TaskComplexity.COMPLEX,
        ModelTier.MAXIMUM,
        "Multi-file refactor",
    ),
    RoutingRule(
        "compliance_edge_case",
        TaskComplexity.COMPLEX,
        ModelTier.MAXIMUM,
        "Complex compliance",
    ),
    RoutingRule(
        "architecture_impact_analysis",
        TaskComplexity.COMPLEX,
        ModelTier.MAXIMUM,
        "Architecture impact",
    ),
    RoutingRule(
        "zero_day_pattern_analysis",
        TaskComplexity.COMPLEX,
        ModelTier.MAXIMUM,
        "Zero-day analysis",
    ),
    RoutingRule(
        "dependency_chain_reasoning",
        TaskComplexity.COMPLEX,
        ModelTier.MAXIMUM,
        "Dependency reasoning",
    ),
]


@dataclass
class ComplexityScore:
    """Result of dynamic complexity scoring."""

    overall_score: float  # 0.0 (simple) to 1.0 (complex)
    input_token_score: float
    code_complexity_score: float
    historical_failure_score: float
    recommended_tier: ModelTier
    scoring_details: dict[str, Any] = field(default_factory=dict)


class ModelRouter:
    """
    Intelligent Model Router for LLM cost optimization.

    Features:
    - Dynamic routing rules via SSM Parameter Store
    - Dynamic complexity scoring (input tokens, code complexity, historical failures)
    - A/B testing for routing experiments
    - Cost tracking and metrics
    - Fallback to default rules when SSM unavailable

    Usage:
        >>> router = ModelRouter()
        >>> decision = router.route("patch_generation")
        >>> print(f"Using {decision.tier.value} tier: {decision.model_id}")
        >>> print(f"Estimated cost: ${decision.estimated_cost_per_1k_tokens:.4f}/1K tokens")

        # With dynamic complexity scoring
        >>> decision = router.route_with_complexity(
        ...     task_type="patch_generation",
        ...     input_text="def complex_function():...",
        ...     context={"code_complexity": 15, "request_id": "123"}
        ... )
    """

    # Complexity scoring thresholds
    INPUT_TOKEN_THRESHOLD_SIMPLE = 1000  # Below this = simple
    INPUT_TOKEN_THRESHOLD_COMPLEX = 4000  # Above this = complex
    CODE_COMPLEXITY_THRESHOLD_SIMPLE = 5  # Cyclomatic complexity
    CODE_COMPLEXITY_THRESHOLD_COMPLEX = 15
    FAILURE_RATE_THRESHOLD_HIGH = 0.3  # Historical failure rate

    def __init__(
        self,
        environment: str | None = None,
        ssm_prefix: str = "/aura",
        enable_ssm: bool = True,
        enable_metrics: bool = True,
    ):
        """
        Initialize Model Router.

        Args:
            environment: Environment name (dev/staging/prod)
            ssm_prefix: SSM Parameter Store prefix
            enable_ssm: Enable SSM Parameter Store for dynamic config
            enable_metrics: Enable CloudWatch metrics
        """
        self.environment = environment or os.environ.get("AURA_ENV", "dev")
        self.ssm_prefix = ssm_prefix

        # Check for environment variable to disable SSM (useful for testing)
        ssm_disabled_by_env = os.environ.get(
            "MODEL_ROUTER_DISABLE_SSM", ""
        ).lower() in (
            "true",
            "1",
            "yes",
        )
        self.enable_ssm = enable_ssm and AWS_AVAILABLE and not ssm_disabled_by_env
        self.enable_metrics = (
            enable_metrics and AWS_AVAILABLE and not ssm_disabled_by_env
        )

        # Initialize AWS clients
        self.ssm_client = None
        self.cloudwatch_client = None
        self.dynamodb = None

        if AWS_AVAILABLE:
            try:
                region = os.environ.get("AWS_REGION", "us-east-1")
                self.ssm_client = boto3.client("ssm", region_name=region)
                self.cloudwatch_client = boto3.client("cloudwatch", region_name=region)
                self.dynamodb = boto3.resource("dynamodb", region_name=region)
            except Exception as e:
                logger.warning(f"Failed to initialize AWS clients: {e}")
                self.enable_ssm = False
                self.enable_metrics = False

        # Load configuration
        self.models = self._load_model_configs()
        self.rules = self._load_routing_rules()
        self.ab_test = self._load_ab_test_config()

        # Build rule lookup for fast access
        self._rule_lookup: dict[str, RoutingRule] = {
            rule.task_type: rule for rule in self.rules
        }

        # Metrics tracking
        self._routing_stats: dict[str, int] = {tier.value: 0 for tier in ModelTier}
        self._cost_savings_estimate: float = 0.0

        # Historical failure tracking for dynamic complexity scoring
        # Maps task_type to list of (timestamp, success) tuples
        self._task_history: dict[str, list[tuple[float, bool]]] = {}
        self._history_window_seconds = 3600  # 1 hour window for failure rate

        logger.info(
            f"ModelRouter initialized for {self.environment} environment. "
            f"SSM: {self.enable_ssm}, Metrics: {self.enable_metrics}, "
            f"A/B Testing: {self.ab_test.enabled}"
        )

    def _load_model_configs(self) -> dict[ModelTier, ModelConfig]:
        """Load model configurations from SSM or use defaults."""
        if not self.enable_ssm:
            return DEFAULT_MODELS.copy()

        assert self.ssm_client is not None
        try:
            param_name = f"{self.ssm_prefix}/{self.environment}/model-router/models"
            response = self.ssm_client.get_parameter(Name=param_name)
            config_json = json.loads(response["Parameter"]["Value"])

            models = {}
            for tier_name, config in config_json.items():
                tier = ModelTier(tier_name)
                models[tier] = ModelConfig(
                    model_id=config["model_id"],
                    tier=tier,
                    input_cost_per_million=config["input_cost_per_million"],
                    output_cost_per_million=config["output_cost_per_million"],
                    avg_latency_ms=config.get("avg_latency_ms", 500),
                    max_tokens=config.get("max_tokens", 4096),
                )
            logger.info(f"Loaded model configs from SSM: {param_name}")
            return models

        except ClientError as e:
            if e.response["Error"]["Code"] == "ParameterNotFound":
                logger.info("Model config not found in SSM, using defaults")
            else:
                logger.warning(f"Failed to load model configs from SSM: {e}")
            return DEFAULT_MODELS.copy()

    def _load_routing_rules(self) -> list[RoutingRule]:
        """Load routing rules from SSM or use defaults."""
        if not self.enable_ssm:
            return DEFAULT_ROUTING_RULES.copy()

        assert self.ssm_client is not None
        try:
            param_name = f"{self.ssm_prefix}/{self.environment}/model-router/rules"
            response = self.ssm_client.get_parameter(Name=param_name)
            rules_json = json.loads(response["Parameter"]["Value"])

            rules = []
            for rule_data in rules_json:
                rules.append(
                    RoutingRule(
                        task_type=rule_data["task_type"],
                        complexity=TaskComplexity(rule_data["complexity"]),
                        tier=ModelTier(rule_data["tier"]),
                        description=rule_data.get("description", ""),
                        enabled=rule_data.get("enabled", True),
                    )
                )
            logger.info(f"Loaded {len(rules)} routing rules from SSM")
            return rules

        except ClientError as e:
            if e.response["Error"]["Code"] == "ParameterNotFound":
                logger.info("Routing rules not found in SSM, using defaults")
            else:
                logger.warning(f"Failed to load routing rules from SSM: {e}")
            return DEFAULT_ROUTING_RULES.copy()

    def _load_ab_test_config(self) -> ABTestConfig:
        """Load A/B test configuration from SSM."""
        if not self.enable_ssm:
            return ABTestConfig()

        assert self.ssm_client is not None
        try:
            param_name = f"{self.ssm_prefix}/{self.environment}/model-router/ab-test"
            response = self.ssm_client.get_parameter(Name=param_name)
            config_json = json.loads(response["Parameter"]["Value"])

            return ABTestConfig(
                enabled=config_json.get("enabled", False),
                experiment_id=config_json.get("experiment_id", ""),
                control_tier=ModelTier(config_json.get("control_tier", "accurate")),
                treatment_tier=ModelTier(config_json.get("treatment_tier", "fast")),
                traffic_split=config_json.get("traffic_split", 0.5),
                task_types=config_json.get("task_types", []),
            )

        except ClientError as e:
            if e.response["Error"]["Code"] == "ParameterNotFound":
                logger.debug("A/B test config not found in SSM")
            else:
                logger.warning(f"Failed to load A/B test config: {e}")
            return ABTestConfig()

    def route(
        self,
        task_type: str,
        context: dict[str, Any] | None = None,
        override_tier: ModelTier | None = None,
    ) -> RoutingDecision:
        """
        Route a task to the appropriate model tier.

        Args:
            task_type: Type of task (e.g., "patch_generation", "query_intent_analysis")
            context: Additional context for routing decisions
            override_tier: Force a specific tier (bypasses routing logic)

        Returns:
            RoutingDecision with model selection details
        """
        start_time = time.time()
        context = context or {}

        # Handle override
        if override_tier is not None:
            model = self.models[override_tier]
            decision = RoutingDecision(
                model_id=model.model_id,
                tier=override_tier,
                complexity=self._infer_complexity(override_tier),
                rule_matched="override",
                estimated_cost_per_1k_tokens=self._estimate_cost_per_1k(model),
                decision_time_ms=(time.time() - start_time) * 1000,
            )
            self._record_routing_decision(decision, task_type)
            return decision

        # Check A/B test
        ab_variant = None
        if self._should_apply_ab_test(task_type):
            ab_variant = self._get_ab_variant(task_type, context)
            tier = (
                self.ab_test.treatment_tier
                if ab_variant == "treatment"
                else self.ab_test.control_tier
            )
            model = self.models[tier]
            decision = RoutingDecision(
                model_id=model.model_id,
                tier=tier,
                complexity=self._infer_complexity(tier),
                rule_matched=f"ab_test:{self.ab_test.experiment_id}",
                is_ab_test=True,
                ab_variant=ab_variant,
                estimated_cost_per_1k_tokens=self._estimate_cost_per_1k(model),
                decision_time_ms=(time.time() - start_time) * 1000,
            )
            self._record_routing_decision(decision, task_type)
            return decision

        # Look up routing rule
        rule = self._rule_lookup.get(task_type)

        if rule and rule.enabled:
            tier = rule.tier
            complexity = rule.complexity
            rule_matched = rule.task_type
        else:
            # Default to ACCURATE tier for unknown tasks (safety)
            tier = ModelTier.ACCURATE
            complexity = TaskComplexity.MEDIUM
            rule_matched = "default"
            logger.debug(
                f"No routing rule for '{task_type}', using default ACCURATE tier"
            )

        model = self.models[tier]
        decision = RoutingDecision(
            model_id=model.model_id,
            tier=tier,
            complexity=complexity,
            rule_matched=rule_matched,
            estimated_cost_per_1k_tokens=self._estimate_cost_per_1k(model),
            decision_time_ms=(time.time() - start_time) * 1000,
        )

        self._record_routing_decision(decision, task_type)
        return decision

    def route_with_complexity(
        self,
        task_type: str,
        input_text: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> RoutingDecision:
        """
        Route a task using dynamic complexity scoring.

        Considers multiple factors to determine optimal model tier:
        - Input token count (longer inputs may need more capable models)
        - Code complexity (cyclomatic complexity if available)
        - Historical failure rate (tasks that fail often get upgraded)

        Args:
            task_type: Type of task (e.g., "patch_generation")
            input_text: Input text for token counting
            context: Additional context including:
                - code_complexity: Cyclomatic complexity score
                - request_id: For consistent A/B testing
                - force_upgrade: Skip to higher tier

        Returns:
            RoutingDecision with dynamic complexity-based selection
        """
        start_time = time.time()
        context = context or {}

        # Calculate dynamic complexity score
        complexity_score = self._score_complexity(task_type, input_text, context)

        # Determine tier based on complexity score
        tier = complexity_score.recommended_tier
        model = self.models[tier]

        decision = RoutingDecision(
            model_id=model.model_id,
            tier=tier,
            complexity=self._infer_complexity(tier),
            rule_matched=f"dynamic_complexity:{complexity_score.overall_score:.2f}",
            estimated_cost_per_1k_tokens=self._estimate_cost_per_1k(model),
            decision_time_ms=(time.time() - start_time) * 1000,
        )

        self._record_routing_decision(decision, task_type)
        return decision

    def _score_complexity(
        self,
        task_type: str,
        input_text: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ComplexityScore:
        """
        Calculate dynamic complexity score for routing decision.

        Combines three factors:
        1. Input token score (0-1): Based on input text length
        2. Code complexity score (0-1): Based on cyclomatic complexity
        3. Historical failure score (0-1): Based on recent failure rate

        Args:
            task_type: Type of task
            input_text: Input text for token estimation
            context: Additional context with code_complexity

        Returns:
            ComplexityScore with breakdown and recommended tier
        """
        context = context or {}

        # 1. Input token score
        input_token_score = 0.0
        estimated_tokens = 0
        if input_text:
            # Approximate: 1 token ~= 4 characters
            estimated_tokens = len(input_text) // 4
            if estimated_tokens < self.INPUT_TOKEN_THRESHOLD_SIMPLE:
                input_token_score = 0.0
            elif estimated_tokens > self.INPUT_TOKEN_THRESHOLD_COMPLEX:
                input_token_score = 1.0
            else:
                # Linear interpolation between thresholds
                input_token_score = (
                    estimated_tokens - self.INPUT_TOKEN_THRESHOLD_SIMPLE
                ) / (
                    self.INPUT_TOKEN_THRESHOLD_COMPLEX
                    - self.INPUT_TOKEN_THRESHOLD_SIMPLE
                )

        # 2. Code complexity score
        code_complexity_score = 0.0
        code_complexity = context.get("code_complexity", 0)
        if code_complexity:
            if code_complexity < self.CODE_COMPLEXITY_THRESHOLD_SIMPLE:
                code_complexity_score = 0.0
            elif code_complexity > self.CODE_COMPLEXITY_THRESHOLD_COMPLEX:
                code_complexity_score = 1.0
            else:
                code_complexity_score = (
                    code_complexity - self.CODE_COMPLEXITY_THRESHOLD_SIMPLE
                ) / (
                    self.CODE_COMPLEXITY_THRESHOLD_COMPLEX
                    - self.CODE_COMPLEXITY_THRESHOLD_SIMPLE
                )

        # 3. Historical failure score
        historical_failure_score = self._get_historical_failure_rate(task_type)

        # Weighted combination (tokens: 30%, complexity: 40%, history: 30%)
        overall_score = (
            0.30 * input_token_score
            + 0.40 * code_complexity_score
            + 0.30 * historical_failure_score
        )

        # Determine recommended tier based on overall score
        if overall_score < 0.33:
            recommended_tier = ModelTier.FAST
        elif overall_score < 0.66:
            recommended_tier = ModelTier.ACCURATE
        else:
            recommended_tier = ModelTier.MAXIMUM

        # Force upgrade if requested
        if context.get("force_upgrade"):
            if recommended_tier == ModelTier.FAST:
                recommended_tier = ModelTier.ACCURATE
            elif recommended_tier == ModelTier.ACCURATE:
                recommended_tier = ModelTier.MAXIMUM

        return ComplexityScore(
            overall_score=overall_score,
            input_token_score=input_token_score,
            code_complexity_score=code_complexity_score,
            historical_failure_score=historical_failure_score,
            recommended_tier=recommended_tier,
            scoring_details={
                "estimated_tokens": estimated_tokens,
                "code_complexity": code_complexity,
                "failure_rate": historical_failure_score,
                "weights": {
                    "input_tokens": 0.30,
                    "code_complexity": 0.40,
                    "historical": 0.30,
                },
            },
        )

    def _get_historical_failure_rate(self, task_type: str) -> float:
        """
        Get historical failure rate for a task type.

        Uses a sliding window to calculate recent failure rate.

        Args:
            task_type: Task type to check

        Returns:
            Failure rate (0.0 to 1.0)
        """
        if task_type not in self._task_history:
            return 0.0

        now = time.time()
        window_start = now - self._history_window_seconds

        # Filter to recent history
        recent = [
            (ts, success)
            for ts, success in self._task_history[task_type]
            if ts > window_start
        ]

        if not recent:
            return 0.0

        # Calculate failure rate
        failures = sum(1 for _, success in recent if not success)
        return failures / len(recent)

    def record_task_outcome(self, task_type: str, success: bool) -> None:
        """
        Record task outcome for historical failure tracking.

        Call this after task completion to update failure rate tracking.

        Args:
            task_type: Task type that was executed
            success: Whether the task succeeded
        """
        now = time.time()

        if task_type not in self._task_history:
            self._task_history[task_type] = []

        self._task_history[task_type].append((now, success))

        # Prune old entries (keep last 1000 per task type)
        if len(self._task_history[task_type]) > 1000:
            self._task_history[task_type] = self._task_history[task_type][-1000:]

        logger.debug(
            f"Recorded {task_type} outcome: {'success' if success else 'failure'}"
        )

    def _should_apply_ab_test(self, task_type: str) -> bool:
        """Check if A/B test should apply to this task."""
        if not self.ab_test.enabled:
            return False
        if self.ab_test.task_types and task_type not in self.ab_test.task_types:
            return False
        return True

    def _get_ab_variant(self, task_type: str, context: dict[str, Any]) -> str:
        """Determine A/B test variant (control or treatment)."""
        # Use consistent hashing for deterministic assignment
        # This ensures same request always gets same variant
        hash_input = (
            f"{task_type}:{context.get('request_id', '')}:{self.ab_test.experiment_id}"
        )
        hash_value = (
            int(hashlib.md5(hash_input.encode(), usedforsecurity=False).hexdigest(), 16)
            % 100
        )

        if hash_value < self.ab_test.traffic_split * 100:
            return "treatment"
        return "control"

    def _infer_complexity(self, tier: ModelTier) -> TaskComplexity:
        """Infer task complexity from tier."""
        mapping = {
            ModelTier.FAST: TaskComplexity.SIMPLE,
            ModelTier.ACCURATE: TaskComplexity.MEDIUM,
            ModelTier.MAXIMUM: TaskComplexity.COMPLEX,
        }
        return mapping.get(tier, TaskComplexity.MEDIUM)

    def _estimate_cost_per_1k(self, model: ModelConfig) -> float:
        """Estimate cost per 1K tokens (assuming 50/50 input/output split)."""
        # Average of input and output costs
        avg_cost = (model.input_cost_per_million + model.output_cost_per_million) / 2
        return avg_cost / 1000  # Convert to per-1K

    def _record_routing_decision(
        self, decision: RoutingDecision, task_type: str
    ) -> None:
        """Record routing decision for metrics."""
        # Update local stats
        self._routing_stats[decision.tier.value] += 1

        # Calculate cost savings vs always using ACCURATE tier
        accurate_cost = self._estimate_cost_per_1k(self.models[ModelTier.ACCURATE])
        if decision.tier == ModelTier.FAST:
            self._cost_savings_estimate += (
                accurate_cost - decision.estimated_cost_per_1k_tokens
            )

        # Send CloudWatch metrics
        if self.enable_metrics:
            self._send_cloudwatch_metrics(decision, task_type)

    def _send_cloudwatch_metrics(
        self, decision: RoutingDecision, task_type: str
    ) -> None:
        """Send routing metrics to CloudWatch."""
        try:
            metrics = [
                {
                    "MetricName": "RoutingDecisions",
                    "Value": 1,
                    "Unit": "Count",
                    "Dimensions": [
                        {"Name": "Tier", "Value": decision.tier.value},
                        {"Name": "Environment", "Value": self.environment},
                    ],
                },
                {
                    "MetricName": "RoutingDecisionLatency",
                    "Value": decision.decision_time_ms,
                    "Unit": "Milliseconds",
                    "Dimensions": [
                        {"Name": "Environment", "Value": self.environment},
                    ],
                },
            ]

            # A/B test metrics
            if decision.is_ab_test:
                metrics.append(
                    {
                        "MetricName": "ABTestDecisions",
                        "Value": 1,
                        "Unit": "Count",
                        "Dimensions": [
                            {
                                "Name": "ExperimentId",
                                "Value": self.ab_test.experiment_id,
                            },
                            {
                                "Name": "Variant",
                                "Value": decision.ab_variant or "unknown",
                            },
                            {"Name": "Environment", "Value": self.environment},
                        ],
                    }
                )

            if self.cloudwatch_client is not None:
                self.cloudwatch_client.put_metric_data(
                    Namespace="Aura/ModelRouter", MetricData=metrics
                )

        except Exception as e:
            logger.warning(f"Failed to send CloudWatch metrics: {e}")

    def get_model_for_tier(self, tier: ModelTier) -> ModelConfig:
        """Get model configuration for a specific tier."""
        return self.models[tier]

    def get_routing_rules(self) -> list[RoutingRule]:
        """Get all routing rules."""
        return self.rules.copy()

    def get_ab_test_config(self) -> ABTestConfig:
        """Get current A/B test configuration."""
        return self.ab_test

    def get_stats(self) -> dict[str, Any]:
        """Get routing statistics."""
        total = sum(self._routing_stats.values())
        distribution = {}
        if total > 0:
            distribution = {
                tier: count / total * 100 for tier, count in self._routing_stats.items()
            }

        return {
            "total_decisions": total,
            "tier_counts": self._routing_stats.copy(),
            "tier_distribution_percent": distribution,
            "estimated_cost_savings_usd": self._cost_savings_estimate,
            "ab_test_enabled": self.ab_test.enabled,
            "ab_test_experiment_id": (
                self.ab_test.experiment_id if self.ab_test.enabled else None
            ),
        }

    def estimate_savings(self, task_distribution: dict[str, int]) -> dict[str, Any]:
        """
        Estimate cost savings for a given task distribution.

        Args:
            task_distribution: Dict mapping task_type to expected call count

        Returns:
            Savings estimate with baseline and optimized costs
        """
        baseline_cost = 0.0  # All ACCURATE
        optimized_cost = 0.0  # With routing

        accurate_model = self.models[ModelTier.ACCURATE]
        accurate_cost_per_1k = self._estimate_cost_per_1k(accurate_model)

        for task_type, count in task_distribution.items():
            # Baseline: everything uses ACCURATE
            baseline_cost += count * accurate_cost_per_1k

            # Optimized: use routing
            decision = self.route(task_type)
            optimized_cost += count * decision.estimated_cost_per_1k_tokens

        savings = baseline_cost - optimized_cost
        savings_percent = (savings / baseline_cost * 100) if baseline_cost > 0 else 0

        return {
            "baseline_cost_per_1k_calls": baseline_cost,
            "optimized_cost_per_1k_calls": optimized_cost,
            "savings_per_1k_calls": savings,
            "savings_percent": savings_percent,
            "task_count": sum(task_distribution.values()),
        }

    def reload_config(self) -> None:
        """Reload configuration from SSM Parameter Store."""
        logger.info("Reloading Model Router configuration from SSM...")
        self.models = self._load_model_configs()
        self.rules = self._load_routing_rules()
        self.ab_test = self._load_ab_test_config()
        self._rule_lookup = {rule.task_type: rule for rule in self.rules}
        logger.info("Model Router configuration reloaded")


# Module-level convenience functions
_default_router: ModelRouter | None = None


def get_router() -> ModelRouter:
    """Get or create the default ModelRouter instance."""
    global _default_router
    if _default_router is None:
        _default_router = ModelRouter()
    return _default_router


def route(task_type: str, context: dict[str, Any] | None = None) -> RoutingDecision:
    """Route a task using the default router."""
    return get_router().route(task_type, context)


if __name__ == "__main__":
    # Demo/test usage
    logging.basicConfig(level=logging.INFO)

    print("Project Aura - Model Router Demo")
    print("=" * 60)

    router = ModelRouter(enable_ssm=False, enable_metrics=False)

    print("\nModel Configurations:")
    for tier, model in router.models.items():
        print(f"  {tier.value}: {model.model_id.split('.')[-1]}")
        print(
            f"    Cost: ${model.input_cost_per_million:.2f}/$M in, ${model.output_cost_per_million:.2f}/$M out"
        )

    print("\n" + "-" * 60)
    print("Routing Examples:")

    test_tasks = [
        "query_intent_analysis",  # Should be FAST
        "patch_generation",  # Should be ACCURATE
        "cross_codebase_correlation",  # Should be MAXIMUM
        "unknown_task",  # Should default to ACCURATE
    ]

    for task in test_tasks:
        decision = router.route(task)
        print(f"\n  Task: {task}")
        print(f"    Tier: {decision.tier.value}")
        print(f"    Model: {decision.model_id.split('.')[-1]}")
        print(f"    Complexity: {decision.complexity.value}")
        print(f"    Est. Cost: ${decision.estimated_cost_per_1k_tokens:.4f}/1K tokens")

    print("\n" + "-" * 60)
    print("Cost Savings Estimate:")

    # Simulate typical task distribution
    task_dist = {
        "query_intent_analysis": 400,  # 40% simple
        "query_expansion": 100,
        "patch_generation": 300,  # 55% medium
        "code_review": 150,
        "threat_assessment": 50,
        "cross_codebase_correlation": 30,  # 5% complex
        "novel_threat_detection": 20,
    }

    savings = router.estimate_savings(task_dist)
    print(f"\n  For {savings['task_count']} calls:")
    print(f"    Baseline (all ACCURATE): ${savings['baseline_cost_per_1k_calls']:.2f}")
    print(f"    With Routing: ${savings['optimized_cost_per_1k_calls']:.2f}")
    print(
        f"    Savings: ${savings['savings_per_1k_calls']:.2f} ({savings['savings_percent']:.1f}%)"
    )

    print("\n" + "-" * 60)
    stats = router.get_stats()
    print("Routing Stats:")
    print(f"  Total Decisions: {stats['total_decisions']}")
    print(f"  Tier Distribution: {stats['tier_distribution_percent']}")

    print("\n" + "=" * 60)
    print("Demo complete!")

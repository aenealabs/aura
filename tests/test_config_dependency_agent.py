"""Tests for ADR-090 Phase 5.1 ConfigDependencyAgent."""

from __future__ import annotations

import textwrap

import pytest

from src.agents.ast_parser_agent import CodeEntity
from src.services.graph.config_dependency_agent import (
    EDGE_DEFAULT_SENSITIVITY,
    SENSITIVITY_CONFIDENTIAL,
    SENSITIVITY_RESTRICTED,
    VERTEX_CONFIG_PARAMETER,
    VERTEX_FEATURE_FLAG,
    VERTEX_KMS_ALIAS,
    ConfigDependencyAgent,
    ConfigScanStats,
)
from src.services.graph.edge_labels import EdgeLabel


def _entity(name, kind, file_path, line=1, parent_chain=()):
    return CodeEntity(
        name=name,
        entity_type=kind,
        file_path=file_path,
        line_number=line,
        parent_chain=parent_chain,
        parent_entity=parent_chain[-1] if parent_chain else None,
    )


@pytest.fixture
def agent() -> ConfigDependencyAgent:
    return ConfigDependencyAgent()


def _of_kind(rels, label):
    return [r for r in rels if r.relationship == label]


# -- Env var detection --------------------------------------------------


class TestEnvVarPython:
    def test_environ_get(self, agent):
        sources = {"x.py": textwrap.dedent("""
                import os
                def main():
                    return os.environ.get("DATABASE_URL")
                """)}
        rels, stats = agent.scan_repo([], sources)
        env = _of_kind(rels, EdgeLabel.DEPENDS_ON_ENV.value)
        assert len(env) == 1
        assert env[0].target_name == "DATABASE_URL"
        assert env[0].properties["sensitivity"] == SENSITIVITY_CONFIDENTIAL
        assert env[0].properties["vertex_label"] == VERTEX_CONFIG_PARAMETER
        assert env[0].properties["kind"] == "env"
        assert stats.env_vars_emitted == 1

    def test_environ_subscript(self, agent):
        sources = {"x.py": 'import os\nx = os.environ["API_KEY"]\n'}
        rels, _ = agent.scan_repo([], sources)
        env = _of_kind(rels, EdgeLabel.DEPENDS_ON_ENV.value)
        assert len(env) == 1
        assert env[0].target_name == "API_KEY"

    def test_getenv(self, agent):
        sources = {"x.py": "import os\nx = os.getenv('LOG_LEVEL')\n"}
        rels, _ = agent.scan_repo([], sources)
        env = _of_kind(rels, EdgeLabel.DEPENDS_ON_ENV.value)
        assert len(env) == 1
        assert env[0].target_name == "LOG_LEVEL"

    def test_lowercase_env_var_not_matched(self, agent):
        # Tighter regex: only SCREAMING_SNAKE_CASE env names match.
        # Lowercase usually indicates a config dict or dataclass field,
        # not an env reference.
        sources = {"x.py": "x = os.environ.get('lowercase_thing')\n"}
        rels, _ = agent.scan_repo([], sources)
        assert _of_kind(rels, EdgeLabel.DEPENDS_ON_ENV.value) == []


class TestEnvVarJavaScript:
    def test_process_env_dot_access(self, agent):
        sources = {"x.js": "const url = process.env.DATABASE_URL;\n"}
        rels, _ = agent.scan_repo([], sources)
        env = _of_kind(rels, EdgeLabel.DEPENDS_ON_ENV.value)
        assert len(env) == 1
        assert env[0].target_name == "DATABASE_URL"
        assert env[0].properties["language"] == "javascript"

    def test_process_env_subscript(self, agent):
        sources = {"x.ts": 'const k = process.env["API_KEY"];\n'}
        rels, _ = agent.scan_repo([], sources)
        env = _of_kind(rels, EdgeLabel.DEPENDS_ON_ENV.value)
        assert len(env) == 1
        assert env[0].target_name == "API_KEY"


# -- SSM parameter detection -------------------------------------------


class TestSSMParameters:
    def test_get_parameter_name_kwarg(self, agent):
        sources = {"x.py": textwrap.dedent("""
                import boto3
                def fetch():
                    return ssm.get_parameter(Name='/myapp/db/password')
                """)}
        rels, stats = agent.scan_repo([], sources)
        ssm = _of_kind(rels, EdgeLabel.READS_CONFIG.value)
        assert len(ssm) == 1
        assert ssm[0].target_name == "/myapp/db/password"
        assert ssm[0].properties["sensitivity"] == SENSITIVITY_RESTRICTED
        assert ssm[0].properties["vertex_label"] == VERTEX_CONFIG_PARAMETER
        assert ssm[0].properties["kind"] == "ssm"
        assert stats.ssm_params_emitted == 1

    def test_get_parameters_plural(self, agent):
        sources = {
            "x.py": (
                "ssm_client.get_parameters(Names=['/foo', '/bar'], "
                "WithDecryption=True)"
            )
        }
        rels, _ = agent.scan_repo([], sources)
        # The first regex matches the first Name= keyword arg; this
        # test just asserts at least one is emitted (precision over
        # exhaustive count is the deterministic-stage contract).
        ssm = _of_kind(rels, EdgeLabel.READS_CONFIG.value)
        assert len(ssm) >= 1


# -- KMS aliases / ARNs ------------------------------------------------


class TestKMSAliases:
    def test_alias_string(self, agent):
        sources = {"x.py": "kms.decrypt(KeyId='alias/myapp-encryption')"}
        rels, stats = agent.scan_repo([], sources)
        kms = _of_kind(rels, EdgeLabel.USES_KMS_KEY.value)
        assert len(kms) == 1
        assert kms[0].target_name == "alias/myapp-encryption"
        assert kms[0].properties["sensitivity"] == SENSITIVITY_RESTRICTED
        assert kms[0].properties["vertex_label"] == VERTEX_KMS_ALIAS
        assert stats.kms_aliases_emitted == 1

    def test_arn_string(self, agent):
        arn = "arn:aws:kms:us-east-1:123456789012:key/abc12345-1234-1234-1234-123456789012"
        sources = {"x.py": f"kms.decrypt(KeyId='{arn}')"}
        rels, _ = agent.scan_repo([], sources)
        kms = _of_kind(rels, EdgeLabel.USES_KMS_KEY.value)
        assert len(kms) == 1
        assert kms[0].target_name == arn

    def test_arn_alias(self, agent):
        arn = "arn:aws:kms:us-west-2:123456789012:alias/myapp-encryption"
        sources = {"x.py": f"client.encrypt(KeyId='{arn}')"}
        rels, _ = agent.scan_repo([], sources)
        kms = _of_kind(rels, EdgeLabel.USES_KMS_KEY.value)
        assert any(r.target_name == arn for r in kms)


# -- Feature flags -----------------------------------------------------


class TestFeatureFlags:
    def test_launchdarkly_variation(self, agent):
        sources = {
            "x.py": ('enabled = ldclient.variation("new-checkout", user, False)')
        }
        rels, stats = agent.scan_repo([], sources)
        ff = _of_kind(rels, EdgeLabel.FEATURE_GATED_BY.value)
        assert len(ff) == 1
        assert ff[0].target_name == "new-checkout"
        assert ff[0].properties["sensitivity"] == SENSITIVITY_CONFIDENTIAL
        assert ff[0].properties["vertex_label"] == VERTEX_FEATURE_FLAG
        assert stats.feature_flags_emitted == 1

    def test_generic_helpers(self, agent):
        sources = {"x.py": textwrap.dedent("""
                def go():
                    if feature_flag("flag-a"):
                        pass
                    if isEnabled("flag-b"):
                        pass
                """)}
        rels, _ = agent.scan_repo([], sources)
        ff = _of_kind(rels, EdgeLabel.FEATURE_GATED_BY.value)
        names = {r.target_name for r in ff}
        assert names == {"flag-a", "flag-b"}

    def test_javascript_ldclient(self, agent):
        sources = {
            "app.tsx": (
                'const enabled = ldClient.boolVariation("checkout-v2", ' "user, false);"
            )
        }
        rels, _ = agent.scan_repo([], sources)
        ff = _of_kind(rels, EdgeLabel.FEATURE_GATED_BY.value)
        assert len(ff) == 1
        assert ff[0].target_name == "checkout-v2"


# -- Source attribution ------------------------------------------------


class TestSourceAttribution:
    def test_attributes_to_enclosing_function(self, agent):
        sources = {"x.py": textwrap.dedent("""\
                import os

                def setup():
                    pass

                def fetch_config():
                    return os.environ.get("MY_VAR")
                """)}
        entities = [
            _entity("setup", "function", "x.py", line=3),
            _entity("fetch_config", "function", "x.py", line=6),
        ]
        rels, _ = agent.scan_repo(entities, sources)
        env = _of_kind(rels, EdgeLabel.DEPENDS_ON_ENV.value)
        assert len(env) == 1
        assert env[0].source_name == "fetch_config"

    def test_attributes_to_enclosing_method_with_parent_chain(self, agent):
        sources = {"x.py": textwrap.dedent("""\
                import os

                class Reader:
                    def load(self):
                        return os.environ["DB_URL"]
                """)}
        entities = [
            _entity("Reader", "class", "x.py", line=3),
            _entity("load", "method", "x.py", line=4, parent_chain=("Reader",)),
        ]
        rels, _ = agent.scan_repo(entities, sources)
        env = _of_kind(rels, EdgeLabel.DEPENDS_ON_ENV.value)
        assert env[0].source_name == "load"
        assert env[0].source_parent_chain == ("Reader",)

    def test_module_scope_falls_back_to_filename_stem(self, agent):
        # No enclosing function -> source_name is the file stem.
        sources = {"settings.py": 'import os\nDB_URL = os.environ["DATABASE_URL"]\n'}
        rels, _ = agent.scan_repo([], sources)
        env = _of_kind(rels, EdgeLabel.DEPENDS_ON_ENV.value)
        assert env[0].source_name == "settings"
        assert env[0].source_parent_chain == ()


# -- Sensitivity contract ----------------------------------------------


class TestSensitivityTiering:
    def test_all_four_edge_types_have_default_sensitivity(self):
        """Sally's tiering: KMS+READS_CONFIG=RESTRICTED, ENV+FLAG=CONFIDENTIAL."""
        assert (
            EDGE_DEFAULT_SENSITIVITY[EdgeLabel.USES_KMS_KEY.value]
            == SENSITIVITY_RESTRICTED
        )
        assert (
            EDGE_DEFAULT_SENSITIVITY[EdgeLabel.READS_CONFIG.value]
            == SENSITIVITY_RESTRICTED
        )
        assert (
            EDGE_DEFAULT_SENSITIVITY[EdgeLabel.DEPENDS_ON_ENV.value]
            == SENSITIVITY_CONFIDENTIAL
        )
        assert (
            EDGE_DEFAULT_SENSITIVITY[EdgeLabel.FEATURE_GATED_BY.value]
            == SENSITIVITY_CONFIDENTIAL
        )


# -- Telemetry ---------------------------------------------------------


class TestStats:
    def test_stats_count_per_edge_type(self, agent):
        sources = {"x.py": textwrap.dedent("""\
                import os
                def f():
                    a = os.environ["A"]
                    b = os.environ["B"]
                    c = ssm.get_parameter(Name='/p/c')
                    d = kms.decrypt(KeyId='alias/d')
                    e = ldclient.variation("flag-e", user, False)
                """)}
        rels, stats = agent.scan_repo([], sources)
        assert stats.env_vars_emitted == 2
        assert stats.ssm_params_emitted == 1
        assert stats.kms_aliases_emitted == 1
        assert stats.feature_flags_emitted == 1
        assert stats.files_scanned == 1

    def test_unsupported_extension_is_silent_skip(self, agent):
        sources = {"data.yaml": "DATABASE_URL: ${env:DATABASE_URL}\n"}
        rels, stats = agent.scan_repo([], sources)
        assert rels == []
        # files_scanned still counts the attempt; no relationships emitted.
        assert stats.files_scanned == 1


class TestDefaults:
    def test_stats_dataclass_zero_init(self):
        stats = ConfigScanStats()
        assert stats.files_scanned == 0
        assert stats.env_vars_emitted == 0
        assert stats.ssm_params_emitted == 0
        assert stats.kms_aliases_emitted == 0
        assert stats.feature_flags_emitted == 0
        assert stats.files_skipped == 0

"""Tests for MIRAS configuration module."""

import pytest

torch = pytest.importorskip("torch", reason="PyTorch required for neural memory tests")

from src.services.models import (
    AttentionalBias,
    MemoryAlgorithm,
    MIRASConfig,
    MIRASLossFunctions,
    MIRASOptimizer,
    MIRASRetention,
    RetentionGate,
    get_miras_preset,
)
from src.services.models.deep_mlp_memory import DeepMLPMemory, MemoryConfig


class TestAttentionalBias:
    """Tests for AttentionalBias enum."""

    def test_enum_values(self):
        """Test enum values are correct."""
        assert AttentionalBias.L2.value == "l2"
        assert AttentionalBias.L1.value == "l1"
        assert AttentionalBias.HUBER.value == "huber"
        assert AttentionalBias.COSINE.value == "cosine"


class TestRetentionGate:
    """Tests for RetentionGate enum."""

    def test_enum_values(self):
        """Test enum values are correct."""
        assert RetentionGate.WEIGHT_DECAY.value == "weight_decay"
        assert RetentionGate.EXPONENTIAL.value == "exponential"
        assert RetentionGate.ADAPTIVE.value == "adaptive"
        assert RetentionGate.NONE.value == "none"


class TestMemoryAlgorithm:
    """Tests for MemoryAlgorithm enum."""

    def test_enum_values(self):
        """Test enum values are correct."""
        assert MemoryAlgorithm.SGD.value == "sgd"
        assert MemoryAlgorithm.MOMENTUM.value == "momentum"
        assert MemoryAlgorithm.ADAM.value == "adam"
        assert MemoryAlgorithm.ADALR.value == "adalr"


class TestMIRASConfig:
    """Tests for MIRASConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = MIRASConfig()
        assert config.attentional_bias == AttentionalBias.HUBER
        assert config.retention_gate == RetentionGate.ADAPTIVE
        assert config.memory_algorithm == MemoryAlgorithm.ADAM
        assert config.huber_delta == 1.0
        assert config.retention_strength == 0.01
        assert config.momentum == 0.9
        assert config.gradient_clip == 1.0

    def test_custom_config(self):
        """Test custom configuration values."""
        config = MIRASConfig(
            attentional_bias=AttentionalBias.L2,
            retention_gate=RetentionGate.WEIGHT_DECAY,
            memory_algorithm=MemoryAlgorithm.SGD,
            retention_strength=0.05,
            gradient_clip=2.0,
        )
        assert config.attentional_bias == AttentionalBias.L2
        assert config.retention_gate == RetentionGate.WEIGHT_DECAY
        assert config.memory_algorithm == MemoryAlgorithm.SGD
        assert config.retention_strength == 0.05
        assert config.gradient_clip == 2.0

    def test_to_dict(self):
        """Test config serialization to dict."""
        config = MIRASConfig()
        data = config.to_dict()

        assert data["attentional_bias"] == "huber"
        assert data["retention_gate"] == "adaptive"
        assert data["memory_algorithm"] == "adam"
        assert isinstance(data["extra_config"], dict)

    def test_from_dict(self):
        """Test config deserialization from dict."""
        data = {
            "attentional_bias": "l2",
            "retention_gate": "weight_decay",
            "memory_algorithm": "sgd",
            "retention_strength": 0.02,
        }
        config = MIRASConfig.from_dict(data)

        assert config.attentional_bias == AttentionalBias.L2
        assert config.retention_gate == RetentionGate.WEIGHT_DECAY
        assert config.memory_algorithm == MemoryAlgorithm.SGD
        assert config.retention_strength == 0.02


class TestMIRASLossFunctions:
    """Tests for MIRAS loss functions."""

    @pytest.fixture
    def predictions_targets(self):
        """Create prediction and target tensors."""
        pred = torch.randn(4, 256)
        target = torch.randn(4, 256)
        return pred, target

    def test_l2_loss(self, predictions_targets):
        """Test L2 loss computation."""
        pred, target = predictions_targets
        loss = MIRASLossFunctions.l2_loss(pred, target)

        assert loss.shape == ()
        assert loss.item() >= 0

    def test_l1_loss(self, predictions_targets):
        """Test L1 loss computation."""
        pred, target = predictions_targets
        loss = MIRASLossFunctions.l1_loss(pred, target)

        assert loss.shape == ()
        assert loss.item() >= 0

    def test_huber_loss(self, predictions_targets):
        """Test Huber loss computation."""
        pred, target = predictions_targets
        loss = MIRASLossFunctions.huber_loss(pred, target, delta=1.0)

        assert loss.shape == ()
        assert loss.item() >= 0

    def test_huber_loss_delta(self, predictions_targets):
        """Test Huber loss with different delta values."""
        pred, target = predictions_targets

        loss_small_delta = MIRASLossFunctions.huber_loss(pred, target, delta=0.1)
        loss_large_delta = MIRASLossFunctions.huber_loss(pred, target, delta=10.0)

        # Both should be valid losses
        assert loss_small_delta.item() >= 0
        assert loss_large_delta.item() >= 0

    def test_cosine_loss(self, predictions_targets):
        """Test cosine loss computation."""
        pred, target = predictions_targets
        loss = MIRASLossFunctions.cosine_loss(pred, target)

        assert loss.shape == ()
        # Cosine distance is in [0, 2]
        assert 0 <= loss.item() <= 2

    def test_cosine_loss_identical(self):
        """Test cosine loss with identical vectors."""
        pred = torch.randn(4, 256)
        target = pred.clone()
        loss = MIRASLossFunctions.cosine_loss(pred, target)

        # Should be close to 0 for identical vectors
        assert loss.item() < 0.01

    def test_cosine_loss_opposite(self):
        """Test cosine loss with opposite vectors."""
        pred = torch.randn(4, 256)
        target = -pred.clone()
        loss = MIRASLossFunctions.cosine_loss(pred, target)

        # Should be close to 2 for opposite vectors
        assert loss.item() > 1.9

    def test_get_loss_fn_l2(self):
        """Test getting L2 loss function."""
        loss_fn = MIRASLossFunctions.get_loss_fn(AttentionalBias.L2)
        pred = torch.randn(4, 256)
        target = torch.randn(4, 256)
        loss = loss_fn(pred, target)
        assert loss.item() >= 0

    def test_get_loss_fn_huber_with_config(self):
        """Test getting Huber loss with config."""
        config = MIRASConfig(huber_delta=0.5)
        loss_fn = MIRASLossFunctions.get_loss_fn(AttentionalBias.HUBER, config)
        pred = torch.randn(4, 256)
        target = torch.randn(4, 256)
        loss = loss_fn(pred, target)
        assert loss.item() >= 0


class TestMIRASRetention:
    """Tests for MIRAS retention strategies."""

    @pytest.fixture
    def model(self):
        """Create a small model for retention testing."""
        config = MemoryConfig(dim=64, depth=1)
        return DeepMLPMemory(config)

    def test_weight_decay(self, model):
        """Test weight decay regularization."""
        loss = MIRASRetention.weight_decay(model, strength=0.01)
        assert loss.item() > 0

    def test_weight_decay_strength(self, model):
        """Test weight decay with different strengths."""
        loss_weak = MIRASRetention.weight_decay(model, strength=0.001)
        loss_strong = MIRASRetention.weight_decay(model, strength=0.1)

        # Stronger decay should give higher loss
        assert loss_strong.item() > loss_weak.item()

    def test_exponential_decay_zero_age(self, model):
        """Test exponential decay at age 0."""
        loss = MIRASRetention.exponential_decay(model, age=0.0)
        # At age 0, decay factor is 1.0, so adjusted strength is 0
        assert loss.item() >= 0

    def test_exponential_decay_old_age(self, model):
        """Test exponential decay at high age."""
        loss_young = MIRASRetention.exponential_decay(model, age=1.0)
        loss_old = MIRASRetention.exponential_decay(model, age=100.0)

        # Older memories should have higher decay
        assert loss_old.item() >= loss_young.item()

    def test_adaptive_decay_low_utilization(self, model):
        """Test adaptive decay with low utilization."""
        loss = MIRASRetention.adaptive_decay(
            model,
            utilization=0.1,
            base_strength=0.01,
            threshold=0.5,
        )
        assert loss.item() > 0

    def test_adaptive_decay_high_utilization(self, model):
        """Test adaptive decay with high utilization."""
        loss_low = MIRASRetention.adaptive_decay(model, utilization=0.1)
        loss_high = MIRASRetention.adaptive_decay(model, utilization=0.9)

        # High utilization should have lower decay
        assert loss_high.item() < loss_low.item()

    def test_apply_retention_none(self, model):
        """Test applying no retention."""
        config = MIRASConfig(retention_gate=RetentionGate.NONE)
        loss = MIRASRetention.apply_retention(
            model,
            RetentionGate.NONE,
            config,
        )
        assert loss.item() == 0.0

    def test_apply_retention_weight_decay(self, model):
        """Test applying weight decay retention."""
        config = MIRASConfig(retention_gate=RetentionGate.WEIGHT_DECAY)
        loss = MIRASRetention.apply_retention(
            model,
            RetentionGate.WEIGHT_DECAY,
            config,
        )
        assert loss.item() > 0

    def test_apply_retention_adaptive(self, model):
        """Test applying adaptive retention."""
        config = MIRASConfig(retention_gate=RetentionGate.ADAPTIVE)
        loss = MIRASRetention.apply_retention(
            model,
            RetentionGate.ADAPTIVE,
            config,
            utilization=0.5,
        )
        assert loss.item() > 0


class TestMIRASOptimizer:
    """Tests for MIRAS optimizer factory."""

    @pytest.fixture
    def model(self):
        """Create a small model for optimizer testing."""
        config = MemoryConfig(dim=64, depth=1)
        return DeepMLPMemory(config)

    def test_create_sgd(self, model):
        """Test creating SGD optimizer."""
        config = MIRASConfig(memory_algorithm=MemoryAlgorithm.SGD)
        optimizer = MIRASOptimizer.create_optimizer(model, config, learning_rate=0.01)

        assert isinstance(optimizer, torch.optim.SGD)

    def test_create_momentum(self, model):
        """Test creating SGD with momentum optimizer."""
        config = MIRASConfig(memory_algorithm=MemoryAlgorithm.MOMENTUM, momentum=0.95)
        optimizer = MIRASOptimizer.create_optimizer(model, config, learning_rate=0.01)

        assert isinstance(optimizer, torch.optim.SGD)

    def test_create_adam(self, model):
        """Test creating Adam optimizer."""
        config = MIRASConfig(memory_algorithm=MemoryAlgorithm.ADAM)
        optimizer = MIRASOptimizer.create_optimizer(model, config, learning_rate=0.001)

        assert isinstance(optimizer, torch.optim.Adam)

    def test_create_adalr(self, model):
        """Test creating adaptive learning rate optimizer."""
        config = MIRASConfig(memory_algorithm=MemoryAlgorithm.ADALR)
        optimizer = MIRASOptimizer.create_optimizer(model, config, learning_rate=0.001)

        assert isinstance(optimizer, torch.optim.Adam)


class TestMIRASPresets:
    """Tests for MIRAS preset configurations."""

    def test_defense_contractor_preset(self):
        """Test defense contractor preset."""
        config = get_miras_preset("defense_contractor")

        assert config.attentional_bias == AttentionalBias.HUBER
        assert config.retention_gate == RetentionGate.NONE
        assert config.memory_algorithm == MemoryAlgorithm.SGD
        assert config.gradient_clip == 0.5

    def test_enterprise_standard_preset(self):
        """Test enterprise standard preset."""
        config = get_miras_preset("enterprise_standard")

        assert config.attentional_bias == AttentionalBias.HUBER
        assert config.retention_gate == RetentionGate.ADAPTIVE
        assert config.memory_algorithm == MemoryAlgorithm.ADAM

    def test_research_lab_preset(self):
        """Test research lab preset."""
        config = get_miras_preset("research_lab")

        assert config.attentional_bias == AttentionalBias.L2
        assert config.retention_gate == RetentionGate.EXPONENTIAL
        assert config.gradient_clip == 2.0

    def test_development_preset(self):
        """Test development preset."""
        config = get_miras_preset("development")

        assert config.attentional_bias == AttentionalBias.L2
        assert config.retention_gate == RetentionGate.WEIGHT_DECAY
        assert config.memory_algorithm == MemoryAlgorithm.SGD

    def test_invalid_preset(self):
        """Test that invalid preset raises error."""
        with pytest.raises(ValueError, match="Unknown preset"):
            get_miras_preset("invalid_preset")

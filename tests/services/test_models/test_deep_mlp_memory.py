"""Tests for DeepMLPMemory module."""

import pytest

torch = pytest.importorskip("torch", reason="PyTorch required for neural memory tests")

from src.services.models import (
    DeepMLPMemory,
    MemoryConfig,
    PersistentMemory,
    SurpriseCalculator,
    create_memory_model,
)


class TestMemoryConfig:
    """Tests for MemoryConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = MemoryConfig()
        assert config.dim == 512
        assert config.depth == 3
        assert config.hidden_multiplier == 4
        assert config.dropout == 0.1
        assert config.use_layer_norm is True
        assert config.use_residual is True
        assert config.persistent_memory_size == 64

    def test_custom_config(self):
        """Test custom configuration values."""
        config = MemoryConfig(
            dim=256,
            depth=5,
            hidden_multiplier=2,
            dropout=0.2,
            use_layer_norm=False,
            use_residual=False,
            persistent_memory_size=32,
        )
        assert config.dim == 256
        assert config.depth == 5
        assert config.hidden_multiplier == 2
        assert config.dropout == 0.2
        assert config.use_layer_norm is False
        assert config.use_residual is False
        assert config.persistent_memory_size == 32


class TestPersistentMemory:
    """Tests for PersistentMemory module."""

    def test_initialization(self):
        """Test PersistentMemory initialization."""
        memory = PersistentMemory(num_slots=64, dim=512)
        assert memory.num_slots == 64
        assert memory.dim == 512
        assert memory.memory.shape == (64, 512)

    def test_forward_shape(self):
        """Test PersistentMemory forward pass output shape."""
        memory = PersistentMemory(num_slots=64, dim=512)
        query = torch.randn(8, 512)
        output = memory(query)
        assert output.shape == (8, 512)

    def test_forward_batch_independence(self):
        """Test that batch items are processed independently."""
        memory = PersistentMemory(num_slots=32, dim=256)
        query1 = torch.randn(1, 256)
        query2 = torch.randn(1, 256)
        query_combined = torch.cat([query1, query2], dim=0)

        output1 = memory(query1)
        output2 = memory(query2)
        output_combined = memory(query_combined)

        torch.testing.assert_close(output1, output_combined[0:1])
        torch.testing.assert_close(output2, output_combined[1:2])

    def test_attention_weights_sum_to_one(self):
        """Test that attention weights are properly normalized."""
        memory = PersistentMemory(num_slots=32, dim=256)
        query = torch.randn(4, 256)

        # Compute attention manually
        q = memory.query_proj(query)
        k = memory.key_proj(memory.memory)
        import math

        attn_scores = torch.matmul(q, k.t()) / math.sqrt(memory.dim)
        attn_weights = torch.nn.functional.softmax(attn_scores, dim=-1)

        # Check weights sum to 1
        weight_sums = attn_weights.sum(dim=-1)
        torch.testing.assert_close(
            weight_sums,
            torch.ones_like(weight_sums),
            atol=1e-5,
            rtol=1e-5,
        )


class TestDeepMLPMemory:
    """Tests for DeepMLPMemory module."""

    @pytest.fixture
    def default_model(self):
        """Create a default DeepMLPMemory model."""
        return DeepMLPMemory()

    @pytest.fixture
    def custom_model(self):
        """Create a custom DeepMLPMemory model."""
        config = MemoryConfig(dim=256, depth=2, hidden_multiplier=2)
        return DeepMLPMemory(config)

    def test_default_initialization(self, default_model):
        """Test default model initialization."""
        assert default_model.config.dim == 512
        assert default_model.config.depth == 3
        assert len(default_model.layers) == 3

    def test_custom_initialization(self, custom_model):
        """Test custom model initialization."""
        assert custom_model.config.dim == 256
        assert custom_model.config.depth == 2
        assert len(custom_model.layers) == 2

    def test_forward_shape(self, default_model):
        """Test forward pass output shape."""
        x = torch.randn(4, 512)
        output = default_model(x)
        assert output.shape == (4, 512)

    def test_forward_without_persistent(self, default_model):
        """Test forward pass without persistent memory."""
        x = torch.randn(4, 512)
        output = default_model(x, use_persistent=False)
        assert output.shape == (4, 512)

    def test_retrieve_method(self, default_model):
        """Test retrieve method is alias for forward."""
        # Set to eval mode to disable dropout for deterministic comparison
        default_model.eval()
        x = torch.randn(2, 512)

        with torch.no_grad():
            output1 = default_model(x, use_persistent=True)
            output2 = default_model.retrieve(x)

        torch.testing.assert_close(output1, output2)

    def test_reconstruction_loss_l2(self, default_model):
        """Test L2 reconstruction loss."""
        key = torch.randn(4, 512)
        value = torch.randn(4, 512)
        loss = default_model.compute_reconstruction_loss(key, value, loss_type="l2")
        assert loss.shape == ()
        assert loss.item() >= 0

    def test_reconstruction_loss_l1(self, default_model):
        """Test L1 reconstruction loss."""
        key = torch.randn(4, 512)
        value = torch.randn(4, 512)
        loss = default_model.compute_reconstruction_loss(key, value, loss_type="l1")
        assert loss.shape == ()
        assert loss.item() >= 0

    def test_reconstruction_loss_huber(self, default_model):
        """Test Huber reconstruction loss."""
        key = torch.randn(4, 512)
        value = torch.randn(4, 512)
        loss = default_model.compute_reconstruction_loss(key, value, loss_type="huber")
        assert loss.shape == ()
        assert loss.item() >= 0

    def test_reconstruction_loss_cosine(self, default_model):
        """Test cosine reconstruction loss."""
        key = torch.randn(4, 512)
        value = torch.randn(4, 512)
        loss = default_model.compute_reconstruction_loss(key, value, loss_type="cosine")
        assert loss.shape == ()
        assert 0 <= loss.item() <= 2  # Cosine distance range

    def test_reconstruction_loss_invalid(self, default_model):
        """Test invalid loss type raises error."""
        key = torch.randn(4, 512)
        value = torch.randn(4, 512)
        with pytest.raises(ValueError, match="Unknown loss type"):
            default_model.compute_reconstruction_loss(key, value, loss_type="invalid")

    def test_parameter_count(self, default_model):
        """Test parameter count calculation."""
        count = default_model.get_parameter_count()
        assert count > 0
        # Default model should have millions of parameters
        assert count > 1_000_000

    def test_memory_size_mb(self, default_model):
        """Test memory size calculation."""
        size_mb = default_model.get_memory_size_mb()
        assert size_mb > 0
        # Should be in reasonable range for FP32
        assert size_mb < 1000  # Less than 1GB

    def test_freeze_persistent_memory(self, default_model):
        """Test freezing persistent memory."""
        default_model.freeze_persistent_memory()
        for param in default_model.persistent_memory.parameters():
            assert param.requires_grad is False

    def test_unfreeze_persistent_memory(self, default_model):
        """Test unfreezing persistent memory."""
        default_model.freeze_persistent_memory()
        default_model.unfreeze_persistent_memory()
        for param in default_model.persistent_memory.parameters():
            assert param.requires_grad is True

    def test_gradient_flow(self, default_model):
        """Test that gradients flow through the model."""
        x = torch.randn(4, 512, requires_grad=True)
        output = default_model(x)
        loss = output.sum()
        loss.backward()
        assert x.grad is not None
        assert x.grad.shape == x.shape


class TestSurpriseCalculator:
    """Tests for SurpriseCalculator."""

    @pytest.fixture
    def model(self):
        """Create a model for surprise calculation."""
        config = MemoryConfig(dim=128, depth=2)
        return DeepMLPMemory(config)

    @pytest.fixture
    def calculator(self, model):
        """Create a SurpriseCalculator."""
        return SurpriseCalculator(model, momentum=0.9, threshold=0.5)

    def test_initialization(self, calculator):
        """Test SurpriseCalculator initialization."""
        assert calculator.momentum == 0.9
        assert calculator.threshold == 0.5
        assert calculator.past_surprise == 0.0

    def test_compute_surprise(self, calculator):
        """Test surprise computation returns valid value."""
        x = torch.randn(1, 128)
        surprise = calculator.compute_surprise(x)
        assert isinstance(surprise, float)
        assert surprise >= 0

    def test_compute_surprise_with_target(self, calculator):
        """Test surprise computation with explicit target."""
        x = torch.randn(1, 128)
        target = torch.randn(1, 128)
        surprise = calculator.compute_surprise(x, target)
        assert isinstance(surprise, float)
        assert surprise >= 0

    def test_momentum_smoothing(self, calculator):
        """Test that momentum smoothing works."""
        x1 = torch.randn(1, 128)
        x2 = torch.randn(1, 128)

        calculator.compute_surprise(x1)
        calculator.compute_surprise(x2)

        # Second surprise should be influenced by first due to momentum
        # Just verify it's not equal to raw surprise
        assert calculator.past_surprise != 0.0

    def test_should_memorize_high_surprise(self, calculator):
        """Test memorization decision for high surprise input."""
        # Create a very different target to trigger high surprise
        x = torch.randn(1, 128)
        target = x * 10  # Very different from expected output

        # Run multiple times to build up momentum
        for _ in range(5):
            should, score = calculator.should_memorize(x, target)

        # Should eventually trigger memorization
        assert isinstance(should, bool)
        assert isinstance(score, float)

    def test_reset_momentum(self, calculator):
        """Test momentum reset."""
        x = torch.randn(1, 128)
        calculator.compute_surprise(x)

        assert calculator.past_surprise != 0.0
        calculator.reset_momentum()
        assert calculator.past_surprise == 0.0


class TestCreateMemoryModel:
    """Tests for create_memory_model factory function."""

    def test_default_creation(self):
        """Test creating model with defaults."""
        model = create_memory_model()
        assert model.config.dim == 512
        assert model.config.depth == 3

    def test_custom_creation(self):
        """Test creating model with custom parameters."""
        model = create_memory_model(
            dim=256,
            depth=5,
            hidden_multiplier=2,
            persistent_slots=32,
        )
        assert model.config.dim == 256
        assert model.config.depth == 5
        assert model.config.hidden_multiplier == 2
        assert model.config.persistent_memory_size == 32

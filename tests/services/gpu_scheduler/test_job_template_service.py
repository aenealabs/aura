"""Tests for GPU Job Template Service (Phase 5)."""

from __future__ import annotations

import pytest

from src.services.gpu_scheduler.exceptions import TemplateNotFoundError
from src.services.gpu_scheduler.job_template_service import GPUJobTemplateService
from src.services.gpu_scheduler.models import (
    EmbeddingJobConfig,
    GPUJobType,
    TemplateCreateRequest,
)


class TestGPUJobTemplateService:
    """Tests for GPU job template CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_template(
        self,
        job_template_service: GPUJobTemplateService,
        sample_template_request: TemplateCreateRequest,
    ):
        """Test creating a new job template."""
        template = await job_template_service.create_template(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=sample_template_request,
        )

        assert template is not None
        assert template.template_id.startswith("tpl-")
        assert template.organization_id == "org-test-123"
        assert template.user_id == "user-test-456"
        assert template.name == sample_template_request.name
        assert template.job_type == sample_template_request.job_type
        assert template.use_count == 0
        assert template.created_at is not None

    @pytest.mark.asyncio
    async def test_get_template(
        self,
        job_template_service: GPUJobTemplateService,
        sample_template_request: TemplateCreateRequest,
    ):
        """Test retrieving a template by ID."""
        # Create template first
        created = await job_template_service.create_template(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=sample_template_request,
        )

        # Retrieve it
        retrieved = await job_template_service.get_template(
            organization_id="org-test-123",
            template_id=created.template_id,
            user_id="user-test-456",
        )

        assert retrieved is not None
        assert retrieved.template_id == created.template_id
        assert retrieved.name == created.name

    @pytest.mark.asyncio
    async def test_get_template_not_found(
        self,
        job_template_service: GPUJobTemplateService,
    ):
        """Test error when template not found."""
        with pytest.raises(TemplateNotFoundError):
            await job_template_service.get_template(
                organization_id="org-test-123",
                template_id="nonexistent-id",
                user_id="user-test-456",
            )

    @pytest.mark.asyncio
    async def test_update_template(
        self,
        job_template_service: GPUJobTemplateService,
        sample_template_request: TemplateCreateRequest,
    ):
        """Test updating an existing template."""
        # Create template
        created = await job_template_service.create_template(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=sample_template_request,
        )

        # Update it
        updated = await job_template_service.update_template(
            organization_id="org-test-123",
            template_id=created.template_id,
            user_id="user-test-456",
            updates={"name": "Updated Template Name", "gpu_memory_gb": 16},
        )

        assert updated.name == "Updated Template Name"
        assert updated.gpu_memory_gb == 16
        assert updated.updated_at is not None

    @pytest.mark.asyncio
    async def test_delete_template(
        self,
        job_template_service: GPUJobTemplateService,
        sample_template_request: TemplateCreateRequest,
    ):
        """Test deleting a template."""
        # Create template
        created = await job_template_service.create_template(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=sample_template_request,
        )

        # Delete it
        result = await job_template_service.delete_template(
            organization_id="org-test-123",
            template_id=created.template_id,
            user_id="user-test-456",
        )

        assert result is True

        # Verify it's gone
        with pytest.raises(TemplateNotFoundError):
            await job_template_service.get_template(
                organization_id="org-test-123",
                template_id=created.template_id,
                user_id="user-test-456",
            )

    @pytest.mark.asyncio
    async def test_list_templates(
        self,
        job_template_service: GPUJobTemplateService,
        sample_embedding_config: EmbeddingJobConfig,
    ):
        """Test listing templates with filters."""
        # Create multiple templates
        for i in range(3):
            request = TemplateCreateRequest(
                name=f"Template {i}",
                job_type=GPUJobType.EMBEDDING_GENERATION,
                config=sample_embedding_config,
                tags=[f"tag-{i}"],
            )
            await job_template_service.create_template(
                organization_id="org-test-123",
                user_id="user-test-456",
                request=request,
            )

        # List all
        templates = await job_template_service.list_templates(
            organization_id="org-test-123",
            user_id="user-test-456",
        )

        assert len(templates) == 3

    @pytest.mark.asyncio
    async def test_list_templates_by_job_type(
        self,
        job_template_service: GPUJobTemplateService,
        sample_embedding_config: EmbeddingJobConfig,
    ):
        """Test filtering templates by job type."""
        # Create embedding template
        request1 = TemplateCreateRequest(
            name="Embedding Template",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            config=sample_embedding_config,
        )
        await job_template_service.create_template(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=request1,
        )

        # List by job type
        templates = await job_template_service.list_templates(
            organization_id="org-test-123",
            user_id="user-test-456",
            job_type=GPUJobType.EMBEDDING_GENERATION,
        )

        assert len(templates) == 1
        assert templates[0].job_type == GPUJobType.EMBEDDING_GENERATION

    @pytest.mark.asyncio
    async def test_create_job_request_from_template(
        self,
        job_template_service: GPUJobTemplateService,
        sample_template_request: TemplateCreateRequest,
    ):
        """Test creating a job request from a template."""
        # Create template
        template = await job_template_service.create_template(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=sample_template_request,
        )

        # Create job request
        job_request = await job_template_service.create_job_request_from_template(
            organization_id="org-test-123",
            template_id=template.template_id,
            user_id="user-test-456",
        )

        assert job_request["job_type"] == template.job_type.value
        assert job_request["priority"] == template.priority.value
        assert job_request["gpu_memory_gb"] == template.gpu_memory_gb

    @pytest.mark.asyncio
    async def test_create_job_request_with_overrides(
        self,
        job_template_service: GPUJobTemplateService,
        sample_template_request: TemplateCreateRequest,
    ):
        """Test creating job request with parameter overrides."""
        # Create template
        template = await job_template_service.create_template(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=sample_template_request,
        )

        # Create job request with overrides
        job_request = await job_template_service.create_job_request_from_template(
            organization_id="org-test-123",
            template_id=template.template_id,
            user_id="user-test-456",
            overrides={"priority": "high", "gpu_memory_gb": 16},
        )

        assert job_request["priority"] == "high"
        assert job_request["gpu_memory_gb"] == 16

    @pytest.mark.asyncio
    async def test_increment_use_count(
        self,
        job_template_service: GPUJobTemplateService,
        sample_template_request: TemplateCreateRequest,
    ):
        """Test that use_count is incremented when template is used."""
        # Create template
        template = await job_template_service.create_template(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=sample_template_request,
        )
        assert template.use_count == 0

        # Use the template
        await job_template_service.create_job_request_from_template(
            organization_id="org-test-123",
            template_id=template.template_id,
            user_id="user-test-456",
        )

        # Check use count incremented
        updated = await job_template_service.get_template(
            organization_id="org-test-123",
            template_id=template.template_id,
            user_id="user-test-456",
        )
        assert updated.use_count == 1

    @pytest.mark.asyncio
    async def test_export_import_template(
        self,
        job_template_service: GPUJobTemplateService,
        sample_template_request: TemplateCreateRequest,
    ):
        """Test exporting and importing a template."""
        # Create template
        original = await job_template_service.create_template(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=sample_template_request,
        )

        # Export it
        exported = await job_template_service.export_template(
            organization_id="org-test-123",
            template_id=original.template_id,
            user_id="user-test-456",
        )

        assert "name" in exported
        assert "job_type" in exported
        assert "config" in exported

        # Import to different org
        imported = await job_template_service.import_template(
            organization_id="org-other-789",
            user_id="user-other-999",
            template_data=exported,
        )

        assert imported.organization_id == "org-other-789"
        assert imported.user_id == "user-other-999"
        assert imported.name == original.name
        assert imported.template_id != original.template_id  # New ID

    @pytest.mark.asyncio
    async def test_public_template_visibility(
        self,
        job_template_service: GPUJobTemplateService,
        sample_embedding_config: EmbeddingJobConfig,
    ):
        """Test public templates are visible to other users in org."""
        # Create public template
        request = TemplateCreateRequest(
            name="Public Template",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            config=sample_embedding_config,
            is_public=True,
        )
        public_template = await job_template_service.create_template(
            organization_id="org-test-123",
            user_id="user-owner-111",
            request=request,
        )

        # Different user can access it
        retrieved = await job_template_service.get_template(
            organization_id="org-test-123",
            template_id=public_template.template_id,
            user_id="user-other-222",
        )

        assert retrieved is not None
        assert retrieved.is_public is True


class TestGPUJobTemplateMultiGPU:
    """Tests for multi-GPU template support."""

    @pytest.mark.asyncio
    async def test_create_multi_gpu_template(
        self,
        job_template_service: GPUJobTemplateService,
        sample_embedding_config: EmbeddingJobConfig,
    ):
        """Test creating a template with multiple GPUs."""
        request = TemplateCreateRequest(
            name="Multi-GPU Training",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            config=sample_embedding_config,
            gpu_count=4,
            gpu_memory_gb=16,
        )

        template = await job_template_service.create_template(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=request,
        )

        assert template.gpu_count == 4

    @pytest.mark.asyncio
    async def test_multi_gpu_job_request(
        self,
        job_template_service: GPUJobTemplateService,
        sample_embedding_config: EmbeddingJobConfig,
    ):
        """Test job request from multi-GPU template includes gpu_count."""
        # Create multi-GPU template
        request = TemplateCreateRequest(
            name="Multi-GPU Training",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            config=sample_embedding_config,
            gpu_count=4,
        )

        template = await job_template_service.create_template(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=request,
        )

        # Create job request
        job_request = await job_template_service.create_job_request_from_template(
            organization_id="org-test-123",
            template_id=template.template_id,
            user_id="user-test-456",
        )

        assert job_request["gpu_count"] == 4

"""
Project Aura - GPU Job Template Service

Manages reusable GPU job configuration templates for:
- Saving frequently used job configurations
- Sharing templates within an organization
- Quick job submission from templates
- Template versioning and usage tracking

ADR-061: GPU Workload Scheduler - Phase 5 Advanced Features
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

from .exceptions import (
    GPUSchedulerError,
    TemplateAccessDeniedError,
    TemplateNotFoundError,
)
from .models import (
    EmbeddingJobConfig,
    GPUJobConfig,
    GPUJobPriority,
    GPUJobTemplate,
    GPUJobType,
    LocalInferenceConfig,
    MemoryConsolidationConfig,
    SWERLTrainingConfig,
    TemplateCreateRequest,
    VulnerabilityTrainingConfig,
)

logger = logging.getLogger(__name__)


class TemplateLimitExceededError(GPUSchedulerError):
    """Raised when organization template limit is exceeded."""

    def __init__(self, message: str):
        super().__init__(message)


# Alias for backwards compatibility
TemplatePermissionError = TemplateAccessDeniedError


# Configuration
MAX_TEMPLATES_PER_ORG = 100
MAX_TEMPLATES_PER_USER = 50


class GPUJobTemplateService:
    """
    Manages GPU job configuration templates.

    Features:
    - Save job configurations as reusable templates
    - Organization-wide and personal templates
    - Template search by name, tags, and job type
    - Usage tracking and analytics

    Usage:
        service = GPUJobTemplateService(table_name="aura-gpu-templates-dev")

        # Create a template
        template = await service.create_template(
            organization_id="org-123",
            user_id="user-456",
            request=TemplateCreateRequest(
                name="Daily Embedding Update",
                job_type=GPUJobType.EMBEDDING_GENERATION,
                config=EmbeddingJobConfig(repository_id="backend-api"),
            ),
        )

        # Use template to create a job
        job_request = await service.create_job_request_from_template(
            organization_id="org-123",
            template_id="template-789",
        )
    """

    def __init__(
        self,
        table_name: str | None = None,
        region: str | None = None,
    ):
        """
        Initialize the template service.

        Args:
            table_name: DynamoDB table for templates
            region: AWS region
        """
        self.table_name = table_name or "aura-gpu-templates"
        self.region = region or "us-east-1"

        # Lazy-loaded DynamoDB table
        self._table = None

        logger.info(f"GPUJobTemplateService initialized (table={self.table_name})")

    @property
    def table(self):
        """Lazy-load DynamoDB table."""
        if self._table is None:
            dynamodb = boto3.resource("dynamodb", region_name=self.region)
            self._table = dynamodb.Table(self.table_name)
        return self._table

    # =========================================================================
    # Template CRUD Operations
    # =========================================================================

    async def create_template(
        self,
        organization_id: str,
        user_id: str,
        request: TemplateCreateRequest,
    ) -> GPUJobTemplate:
        """
        Create a new job template.

        Args:
            organization_id: Organization ID
            user_id: User creating the template
            request: Template creation request

        Returns:
            Created template

        Raises:
            TemplateLimitExceededError: If template limits exceeded
        """
        # Check limits
        await self._check_template_limits(organization_id, user_id)

        template_id = f"tpl-{uuid.uuid4()}"
        now = datetime.now(timezone.utc)

        template = GPUJobTemplate(
            template_id=template_id,
            organization_id=organization_id,
            user_id=user_id,
            name=request.name,
            description=request.description,
            job_type=request.job_type,
            config=request.config,
            priority=request.priority,
            gpu_memory_gb=request.gpu_memory_gb,
            gpu_count=request.gpu_count,
            max_runtime_hours=request.max_runtime_hours,
            checkpoint_enabled=request.checkpoint_enabled,
            is_public=request.is_public,
            tags=request.tags,
            use_count=0,
            created_at=now,
        )

        self.table.put_item(Item=template.to_dynamodb_item())

        logger.info(
            f"Created template '{template.name}' ({template_id}) "
            f"for org {organization_id}"
        )

        return template

    async def get_template(
        self,
        organization_id: str,
        template_id: str,
        user_id: str | None = None,
    ) -> GPUJobTemplate:
        """
        Get a template by ID.

        Args:
            organization_id: Organization ID
            template_id: Template ID
            user_id: Optional user ID for permission check

        Returns:
            Template object

        Raises:
            TemplateNotFoundError: If template not found
            TemplatePermissionError: If user lacks access
        """
        response = self.table.get_item(
            Key={
                "organization_id": organization_id,
                "template_id": template_id,
            }
        )

        item = response.get("Item")
        if not item:
            raise TemplateNotFoundError(template_id, organization_id)

        template = GPUJobTemplate.from_dynamodb_item(item)

        # Check permission for private templates
        if user_id and not template.is_public and template.user_id != user_id:
            raise TemplateAccessDeniedError(template_id, user_id)

        return template

    async def update_template(
        self,
        organization_id: str,
        template_id: str,
        user_id: str,
        updates: dict[str, Any],
    ) -> GPUJobTemplate:
        """
        Update an existing template.

        Args:
            organization_id: Organization ID
            template_id: Template ID
            user_id: User making the update
            updates: Fields to update

        Returns:
            Updated template

        Raises:
            TemplateNotFoundError: If template not found
            TemplatePermissionError: If user lacks permission
        """
        # Verify ownership
        template = await self.get_template(organization_id, template_id)
        if template.user_id != user_id:
            raise TemplateAccessDeniedError(template_id, user_id)

        # Build update expression
        update_parts = ["updated_at = :updated_at"]
        expr_values: dict[str, Any] = {
            ":updated_at": datetime.now(timezone.utc).isoformat()
        }
        expr_names: dict[str, str] = {}

        allowed_fields = {
            "name",
            "description",
            "config",
            "priority",
            "gpu_memory_gb",
            "gpu_count",
            "max_runtime_hours",
            "checkpoint_enabled",
            "is_public",
            "tags",
        }

        # Reserved words in DynamoDB that need expression attribute names
        reserved_words = {"name", "status", "type", "config"}

        for field, value in updates.items():
            if field in allowed_fields:
                if field == "config":
                    value = (
                        value.model_dump() if hasattr(value, "model_dump") else value
                    )
                elif field == "priority":
                    value = value.value if hasattr(value, "value") else value

                # Handle reserved words
                if field in reserved_words:
                    expr_names[f"#{field}"] = field
                    update_parts.append(f"#{field} = :{field}")
                else:
                    update_parts.append(f"{field} = :{field}")
                expr_values[f":{field}"] = value

        update_kwargs = {
            "Key": {
                "organization_id": organization_id,
                "template_id": template_id,
            },
            "UpdateExpression": "SET " + ", ".join(update_parts),
            "ExpressionAttributeValues": expr_values,
        }
        if expr_names:
            update_kwargs["ExpressionAttributeNames"] = expr_names

        self.table.update_item(**update_kwargs)

        logger.info(f"Updated template {template_id}")

        return await self.get_template(organization_id, template_id)

    async def delete_template(
        self,
        organization_id: str,
        template_id: str,
        user_id: str,
    ) -> bool:
        """
        Delete a template.

        Args:
            organization_id: Organization ID
            template_id: Template ID
            user_id: User requesting deletion

        Returns:
            True if deleted successfully

        Raises:
            TemplateNotFoundError: If template not found
            TemplateAccessDeniedError: If user lacks permission
        """
        # Verify ownership
        template = await self.get_template(organization_id, template_id)
        if template.user_id != user_id:
            raise TemplateAccessDeniedError(template_id, user_id)

        self.table.delete_item(
            Key={
                "organization_id": organization_id,
                "template_id": template_id,
            }
        )

        logger.info(f"Deleted template {template_id}")
        return True

    # =========================================================================
    # Template Listing and Search
    # =========================================================================

    async def list_templates(
        self,
        organization_id: str,
        user_id: str | None = None,
        include_public: bool = True,
        job_type: GPUJobType | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> list[GPUJobTemplate]:
        """
        List templates for an organization.

        Args:
            organization_id: Organization ID
            user_id: Optional user ID to filter personal templates
            include_public: Whether to include public org templates
            job_type: Filter by job type
            tags: Filter by tags (any match)
            limit: Maximum results

        Returns:
            List of templates
        """
        response = self.table.query(
            KeyConditionExpression="organization_id = :org_id",
            ExpressionAttributeValues={":org_id": organization_id},
            Limit=limit * 2,  # Over-fetch to account for filtering
        )

        templates = []
        for item in response.get("Items", []):
            template = GPUJobTemplate.from_dynamodb_item(item)

            # Filter by visibility
            if user_id:
                if not template.is_public and template.user_id != user_id:
                    continue
            elif not include_public:
                continue

            # Filter by job type
            if job_type and template.job_type != job_type:
                continue

            # Filter by tags (any match)
            if tags:
                if not any(tag in template.tags for tag in tags):
                    continue

            templates.append(template)

            if len(templates) >= limit:
                break

        return templates

    async def list_user_templates(
        self,
        organization_id: str,
        user_id: str,
        limit: int = 50,
    ) -> list[GPUJobTemplate]:
        """
        List templates created by a specific user.

        Args:
            organization_id: Organization ID
            user_id: User ID
            limit: Maximum results

        Returns:
            List of user's templates
        """
        # Query using user-templates GSI
        response = self.table.query(
            IndexName="user-templates-index",
            KeyConditionExpression="user_id = :user_id",
            FilterExpression="organization_id = :org_id",
            ExpressionAttributeValues={
                ":user_id": user_id,
                ":org_id": organization_id,
            },
            Limit=limit,
        )

        return [
            GPUJobTemplate.from_dynamodb_item(item)
            for item in response.get("Items", [])
        ]

    async def search_templates(
        self,
        organization_id: str,
        query: str,
        user_id: str | None = None,
        limit: int = 20,
    ) -> list[GPUJobTemplate]:
        """
        Search templates by name or description.

        Args:
            organization_id: Organization ID
            query: Search query (case-insensitive)
            user_id: Optional user ID for permission filtering
            limit: Maximum results

        Returns:
            Matching templates
        """
        query_lower = query.lower()

        # Get all templates and filter (for simplicity; could use OpenSearch)
        all_templates = await self.list_templates(
            organization_id=organization_id,
            user_id=user_id,
            limit=500,
        )

        results = []
        for template in all_templates:
            # Search in name, description, and tags
            searchable = (
                template.name.lower()
                + " "
                + (template.description or "").lower()
                + " "
                + " ".join(template.tags)
            )
            if query_lower in searchable:
                results.append(template)
                if len(results) >= limit:
                    break

        return results

    # =========================================================================
    # Template Usage
    # =========================================================================

    async def increment_use_count(
        self,
        organization_id: str,
        template_id: str,
    ) -> None:
        """
        Increment the use count for a template.

        Args:
            organization_id: Organization ID
            template_id: Template ID
        """
        try:
            self.table.update_item(
                Key={
                    "organization_id": organization_id,
                    "template_id": template_id,
                },
                UpdateExpression="SET use_count = use_count + :inc",
                ExpressionAttributeValues={":inc": 1},
            )
        except ClientError as e:
            logger.warning(f"Failed to increment use count: {e}")

    async def get_popular_templates(
        self,
        organization_id: str,
        limit: int = 10,
    ) -> list[GPUJobTemplate]:
        """
        Get most popular templates by usage count.

        Args:
            organization_id: Organization ID
            limit: Maximum results

        Returns:
            Templates sorted by use_count descending
        """
        templates = await self.list_templates(
            organization_id=organization_id,
            include_public=True,
            limit=100,
        )

        # Sort by use count
        templates.sort(key=lambda t: t.use_count, reverse=True)

        return templates[:limit]

    async def create_job_request_from_template(
        self,
        organization_id: str,
        template_id: str,
        user_id: str,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create a job submission request from a template.

        Args:
            organization_id: Organization ID
            template_id: Template ID to use
            user_id: User requesting the job
            overrides: Optional field overrides

        Returns:
            Job creation request dict compatible with GPUJobCreateRequest

        Raises:
            TemplateNotFoundError: If template not found
        """
        template = await self.get_template(
            organization_id=organization_id,
            template_id=template_id,
            user_id=user_id,
        )

        # Increment usage
        await self.increment_use_count(organization_id, template_id)

        # Build request
        request = {
            "job_type": template.job_type.value,
            "config": template.config.model_dump(),
            "priority": template.priority.value,
            "gpu_memory_gb": template.gpu_memory_gb,
            "gpu_count": template.gpu_count,
            "max_runtime_hours": template.max_runtime_hours,
            "checkpoint_enabled": template.checkpoint_enabled,
        }

        # Apply overrides
        if overrides:
            for key, value in overrides.items():
                if key in request:
                    request[key] = value

        return request

    # =========================================================================
    # Template Import/Export
    # =========================================================================

    async def export_template(
        self,
        organization_id: str,
        template_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """
        Export a template as a portable JSON object.

        Args:
            organization_id: Organization ID
            template_id: Template ID
            user_id: User requesting export

        Returns:
            Template as portable dict (without org-specific IDs)
        """
        template = await self.get_template(
            organization_id=organization_id,
            template_id=template_id,
            user_id=user_id,
        )

        return {
            "name": template.name,
            "description": template.description,
            "job_type": template.job_type.value,
            "config": template.config.model_dump(),
            "priority": template.priority.value,
            "gpu_memory_gb": template.gpu_memory_gb,
            "gpu_count": template.gpu_count,
            "max_runtime_hours": template.max_runtime_hours,
            "checkpoint_enabled": template.checkpoint_enabled,
            "tags": template.tags,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }

    async def import_template(
        self,
        organization_id: str,
        user_id: str,
        template_data: dict[str, Any],
    ) -> GPUJobTemplate:
        """
        Import a template from a portable JSON object.

        Args:
            organization_id: Organization ID
            user_id: User importing the template
            template_data: Portable template dict

        Returns:
            Created template

        Raises:
            ValueError: If template data is invalid
        """
        # Parse job type and config
        job_type = GPUJobType(template_data["job_type"])
        config_data = template_data["config"]

        config: GPUJobConfig
        if job_type == GPUJobType.EMBEDDING_GENERATION:
            config = EmbeddingJobConfig(**config_data)
        elif job_type == GPUJobType.VULNERABILITY_TRAINING:
            config = VulnerabilityTrainingConfig(**config_data)
        elif job_type == GPUJobType.SWE_RL_TRAINING:
            config = SWERLTrainingConfig(**config_data)
        elif job_type == GPUJobType.MEMORY_CONSOLIDATION:
            config = MemoryConsolidationConfig(**config_data)
        elif job_type == GPUJobType.LOCAL_INFERENCE:
            config = LocalInferenceConfig(**config_data)
        else:
            raise ValueError(f"Unknown job type: {job_type}")

        request = TemplateCreateRequest(
            name=template_data.get("name", "Imported Template"),
            description=template_data.get("description"),
            job_type=job_type,
            config=config,
            priority=GPUJobPriority(template_data.get("priority", "normal")),
            gpu_memory_gb=template_data.get("gpu_memory_gb", 8),
            gpu_count=template_data.get("gpu_count", 1),
            max_runtime_hours=template_data.get("max_runtime_hours", 2),
            checkpoint_enabled=template_data.get("checkpoint_enabled", True),
            is_public=False,  # Imported templates start as private
            tags=template_data.get("tags", []),
        )

        return await self.create_template(organization_id, user_id, request)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _check_template_limits(
        self,
        organization_id: str,
        user_id: str,
    ) -> None:
        """Check if template limits are exceeded."""
        # Check org limit
        org_templates = await self.list_templates(
            organization_id=organization_id,
            limit=MAX_TEMPLATES_PER_ORG + 1,
        )
        if len(org_templates) >= MAX_TEMPLATES_PER_ORG:
            raise TemplateLimitExceededError(
                f"Organization limit of {MAX_TEMPLATES_PER_ORG} templates exceeded"
            )

        # Check user limit
        user_templates = await self.list_user_templates(
            organization_id=organization_id,
            user_id=user_id,
            limit=MAX_TEMPLATES_PER_USER + 1,
        )
        if len(user_templates) >= MAX_TEMPLATES_PER_USER:
            raise TemplateLimitExceededError(
                f"User limit of {MAX_TEMPLATES_PER_USER} templates exceeded"
            )

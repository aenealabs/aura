#!/usr/bin/env python3
"""
Project Aura - Migration CLI

Unified command-line interface for migrating from AWS to self-hosted services.

Usage:
    python -m src.migration.cli neptune --help
    python -m src.migration.cli dynamodb --help
    python -m src.migration.cli s3 --help
    python -m src.migration.cli secrets --help
    python -m src.migration.cli all --help

See ADR-049: Self-Hosted Deployment Strategy
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from src.migration.base import MigrationConfig, MigrationProgress, MigrationResult

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for CLI."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def progress_callback(progress: MigrationProgress) -> None:
    """Print progress updates."""
    bar_width = 40
    filled = int(bar_width * progress.percent_complete / 100)
    bar = "=" * filled + "-" * (bar_width - filled)

    print(
        f"\r[{bar}] {progress.percent_complete:.1f}% "
        f"({progress.migrated_items}/{progress.total_items}) "
        f"ETA: {progress.estimated_remaining_seconds:.0f}s",
        end="",
        flush=True,
    )


def print_result(result: MigrationResult) -> None:
    """Print migration result summary."""
    print("\n")
    print("=" * 60)
    print("MIGRATION RESULT")
    print("=" * 60)
    print(f"Status:       {result.status.value.upper()}")
    print(f"Source:       {result.source_type}")
    print(f"Target:       {result.target_type}")
    print(f"Started:      {result.started_at.isoformat()}")
    if result.completed_at:
        print(f"Completed:    {result.completed_at.isoformat()}")
    print("-" * 60)
    print(f"Total Items:  {result.progress.total_items}")
    print(f"Migrated:     {result.progress.migrated_items}")
    print(f"Failed:       {result.progress.failed_items}")
    print(f"Skipped:      {result.progress.skipped_items}")
    print(f"Duration:     {result.progress.elapsed_seconds:.2f} seconds")
    print(f"Rate:         {result.progress.items_per_second:.2f} items/sec")

    if result.error_message:
        print("-" * 60)
        print(f"Error:        {result.error_message}")

    if result.warnings:
        print("-" * 60)
        print("Warnings:")
        for warning in result.warnings:
            print(f"  - {warning}")

    if result.progress.errors:
        print("-" * 60)
        print(f"Errors ({len(result.progress.errors)} total):")
        for error in result.progress.errors[:10]:  # Show first 10
            print(f"  - {error}")
        if len(result.progress.errors) > 10:
            print(f"  ... and {len(result.progress.errors) - 10} more")

    print("=" * 60)


async def migrate_neptune(args: argparse.Namespace) -> MigrationResult:
    """Run Neptune to Neo4j migration."""
    from src.migration.neptune_to_neo4j import NeptuneToNeo4jMigrator

    config = MigrationConfig(
        batch_size=args.batch_size,
        max_concurrent=args.concurrency,
        stop_on_error=args.stop_on_error,
        skip_existing=not args.overwrite,
        verify_data=args.verify,
        dry_run=args.dry_run,
    )

    migrator = NeptuneToNeo4jMigrator(
        neptune_endpoint=args.neptune_endpoint,
        neo4j_uri=args.neo4j_uri,
        neo4j_username=args.neo4j_username,
        neo4j_password=args.neo4j_password,
        neo4j_database=args.neo4j_database,
        config=config,
    )

    migrator.set_progress_callback(progress_callback)
    return await migrator.run()


async def migrate_dynamodb(args: argparse.Namespace) -> MigrationResult:
    """Run DynamoDB to PostgreSQL migration."""
    from src.migration.dynamodb_to_postgres import DynamoDBToPostgresMigrator

    config = MigrationConfig(
        batch_size=args.batch_size,
        max_concurrent=args.concurrency,
        stop_on_error=args.stop_on_error,
        skip_existing=not args.overwrite,
        verify_data=args.verify,
        dry_run=args.dry_run,
    )

    tables = args.tables.split(",") if args.tables else None

    migrator = DynamoDBToPostgresMigrator(
        dynamodb_region=args.region,
        dynamodb_table_prefix=args.dynamodb_prefix,
        postgres_host=args.postgres_host,
        postgres_port=args.postgres_port,
        postgres_database=args.postgres_database,
        postgres_username=args.postgres_username,
        postgres_password=args.postgres_password,
        postgres_table_prefix=args.postgres_prefix,
        tables=tables,
        config=config,
    )

    migrator.set_progress_callback(progress_callback)
    return await migrator.run()


async def migrate_s3(args: argparse.Namespace) -> MigrationResult:
    """Run S3 to MinIO migration."""
    from src.migration.s3_to_minio import S3ToMinioMigrator

    config = MigrationConfig(
        batch_size=args.batch_size,
        max_concurrent=args.concurrency,
        stop_on_error=args.stop_on_error,
        skip_existing=not args.overwrite,
        verify_data=args.verify,
        dry_run=args.dry_run,
    )

    buckets = args.buckets.split(",") if args.buckets else None
    bucket_mapping = {}
    if args.bucket_mapping:
        for mapping in args.bucket_mapping.split(","):
            src, dst = mapping.split(":")
            bucket_mapping[src] = dst

    migrator = S3ToMinioMigrator(
        s3_region=args.region,
        s3_buckets=buckets,
        minio_endpoint=args.minio_endpoint,
        minio_access_key=args.minio_access_key,
        minio_secret_key=args.minio_secret_key,
        minio_secure=args.minio_secure,
        bucket_mapping=bucket_mapping,
        config=config,
    )

    migrator.set_progress_callback(progress_callback)
    return await migrator.run()


async def migrate_secrets(args: argparse.Namespace) -> MigrationResult:
    """Run Secrets Manager to file migration."""
    from src.migration.secrets_to_file import SecretsToFileMigrator

    config = MigrationConfig(
        batch_size=args.batch_size,
        max_concurrent=args.concurrency,
        stop_on_error=args.stop_on_error,
        skip_existing=not args.overwrite,
        verify_data=args.verify,
        dry_run=args.dry_run,
    )

    migrator = SecretsToFileMigrator(
        secrets_manager_region=args.region,
        secrets_prefix=args.prefix,
        target_path=args.target_path,
        key_file=args.key_file,
        config=config,
    )

    migrator.set_progress_callback(progress_callback)
    result = await migrator.run()

    # Export key backup if requested
    if args.backup_key and result.status.value == "completed":
        await migrator.export_key_backup(args.backup_key)

    return result


async def migrate_all(args: argparse.Namespace) -> dict[str, MigrationResult]:
    """Run all migrations."""
    results = {}

    services = (
        args.services.split(",")
        if args.services
        else ["neptune", "dynamodb", "s3", "secrets"]
    )

    for service in services:
        print(f"\n{'='*60}")
        print(f"MIGRATING: {service.upper()}")
        print("=" * 60)

        if service == "neptune":
            results["neptune"] = await migrate_neptune(args)
        elif service == "dynamodb":
            results["dynamodb"] = await migrate_dynamodb(args)
        elif service == "s3":
            results["s3"] = await migrate_s3(args)
        elif service == "secrets":
            results["secrets"] = await migrate_secrets(args)

        print_result(results[service])

    return results


def add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add common arguments to parser."""
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of items per batch (default: 100)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Max concurrent operations (default: 5)",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop migration on first error",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing items in target",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        default=True,
        help="Verify each migrated item (default: true)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_false",
        dest="verify",
        help="Skip verification",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count items only, don't migrate",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output result to JSON file",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        prog="aura-migrate",
        description="Project Aura Migration Toolkit - AWS to Self-Hosted",
    )
    subparsers = parser.add_subparsers(dest="command", help="Migration type")

    # Neptune to Neo4j
    neptune_parser = subparsers.add_parser(
        "neptune",
        help="Migrate Neptune to Neo4j",
    )
    neptune_parser.add_argument(
        "--neptune-endpoint",
        required=True,
        help="Neptune cluster endpoint",
    )
    neptune_parser.add_argument(
        "--neo4j-uri",
        default="bolt://localhost:7687",
        help="Neo4j connection URI",
    )
    neptune_parser.add_argument(
        "--neo4j-username",
        default="neo4j",
        help="Neo4j username",
    )
    neptune_parser.add_argument(
        "--neo4j-password",
        required=True,
        help="Neo4j password",
    )
    neptune_parser.add_argument(
        "--neo4j-database",
        default="neo4j",
        help="Neo4j database name",
    )
    add_common_args(neptune_parser)

    # DynamoDB to PostgreSQL
    dynamodb_parser = subparsers.add_parser(
        "dynamodb",
        help="Migrate DynamoDB to PostgreSQL",
    )
    dynamodb_parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region",
    )
    dynamodb_parser.add_argument(
        "--dynamodb-prefix",
        default="aura_",
        help="DynamoDB table name prefix",
    )
    dynamodb_parser.add_argument(
        "--tables",
        help="Comma-separated list of tables to migrate (default: all)",
    )
    dynamodb_parser.add_argument(
        "--postgres-host",
        default="localhost",
        help="PostgreSQL host",
    )
    dynamodb_parser.add_argument(
        "--postgres-port",
        type=int,
        default=5432,
        help="PostgreSQL port",
    )
    dynamodb_parser.add_argument(
        "--postgres-database",
        default="aura",
        help="PostgreSQL database",
    )
    dynamodb_parser.add_argument(
        "--postgres-username",
        default="aura",
        help="PostgreSQL username",
    )
    dynamodb_parser.add_argument(
        "--postgres-password",
        required=True,
        help="PostgreSQL password",
    )
    dynamodb_parser.add_argument(
        "--postgres-prefix",
        default="aura_",
        help="PostgreSQL table name prefix",
    )
    add_common_args(dynamodb_parser)

    # S3 to MinIO
    s3_parser = subparsers.add_parser(
        "s3",
        help="Migrate S3 to MinIO",
    )
    s3_parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region",
    )
    s3_parser.add_argument(
        "--buckets",
        help="Comma-separated list of buckets to migrate (default: all)",
    )
    s3_parser.add_argument(
        "--bucket-mapping",
        help="Bucket name mapping (src1:dst1,src2:dst2)",
    )
    s3_parser.add_argument(
        "--minio-endpoint",
        default="localhost:9000",
        help="MinIO endpoint (host:port)",
    )
    s3_parser.add_argument(
        "--minio-access-key",
        default="minioadmin",
        help="MinIO access key",
    )
    s3_parser.add_argument(
        "--minio-secret-key",
        required=True,
        help="MinIO secret key",
    )
    s3_parser.add_argument(
        "--minio-secure",
        action="store_true",
        help="Use HTTPS for MinIO",
    )
    add_common_args(s3_parser)

    # Secrets Manager to File
    secrets_parser = subparsers.add_parser(
        "secrets",
        help="Migrate Secrets Manager to file-based",
    )
    secrets_parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region",
    )
    secrets_parser.add_argument(
        "--prefix",
        help="Secret name prefix to filter",
    )
    secrets_parser.add_argument(
        "--target-path",
        default="/etc/aura/secrets",
        help="Directory for migrated secrets",
    )
    secrets_parser.add_argument(
        "--key-file",
        default="/etc/aura/.secrets_key",
        help="Path to encryption key file",
    )
    secrets_parser.add_argument(
        "--backup-key",
        help="Export encryption key to this path",
    )
    add_common_args(secrets_parser)

    # All services
    all_parser = subparsers.add_parser(
        "all",
        help="Migrate all services",
    )
    all_parser.add_argument(
        "--services",
        help="Comma-separated list of services (default: all)",
    )
    # Add all args from individual parsers
    all_parser.add_argument("--neptune-endpoint", help="Neptune endpoint")
    all_parser.add_argument("--neo4j-uri", default="bolt://localhost:7687")
    all_parser.add_argument("--neo4j-username", default="neo4j")
    all_parser.add_argument("--neo4j-password")
    all_parser.add_argument("--neo4j-database", default="neo4j")
    all_parser.add_argument("--region", default="us-east-1")
    all_parser.add_argument("--dynamodb-prefix", default="aura_")
    all_parser.add_argument("--tables")
    all_parser.add_argument("--postgres-host", default="localhost")
    all_parser.add_argument("--postgres-port", type=int, default=5432)
    all_parser.add_argument("--postgres-database", default="aura")
    all_parser.add_argument("--postgres-username", default="aura")
    all_parser.add_argument("--postgres-password")
    all_parser.add_argument("--postgres-prefix", default="aura_")
    all_parser.add_argument("--buckets")
    all_parser.add_argument("--bucket-mapping")
    all_parser.add_argument("--minio-endpoint", default="localhost:9000")
    all_parser.add_argument("--minio-access-key", default="minioadmin")
    all_parser.add_argument("--minio-secret-key")
    all_parser.add_argument("--minio-secure", action="store_true")
    all_parser.add_argument("--prefix")
    all_parser.add_argument("--target-path", default="/etc/aura/secrets")
    all_parser.add_argument("--key-file", default="/etc/aura/.secrets_key")
    all_parser.add_argument("--backup-key")
    add_common_args(all_parser)

    return parser


async def main_async(args: argparse.Namespace) -> int:
    """Async main entry point."""
    result = None

    try:
        if args.command == "neptune":
            result = await migrate_neptune(args)
        elif args.command == "dynamodb":
            result = await migrate_dynamodb(args)
        elif args.command == "s3":
            result = await migrate_s3(args)
        elif args.command == "secrets":
            result = await migrate_secrets(args)
        elif args.command == "all":
            results = await migrate_all(args)
            # Save combined results
            if args.output:
                output_data = {k: v.to_dict() for k, v in results.items()}
                Path(args.output).write_text(json.dumps(output_data, indent=2))
            # Return failure if any migration failed
            for r in results.values():
                if r.status.value == "failed":
                    return 1
            return 0
        else:
            print("No command specified. Use --help for usage.")
            return 1

        print_result(result)

        # Save result if output specified
        if args.output:
            Path(args.output).write_text(json.dumps(result.to_dict(), indent=2))

        return 0 if result.status.value == "completed" else 1

    except KeyboardInterrupt:
        print("\nMigration cancelled by user")
        return 130

    except Exception as e:
        logger.exception(f"Migration failed: {e}")
        return 1


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    setup_logging(getattr(args, "verbose", False))
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())

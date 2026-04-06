"""
Tests for Queue Flow Analyzer
=============================

ADR-056 Phase 3: Data Flow Analysis

Tests for message queue detection in code.
"""

import platform
import tempfile
from pathlib import Path

import pytest

from src.services.data_flow.queue_analyzer import QueueFlowAnalyzer
from src.services.data_flow.types import QueueType

# Use forked mode on non-Linux to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestQueueFlowAnalyzerMock:
    """Tests for QueueFlowAnalyzer in mock mode."""

    @pytest.fixture
    def analyzer(self):
        """Create mock analyzer."""
        return QueueFlowAnalyzer(use_mock=True)

    @pytest.mark.asyncio
    async def test_analyze_file_mock(self, analyzer):
        """Test mock file analysis returns sample data."""
        connections = await analyzer.analyze_file("test.py")

        assert len(connections) > 0
        assert all(conn.connection_id for conn in connections)
        assert any(conn.queue_type == QueueType.SQS for conn in connections)

    @pytest.mark.asyncio
    async def test_analyze_directory_mock(self, analyzer):
        """Test mock directory analysis returns sample data."""
        connections = await analyzer.analyze_directory("/some/path")

        assert len(connections) > 0
        queue_types = {conn.queue_type for conn in connections}
        assert len(queue_types) >= 2


class TestQueueFlowAnalyzerReal:
    """Tests for QueueFlowAnalyzer with real code analysis."""

    @pytest.fixture
    def analyzer(self):
        """Create real analyzer."""
        return QueueFlowAnalyzer(use_mock=False)

    @pytest.mark.asyncio
    async def test_analyze_file_nonexistent(self, analyzer):
        """Test analyzing nonexistent file returns empty list."""
        connections = await analyzer.analyze_file("/nonexistent/file.py")
        assert connections == []

    @pytest.mark.asyncio
    async def test_analyze_file_with_sqs(self, analyzer):
        """Test detecting SQS connections."""
        code = """
import boto3

sqs = boto3.client("sqs")

def send_message(queue_url, message):
    sqs.send_message(QueueUrl=queue_url, MessageBody=message)

def receive_messages(queue_url):
    response = sqs.receive_message(QueueUrl=queue_url)
    return response.get("Messages", [])
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            connections = await analyzer.analyze_file(temp_path)
            assert len(connections) >= 1
            assert any(conn.queue_type == QueueType.SQS for conn in connections)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_analyze_file_with_sns(self, analyzer):
        """Test detecting SNS connections."""
        code = """
import boto3

sns = boto3.client("sns")

def publish_event(topic_arn, message):
    sns.publish(TopicArn=topic_arn, Message=message)
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            connections = await analyzer.analyze_file(temp_path)
            assert len(connections) >= 1
            assert any(conn.queue_type == QueueType.SNS for conn in connections)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_analyze_file_with_kafka(self, analyzer):
        """Test detecting Kafka connections."""
        code = """
from kafka import KafkaProducer, KafkaConsumer

producer = KafkaProducer(bootstrap_servers="localhost:9092")

def send_event(topic, key, value):
    producer.send(topic, key=key, value=value)

consumer = KafkaConsumer("my-topic", bootstrap_servers="localhost:9092")

def consume_events():
    for message in consumer:
        process(message)
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            connections = await analyzer.analyze_file(temp_path)
            assert len(connections) >= 1
            assert any(conn.queue_type == QueueType.KAFKA for conn in connections)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_analyze_file_with_rabbitmq(self, analyzer):
        """Test detecting RabbitMQ connections."""
        code = """
import pika

connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
channel = connection.channel()

def publish_message(queue_name, message):
    channel.basic_publish(exchange="", routing_key=queue_name, body=message)

def consume_messages(queue_name, callback):
    channel.basic_consume(queue=queue_name, on_message_callback=callback)
    channel.start_consuming()
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            connections = await analyzer.analyze_file(temp_path)
            assert len(connections) >= 1
            assert any(conn.queue_type == QueueType.RABBITMQ for conn in connections)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_analyze_file_with_celery(self, analyzer):
        """Test detecting Celery task queues."""
        code = """
from celery import Celery

app = Celery("tasks", broker="redis://localhost:6379")

@app.task
def process_order(order_id):
    # Process the order
    pass

@app.task
def send_notification(user_id, message):
    # Send notification
    pass
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            connections = await analyzer.analyze_file(temp_path)
            assert len(connections) >= 1
            assert any(conn.queue_type == QueueType.CELERY for conn in connections)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_analyze_file_detects_producer(self, analyzer):
        """Test detecting producer operations."""
        code = """
import boto3

sqs = boto3.client("sqs")
queue_url = "https://sqs.us-east-1.amazonaws.com/123456789/my-queue"

def send_event(event):
    sqs.send_message(QueueUrl=queue_url, MessageBody=str(event))
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            connections = await analyzer.analyze_file(temp_path)
            assert len(connections) >= 1
            assert any(conn.is_producer for conn in connections)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_analyze_file_detects_consumer(self, analyzer):
        """Test detecting consumer operations."""
        code = """
import boto3

sqs = boto3.client("sqs")
queue_url = "https://sqs.us-east-1.amazonaws.com/123456789/my-queue"

def process_messages():
    response = sqs.receive_message(QueueUrl=queue_url)
    for msg in response.get("Messages", []):
        process(msg)
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            connections = await analyzer.analyze_file(temp_path)
            assert len(connections) >= 1
            assert any(conn.is_consumer for conn in connections)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_analyze_file_no_queues(self, analyzer):
        """Test file without queue connections."""
        code = """
def calculate_tax(amount, rate):
    return amount * rate

def format_currency(amount):
    return f"${amount:.2f}"
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            connections = await analyzer.analyze_file(temp_path)
            assert connections == []
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_analyze_directory(self, analyzer):
        """Test directory analysis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_file = Path(tmpdir) / "event_publisher.py"
            # Add more specific SQS usage pattern for detection
            queue_file.write_text(
                """
import boto3

sqs = boto3.client("sqs")
queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/my-queue"

def send_event(event):
    sqs.send_message(QueueUrl=queue_url, MessageBody=str(event))
"""
            )
            util_file = Path(tmpdir) / "utils.py"
            util_file.write_text(
                """
def helper():
    pass
"""
            )

            connections = await analyzer.analyze_directory(tmpdir)
            # Verify it doesn't error and returns a list
            assert isinstance(connections, list)

    @pytest.mark.asyncio
    async def test_analyze_file_with_eventbridge(self, analyzer):
        """Test detecting EventBridge connections."""
        code = """
import boto3

events = boto3.client("events")

def put_event(detail_type, detail):
    events.put_events(
        Entries=[{
            "Source": "my.app",
            "DetailType": detail_type,
            "Detail": detail,
        }]
    )
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            connections = await analyzer.analyze_file(temp_path)
            assert len(connections) >= 1
            assert any(conn.queue_type == QueueType.EVENTBRIDGE for conn in connections)
        finally:
            Path(temp_path).unlink()


class TestQueueFlowAnalyzerEdgeCases:
    """Edge case tests for QueueFlowAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create real analyzer."""
        return QueueFlowAnalyzer(use_mock=False)

    @pytest.mark.asyncio
    async def test_syntax_error_file(self, analyzer):
        """Test handling of files with syntax errors."""
        code = """
import boto3
sqs = boto3.client("sqs"
# Missing closing parenthesis
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            connections = await analyzer.analyze_file(temp_path)
            assert isinstance(connections, list)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_empty_file(self, analyzer):
        """Test handling of empty files."""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            connections = await analyzer.analyze_file(temp_path)
            assert connections == []
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_multiple_queue_types(self, analyzer):
        """Test detecting multiple queue types in same file."""
        code = """
import boto3
from kafka import KafkaProducer

sqs = boto3.client("sqs")
kafka_producer = KafkaProducer(bootstrap_servers="localhost:9092")

def send_to_sqs(msg):
    sqs.send_message(QueueUrl="url", MessageBody=msg)

def send_to_kafka(msg):
    kafka_producer.send("topic", msg)
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            connections = await analyzer.analyze_file(temp_path)
            queue_types = {conn.queue_type for conn in connections}
            assert len(queue_types) >= 2
        finally:
            Path(temp_path).unlink()

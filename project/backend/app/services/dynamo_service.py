"""
DynamoDB Service
================
Generic CRUD wrapper for AWS DynamoDB.
Replaces SQLAlchemy/SQLite for AWS migration.
"""

import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal
import structlog
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from app.core.config import settings


logger = structlog.get_logger()


def _convert_floats(obj):
    """Convert float values to Decimal for DynamoDB compatibility."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _convert_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_floats(i) for i in obj]
    return obj


def _convert_decimals(obj):
    """Convert Decimal values back to float/int for JSON serialization."""
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_decimals(i) for i in obj]
    return obj


class DynamoService:
    """
    Generic DynamoDB CRUD service.

    Provides typed operations for all CareerForge tables:
    - Users (PK: userId)
    - Projects (PK: userId, SK: projectId)
    - Resumes (PK: userId, SK: resumeId)
    - Jobs (PK: jobId)
    - Applications (PK: userId, SK: applicationId)
    - Roadmaps (PK: userId, SK: roadmapId)
    """

    def __init__(self):
        self._resource = None

    def _get_resource(self):
        """Get or create DynamoDB resource."""
        if self._resource is None:
            self._resource = boto3.resource(
                "dynamodb",
                region_name=settings.AWS_REGION,
            )
            logger.info("Initialized DynamoDB resource", region=settings.AWS_REGION)
        return self._resource

    def _get_table(self, table_name: str):
        """Get a DynamoDB table reference."""
        return self._get_resource().Table(table_name)

    async def put_item(self, table: str, item: dict) -> dict:
        """
        Put an item into a DynamoDB table.

        Args:
            table: Table name
            item: Item dict to store

        Returns:
            The stored item
        """
        dynamo_table = self._get_table(table)
        # Convert floats to Decimal
        safe_item = _convert_floats(item)
        # Remove None values (DynamoDB doesn't allow them)
        safe_item = {k: v for k, v in safe_item.items() if v is not None}

        try:
            dynamo_table.put_item(Item=safe_item)
            logger.debug("DynamoDB put_item", table=table, key=str(list(safe_item.keys())[:3]))
            return item
        except ClientError as e:
            logger.error("DynamoDB put_item failed", table=table, error=str(e))
            raise

    async def get_item(self, table: str, key: dict) -> Optional[dict]:
        """
        Get a single item by its key.

        Args:
            table: Table name
            key: Primary key dict (e.g., {"userId": "abc"} or {"userId": "abc", "projectId": "xyz"})

        Returns:
            Item dict or None if not found
        """
        dynamo_table = self._get_table(table)

        try:
            response = dynamo_table.get_item(Key=key)
            item = response.get("Item")
            if item:
                return _convert_decimals(item)
            return None
        except ClientError as e:
            logger.error("DynamoDB get_item failed", table=table, error=str(e))
            raise

    async def query(
        self,
        table: str,
        pk_name: str,
        pk_value: str,
        sk_name: Optional[str] = None,
        sk_value: Optional[str] = None,
        sk_begins_with: Optional[str] = None,
        filter_expression=None,
        limit: Optional[int] = None,
        scan_forward: bool = True,
    ) -> List[dict]:
        """
        Query items by partition key (and optionally sort key).

        Args:
            table: Table name
            pk_name: Partition key attribute name
            pk_value: Partition key value
            sk_name: Optional sort key name for additional filtering
            sk_value: Optional exact sort key value
            sk_begins_with: Optional sort key prefix
            filter_expression: Optional boto3 filter expression
            limit: Max items to return
            scan_forward: True for ascending, False for descending

        Returns:
            List of item dicts
        """
        dynamo_table = self._get_table(table)

        kwargs = {
            "KeyConditionExpression": Key(pk_name).eq(pk_value),
            "ScanIndexForward": scan_forward,
        }

        if sk_name and sk_value:
            kwargs["KeyConditionExpression"] = (
                Key(pk_name).eq(pk_value) & Key(sk_name).eq(sk_value)
            )
        elif sk_name and sk_begins_with:
            kwargs["KeyConditionExpression"] = (
                Key(pk_name).eq(pk_value) & Key(sk_name).begins_with(sk_begins_with)
            )

        if filter_expression:
            kwargs["FilterExpression"] = filter_expression

        if limit:
            kwargs["Limit"] = limit

        try:
            response = dynamo_table.query(**kwargs)
            items = response.get("Items", [])

            # Handle pagination if needed
            while "LastEvaluatedKey" in response and (limit is None or len(items) < limit):
                kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
                response = dynamo_table.query(**kwargs)
                items.extend(response.get("Items", []))

            return [_convert_decimals(item) for item in items]
        except ClientError as e:
            logger.error("DynamoDB query failed", table=table, error=str(e))
            raise

    async def delete_item(self, table: str, key: dict) -> None:
        """
        Delete an item by its key.

        Args:
            table: Table name
            key: Primary key dict
        """
        dynamo_table = self._get_table(table)

        try:
            dynamo_table.delete_item(Key=key)
            logger.debug("DynamoDB delete_item", table=table)
        except ClientError as e:
            logger.error("DynamoDB delete_item failed", table=table, error=str(e))
            raise

    async def update_item(
        self,
        table: str,
        key: dict,
        updates: dict,
    ) -> dict:
        """
        Update specific attributes of an item.

        Args:
            table: Table name
            key: Primary key dict
            updates: Dict of attribute names to new values

        Returns:
            Updated item attributes
        """
        dynamo_table = self._get_table(table)

        # Build update expression
        update_parts = []
        expression_names = {}
        expression_values = {}

        for i, (attr_name, attr_value) in enumerate(updates.items()):
            placeholder_name = f"#attr{i}"
            placeholder_value = f":val{i}"
            update_parts.append(f"{placeholder_name} = {placeholder_value}")
            expression_names[placeholder_name] = attr_name
            expression_values[placeholder_value] = _convert_floats(attr_value)

        # Remove None values from expression_values
        # For None values, use REMOVE instead
        set_parts = []
        remove_parts = []
        final_names = {}
        final_values = {}

        for i, (attr_name, attr_value) in enumerate(updates.items()):
            placeholder_name = f"#attr{i}"
            placeholder_value = f":val{i}"
            final_names[placeholder_name] = attr_name

            if attr_value is None:
                remove_parts.append(placeholder_name)
            else:
                set_parts.append(f"{placeholder_name} = {placeholder_value}")
                final_values[placeholder_value] = _convert_floats(attr_value)

        update_expression_parts = []
        if set_parts:
            update_expression_parts.append("SET " + ", ".join(set_parts))
        if remove_parts:
            update_expression_parts.append("REMOVE " + ", ".join(remove_parts))

        update_expression = " ".join(update_expression_parts)

        try:
            kwargs = {
                "Key": key,
                "UpdateExpression": update_expression,
                "ExpressionAttributeNames": final_names,
                "ReturnValues": "ALL_NEW",
            }
            if final_values:
                kwargs["ExpressionAttributeValues"] = final_values

            response = dynamo_table.update_item(**kwargs)
            return _convert_decimals(response.get("Attributes", {}))
        except ClientError as e:
            logger.error("DynamoDB update_item failed", table=table, error=str(e))
            raise

    async def scan(
        self,
        table: str,
        filter_expression=None,
        limit: Optional[int] = None,
    ) -> List[dict]:
        """
        Scan entire table (expensive — use sparingly).

        Args:
            table: Table name
            filter_expression: Optional boto3 filter
            limit: Max items

        Returns:
            List of item dicts
        """
        dynamo_table = self._get_table(table)

        kwargs = {}
        if filter_expression:
            kwargs["FilterExpression"] = filter_expression
        if limit:
            kwargs["Limit"] = limit

        try:
            response = dynamo_table.scan(**kwargs)
            items = response.get("Items", [])
            return [_convert_decimals(item) for item in items]
        except ClientError as e:
            logger.error("DynamoDB scan failed", table=table, error=str(e))
            raise

    @staticmethod
    def generate_id() -> str:
        """Generate a unique ID for DynamoDB items."""
        return str(uuid.uuid4())

    @staticmethod
    def now_iso() -> str:
        """Get current UTC timestamp in ISO format."""
        return datetime.utcnow().isoformat() + "Z"

    async def ensure_job_scout_tables(self):
        """Create UserJobStatuses and BlacklistedCompanies tables if they don't exist."""
        client = self._get_resource().meta.client
        try:
            existing = client.list_tables()["TableNames"]
        except ClientError:
            existing = []

        tables = {
            "UserJobStatuses": {
                "KeySchema": [
                    {"AttributeName": "userId", "KeyType": "HASH"},
                    {"AttributeName": "jobId", "KeyType": "RANGE"},
                ],
                "AttributeDefinitions": [
                    {"AttributeName": "userId", "AttributeType": "S"},
                    {"AttributeName": "jobId", "AttributeType": "S"},
                ],
            },
            "BlacklistedCompanies": {
                "KeySchema": [
                    {"AttributeName": "companyName", "KeyType": "HASH"},
                ],
                "AttributeDefinitions": [
                    {"AttributeName": "companyName", "AttributeType": "S"},
                ],
            },
        }

        for name, schema in tables.items():
            if name not in existing:
                try:
                    client.create_table(
                        TableName=name,
                        BillingMode="PAY_PER_REQUEST",
                        **schema,
                    )
                    logger.info(f"Created DynamoDB table: {name}")
                except ClientError as e:
                    if e.response["Error"]["Code"] != "ResourceInUseException":
                        logger.error(f"Failed to create table {name}: {e}")


# Global instance
dynamo_service = DynamoService()

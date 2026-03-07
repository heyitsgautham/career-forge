#!/usr/bin/env python3
"""
migrate_tokens_to_kms.py
========================
One-time migration: re-encrypt all Fernet-encrypted tokens in DynamoDB with AWS KMS.

Scans the Users table for rows that have an encrypted_token field whose value does NOT
start with the "KMS:" prefix (i.e., old Fernet ciphertext), decrypts with the legacy
Fernet encryptor, then re-encrypts with the KMS encryptor and writes back.

Safe to run multiple times — already-migrated rows are skipped.

Usage:
    cd project/backend
    /opt/anaconda3/bin/python scripts/migrate_tokens_to_kms.py [--dry-run]
"""

import sys
import argparse
import logging

# Add project root to path
sys.path.insert(0, ".")

import boto3
from app.core.config import settings
from app.core.security import KmsTokenEncryptor, TokenEncryptor

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_KMS_PREFIX = "KMS:"
_TABLES = ["Users"]                             # DynamoDB tables to migrate
_TOKEN_FIELDS = ["githubToken", "linkedinToken"] # Attribute names that hold encrypted tokens


def migrate(dry_run: bool = False, original_secret_key: str = None) -> None:
    dynamo = boto3.resource("dynamodb", region_name=settings.AWS_REGION)
    kms_enc = KmsTokenEncryptor()

    # The Fernet fallback MUST use the key that originally encrypted the tokens,
    # NOT the current settings.SECRET_KEY (which may now point to Secrets Manager).
    # Pass --original-key if the default "change-me-in-production" was overridden.
    original_key = original_secret_key or "change-me-in-production"
    fernet_enc = TokenEncryptor(secret_key=original_key)
    logger.info("Using original Fernet key derived from: %s", original_key[:8] + "...")

    total_scanned = 0
    total_migrated = 0
    total_skipped = 0
    total_errors = 0

    for table_name in _TABLES:
        table = dynamo.Table(table_name)

        paginator = boto3.client("dynamodb", region_name=settings.AWS_REGION).get_paginator("scan")
        pages = paginator.paginate(TableName=table_name)

        for page in pages:
            for raw_item in page["Items"]:
                # boto3 resource scan returns unmarshalled items; use the table directly
                pass

        # Use table.scan for proper unmarshalling
        scan_kwargs: dict = {}
        while True:
            response = table.scan(**scan_kwargs)
            items = response.get("Items", [])
            total_scanned += len(items)

            for item in items:
                user_id = item.get("userId") or item.get("user_id") or item.get("id", "<unknown>")

                for field in _TOKEN_FIELDS:
                    ciphertext = item.get(field)
                    if not ciphertext or not isinstance(ciphertext, str):
                        continue

                    if ciphertext.startswith(_KMS_PREFIX):
                        total_skipped += 1
                        logger.debug("SKIP user=%s field=%s (already KMS)", user_id, field)
                        continue

                    # Fernet-encrypted — migrate
                    try:
                        plaintext = fernet_enc.decrypt(ciphertext)
                        new_ciphertext = kms_enc.encrypt(plaintext)
                    except Exception as exc:
                        total_errors += 1
                        logger.error("ERROR user=%s field=%s: %s", user_id, field, exc)
                        continue

                    if dry_run:
                        logger.info("DRY-RUN  user=%s field=%s — would re-encrypt", user_id, field)
                    else:
                        key_attrs = {s["AttributeName"]: item[s["AttributeName"]]
                                     for s in table.key_schema}
                        table.update_item(
                            Key=key_attrs,
                            UpdateExpression=f"SET {field} = :v",
                            ExpressionAttributeValues={":v": new_ciphertext},
                        )
                        logger.info("MIGRATED user=%s field=%s", user_id, field)

                    total_migrated += 1

            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            scan_kwargs["ExclusiveStartKey"] = last_key

    logger.info(
        "\nDone%s — scanned=%d  migrated=%d  skipped=%d  errors=%d",
        " (DRY RUN)" if dry_run else "",
        total_scanned,
        total_migrated,
        total_skipped,
        total_errors,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate Fernet tokens to KMS in DynamoDB")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    parser.add_argument(
        "--original-key",
        default="change-me-in-production",
        help="The SECRET_KEY that was used when tokens were originally encrypted (default: change-me-in-production)",
    )
    args = parser.parse_args()
    migrate(dry_run=args.dry_run, original_secret_key=args.original_key)

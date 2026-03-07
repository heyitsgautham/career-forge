# AWS Security Implementation: KMS + Secrets Manager

**Status:** Live in production as of 2026-03-08  
**Account:** `602664593597` (us-east-1)

---

## Overview

CareerForge uses two AWS security services in tandem:

| Service | Purpose |
|---|---|
| **AWS KMS** | Encrypts user OAuth tokens (GitHub, LinkedIn) stored in DynamoDB |
| **AWS Secrets Manager** | Stores application secrets (JWT key, app key, OAuth secrets) loaded at startup |

---

## AWS Resources

### KMS Customer Managed Key

| Property | Value |
|---|---|
| Key alias | `alias/careerforge-tokens` |
| Key ID | `d2c68fae-4c0f-4d46-a995-d5c1af4b8b87` |
| Region | `us-east-1` |
| Key usage | `ENCRYPT_DECRYPT` |
| Key spec | `SYMMETRIC_DEFAULT` (AES-256-GCM) |

### Secrets Manager Secrets

| Secret name | Mapped to `settings.*` | Description |
|---|---|---|
| `careerforge/jwt-secret-key` | `JWT_SECRET_KEY` | JWT HS256 signing key (32-byte random) |
| `careerforge/app-secret-key` | `SECRET_KEY` | App secret / Fernet fallback key |
| `careerforge/github-app-private-key` | (loaded directly in `github_service.py`) | GitHub App RS256 PEM private key |
| `careerforge/github-app-client-secret` | `GITHUB_APP_CLIENT_SECRET` | GitHub App OAuth client secret |
| `careerforge/cognito-app-client-secret` | `COGNITO_APP_CLIENT_SECRET` | Cognito App client secret |

---

## Architecture

### Token Encryption Flow (KMS)

```
User logs in via GitHub OAuth
           │
           ▼
     auth.py route
           │  token_encryptor.encrypt(github_token)
           ▼
   KmsTokenEncryptor.encrypt()
           │  boto3 → kms.encrypt(KeyId="alias/careerforge-tokens", Plaintext=...)
           ▼
   Ciphertext blob → base64 encoded
   Stored in DynamoDB Users table as:
   { "githubToken": "KMS:AQIC..." }
           │
           ▼
   When token needed: token_encryptor.decrypt("KMS:AQIC...")
           │  boto3 → kms.decrypt(CiphertextBlob=...)
           ▼
   Plaintext token returned to caller (never persisted)
```

**Key property:** The plaintext key material never exists in application memory or storage — only in KMS HSMs.

### Secrets Manager Flow (startup)

```
FastAPI app starts
        │
        ▼
  Settings.__init__ (pydantic)
        │  reads .env / environment variables first
        ▼
  model_validator(mode="after") fires
        │  boto3 → secretsmanager.get_secret_value(SecretId=...)
        │  Overrides: JWT_SECRET_KEY, SECRET_KEY,
        │             GITHUB_APP_CLIENT_SECRET, COGNITO_APP_CLIENT_SECRET
        ▼
  settings.JWT_SECRET_KEY = <value from SM>  (never from .env in production)
        │
        ▼
  App ready — all secrets live only in process memory
```

**Fallback:** If Secrets Manager is unreachable (local dev without AWS creds), the `.env` values are used automatically. A warning is logged.

---

## Code Location

| File | What it does |
|---|---|
| [app/core/security.py](../project/backend/app/core/security.py) | `KmsTokenEncryptor` class + `TokenEncryptor` Fernet fallback |
| [app/core/config.py](../project/backend/app/core/config.py) | `Settings.model_validator` — loads SM secrets at startup |
| [app/core/__init__.py](../project/backend/app/core/__init__.py) | Exports `token_encryptor`, `KmsTokenEncryptor`, `TokenEncryptor` |
| [scripts/migrate_tokens_to_kms.py](../project/backend/scripts/migrate_tokens_to_kms.py) | One-time migration: re-encrypts legacy Fernet tokens to KMS |

### `KmsTokenEncryptor` — how it works

```python
# Encrypt (new tokens — always KMS)
ciphertext = token_encryptor.encrypt("ghp_abc123...")
# → "KMS:AQICAHi..."   (KMS: prefix + base64 blob)
# Stored in DynamoDB

# Decrypt (auto-detects KMS vs legacy Fernet)
plaintext = token_encryptor.decrypt("KMS:AQICAHi...")   # → KMS path
plaintext = token_encryptor.decrypt("gAAAAABp...")      # → Fernet fallback
```

The `"KMS:"` prefix allows the decryptor to distinguish between new KMS ciphertext and old Fernet ciphertext — enabling zero-downtime migration.

---

## Token Migration (completed 2026-03-08)

The migration re-encrypted all existing Fernet-encrypted `githubToken` / `linkedinToken` fields in DynamoDB with KMS.

**Result:** `scanned=9  migrated=4  skipped=0  errors=3`

- **4 migrated:** Tokens successfully re-encrypted with KMS  
- **3 errors:** Tokens encrypted with a different key (test/dev accounts) — users must re-authenticate; their tokens will be KMS-encrypted on next login automatically
- **Idempotent:** Running the script again shows `skipped=4` for already-migrated rows

To re-run (e.g., for new users with legacy tokens):
```bash
cd project/backend
/opt/anaconda3/bin/python scripts/migrate_tokens_to_kms.py --dry-run   # preview
/opt/anaconda3/bin/python scripts/migrate_tokens_to_kms.py              # execute
```

If the original `SECRET_KEY` was not `change-me-in-production`:
```bash
/opt/anaconda3/bin/python scripts/migrate_tokens_to_kms.py --original-key "your-old-key"
```

---

## Rotating Secrets

### Rotate JWT secret key (manual)
```bash
# Generate new key
NEW_KEY=$(openssl rand -base64 32)

# Update in Secrets Manager
aws secretsmanager put-secret-value \
  --secret-id careerforge/jwt-secret-key \
  --secret-string "$NEW_KEY" \
  --region us-east-1

# Restart the app — settings reload from SM on next startup
```

> **Note:** Rotating the JWT key invalidates all active sessions. Users must log in again.

### Rotate KMS key (automatic)
```bash
# Enable automatic annual rotation
aws kms enable-key-rotation \
  --key-id alias/careerforge-tokens \
  --region us-east-1
```

KMS handles key rotation transparently — existing ciphertext is re-encrypted automatically. No code changes needed.

### Update GitHub App client secret
```bash
aws secretsmanager put-secret-value \
  --secret-id careerforge/github-app-client-secret \
  --secret-string "new-secret-value" \
  --region us-east-1
```

---

## Setting up in a New Environment

### 1. Create KMS key
```bash
KEY_ID=$(aws kms create-key \
  --description "CareerForge token encryption at rest" \
  --region us-east-1 \
  --query 'KeyMetadata.KeyId' --output text)

aws kms create-alias \
  --alias-name alias/careerforge-tokens \
  --target-key-id "$KEY_ID" \
  --region us-east-1
```

### 2. Create Secrets Manager secrets
```bash
JWT_KEY=$(openssl rand -base64 32)
APP_KEY=$(openssl rand -base64 32)

aws secretsmanager create-secret \
  --name careerforge/jwt-secret-key \
  --secret-string "$JWT_KEY" --region us-east-1

aws secretsmanager create-secret \
  --name careerforge/app-secret-key \
  --secret-string "$APP_KEY" --region us-east-1

aws secretsmanager create-secret \
  --name careerforge/github-app-client-secret \
  --secret-string "<github-oauth-secret>" --region us-east-1

aws secretsmanager create-secret \
  --name careerforge/cognito-app-client-secret \
  --secret-string "<cognito-client-secret>" --region us-east-1

# Upload GitHub App PEM key
aws secretsmanager create-secret \
  --name careerforge/github-app-private-key \
  --secret-string file://path/to/private-key.pem --region us-east-1
```

### 3. IAM permissions required
The EC2 instance role / ECS task role / Lambda execution role needs:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey"],
      "Resource": "arn:aws:kms:us-east-1:602664593597:key/d2c68fae-4c0f-4d46-a995-d5c1af4b8b87"
    },
    {
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:us-east-1:602664593597:secret:careerforge/*"
    }
  ]
}
```

### 4. Set `.env`
```dotenv
AWS_REGION=us-east-1
KMS_KEY_ID=alias/careerforge-tokens

# SM secret names (not values — values are fetched at startup)
SM_JWT_SECRET_NAME=careerforge/jwt-secret-key
SM_APP_SECRET_NAME=careerforge/app-secret-key
SM_GITHUB_CLIENT_SECRET_NAME=careerforge/github-app-client-secret
SM_COGNITO_CLIENT_SECRET_NAME=careerforge/cognito-app-client-secret

# These are FALLBACK defaults only — SM values take priority when AWS is reachable
JWT_SECRET_KEY=change-me-in-production
SECRET_KEY=change-me-in-production
```

---

## Audit Trail

Every KMS `Encrypt` / `Decrypt` call is automatically logged in **AWS CloudTrail**:

```
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=Decrypt \
  --region us-east-1 \
  --start-time 2026-03-08T00:00:00Z
```

This gives a full audit of when and by which IAM principal each token was accessed.

---

## Cost

| Service | Usage | Cost |
|---|---|---|
| KMS CMK | 1 key | $1.00/month |
| KMS API calls | ~100K encrypt+decrypt/month | $0.30/month |
| Secrets Manager | 5 secrets | $2.00/month |
| Secrets Manager API calls | ~10K/month | $0.05/month |
| **Total** | | **~$3.35/month** |

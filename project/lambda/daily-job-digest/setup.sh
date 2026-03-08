#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup.sh — Deploy CareerForge Daily Job Digest Lambda via AWS SAM
#
# Prerequisites:
#   • AWS CLI configured  (aws configure)
#   • SAM CLI installed   (brew install aws/tap/aws-sam-cli)
#   • Python 3.12
#
# Usage:
#   cd project/lambda/daily-job-digest
#   chmod +x setup.sh && ./setup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

STACK_NAME="careerforge-daily-digest"
REGION="${AWS_REGION:-us-east-1}"
S3_BUCKET="${SAM_DEPLOY_BUCKET:-}"   # optional — SAM creates one if empty

# Recipient emails — taken from DEFAULT_RECIPIENT_EMAILS in .env (ref-repos)
# You can override via env: RECIPIENT_EMAILS="a@b.com,c@d.com,e@f.com"
RECIPIENT_EMAILS="${RECIPIENT_EMAILS:-krishnagoutham37@gmail.com,hiruviru18@gmail.com,kishorerose88@gmail.com}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " CareerForge — Daily Job Digest Setup"
echo " Stack  : $STACK_NAME"
echo " Region : $REGION"
echo " Emails : $RECIPIENT_EMAILS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Build (packages Lambda + dependencies) ─────────────────────────────
echo ""
echo "▶ sam build …"
sam build --template template.yaml

# ── 2. Deploy ─────────────────────────────────────────────────────────────
echo ""
echo "▶ sam deploy …"
sam deploy \
  --stack-name  "$STACK_NAME" \
  --region      "$REGION" \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --resolve-s3 \
  --parameter-overrides \
    "RecipientEmails=$RECIPIENT_EMAILS" \
  --no-fail-on-empty-changeset

# ── 3. Print outputs ──────────────────────────────────────────────────────
echo ""
echo "▶ Stack outputs:"
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region     "$REGION" \
  --query "Stacks[0].Outputs" \
  --output table

# ── 4. Reminder ───────────────────────────────────────────────────────────
echo ""
echo "✅  Deployment complete!"
echo ""
echo "⚠️  IMPORTANT: Each recipient will receive a"
echo "   'AWS Notification - Subscription Confirmation' email."
echo "   They must click the confirmation link before digest"
echo "   emails start arriving."
echo ""
echo "To test immediately (invoke Lambda manually):"
echo "  aws lambda invoke --function-name careerforge-daily-job-digest \\"
echo "    --region $REGION out.json && cat out.json"

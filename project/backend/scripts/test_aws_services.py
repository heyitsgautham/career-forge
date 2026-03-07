"""Quick AWS service verification for M1 migration."""
import boto3
import json
import sys

def main():
    passed = 0
    failed = 0
    
    # Test 1: Bedrock LLM
    print("=== Test 1: Bedrock LLM ===")
    try:
        bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": "Say hello in 5 words"}],
        })
        resp = bedrock.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0", body=body
        )
        result = json.loads(resp["body"].read())
        text = result["content"][0]["text"]
        print(f"  LLM Response: {text[:80]}")
        print("  PASS")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Test 2: Titan Embeddings
    print("\n=== Test 2: Titan Embeddings ===")
    try:
        embed_body = json.dumps({"inputText": "test embedding generation"})
        embed_resp = bedrock.invoke_model(
            modelId="amazon.titan-embed-text-v2:0", body=embed_body
        )
        embed_result = json.loads(embed_resp["body"].read())
        dims = len(embed_result["embedding"])
        print(f"  Embedding dimension: {dims} (expected: 1024)")
        assert dims == 1024, f"Expected 1024, got {dims}"
        print("  PASS")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Test 3: DynamoDB Tables
    print("\n=== Test 3: DynamoDB Tables ===")
    try:
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        tables = ["Users", "Projects", "Resumes", "Jobs", "Applications", "Roadmaps", "SkillGapReports"]
        for table_name in tables:
            table = dynamodb.Table(table_name)
            table.load()
            print(f"  {table_name}: OK (status={table.table_status})")
        print("  PASS")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Test 4: S3 Bucket
    print("\n=== Test 4: S3 Bucket ===")
    try:
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.head_bucket(Bucket="careerforge-pdfs-602664593597")
        print("  Bucket exists: careerforge-pdfs-602664593597")
        print("  PASS")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Test 5: Import app services
    print("\n=== Test 5: Import App Services ===")
    try:
        sys.path.insert(0, ".")
        from app.services.bedrock_client import bedrock_client
        from app.services.dynamo_service import dynamo_service
        from app.services.s3_service import s3_service
        print("  bedrock_client imported OK")
        print("  dynamo_service imported OK")
        print("  s3_service imported OK")
        print("  PASS")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)
    else:
        print("All tests passed!")

if __name__ == "__main__":
    main()

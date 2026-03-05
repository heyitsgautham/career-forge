"""Full end-to-end test of all AWS services via the app service layer."""
import sys
sys.path.insert(0, ".")
import asyncio

async def main():
    from app.services.bedrock_client import bedrock_client
    from app.services.dynamo_service import dynamo_service
    from app.services.s3_service import s3_service
    from app.core.config import get_settings

    s = get_settings()
    print(f"Config: MODEL={s.BEDROCK_MODEL_ID}, DYNAMO={s.USE_DYNAMO}, S3={s.S3_BUCKET}")
    
    passed = 0
    failed = 0

    # 1. LLM text generation
    print("\n--- Test 1: LLM Text Generation ---")
    try:
        r = await bedrock_client.generate("Say hello in exactly 3 words")
        print(f"  Response: {r[:80]}")
        passed += 1
        print("  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # 2. JSON generation
    print("\n--- Test 2: JSON Generation ---")
    try:
        j = await bedrock_client.generate_json('Return only this JSON object: {"status": "ok", "count": 42}')
        print(f"  Parsed: {j}")
        assert j.get("status") == "ok"
        passed += 1
        print("  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # 3. Embedding
    print("\n--- Test 3: Titan Embeddings ---")
    try:
        e = await bedrock_client.generate_embedding("test text for embedding")
        print(f"  Dimension: {len(e)} (expected 1024)")
        assert len(e) == 1024
        passed += 1
        print("  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # 4. DynamoDB CRUD
    print("\n--- Test 4: DynamoDB CRUD ---")
    try:
        test_id = "test-migration-verify"
        await dynamo_service.put_item("Users", {
            "userId": test_id,
            "email": "test@migration.com",
            "name": "Migration Test",
            "createdAt": dynamo_service.now_iso(),
        })
        u = await dynamo_service.get_item("Users", {"userId": test_id})
        assert u["email"] == "test@migration.com"
        print(f"  Put+Get: email={u['email']}")
        await dynamo_service.delete_item("Users", {"userId": test_id})
        gone = await dynamo_service.get_item("Users", {"userId": test_id})
        assert gone is None
        print("  Delete: confirmed gone")
        passed += 1
        print("  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # 5. S3 Upload + Presign + Delete
    print("\n--- Test 5: S3 Operations ---")
    try:
        key = "test/migration-verify.pdf"
        ok = await s3_service.upload_file(key=key, data=b"test pdf content here", content_type="application/pdf")
        assert ok  # returns s3:// URI string
        print("  Upload: OK")
        url = await s3_service.get_presigned_url(key)
        assert url and "migration-verify" in url
        print(f"  Presigned URL: {url[:80]}...")
        await s3_service.delete_file(key)
        exists = await s3_service.file_exists(key)
        assert not exists
        print("  Delete: confirmed gone")
        passed += 1
        print("  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Summary
    print(f"\n{'='*45}")
    print(f"Results: {passed}/5 passed, {failed}/5 failed")
    if failed == 0:
        print("ALL SERVICE TESTS PASSED!")
    else:
        print("SOME TESTS FAILED")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

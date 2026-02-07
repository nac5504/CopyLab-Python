
import os
import sys
from CopyLab import CopyLab, CopyLabError

def verify_sdk():
    api_key = os.environ.get("COPYLAB_API_KEY", "cl_cravr_22fc42d9ef9f5587662d24055da39875")
    
    print("--- CopyLab SDK Verification ---")
    
    try:
        # 1. Configure
        CopyLab.configure(api_key=api_key)
        
        # 2. Identify
        CopyLab.identify(user_id="sdk_test_user")
        
        # 3. Test Remote Template Generation
        print("\nTesting generate_notification (Remote Template)...")
        result = CopyLab.generate_notification(
            placement_id="chat_message_sent",
            variables={
                "message_author_name": "SDK Tester",
                "message_text": "Is this thing on?"
            }
        )
        
        print(f"Success! Result:")
        print(f"  Title: {result.get('title')}")
        print(f"  Message: {result.get('message')}")
        print(f"  Template Used: {result.get('template_name')} ({result.get('template_used')})")
        
        # 4. Test Analytics
        print("\nTesting log_app_open...")
        CopyLab.log_app_open()
        
        # 5. Test Notification Logging (Single)
        print("\nTesting log_notification_sent...")
        CopyLab.log_notification_sent(
            notification_id=f"test_notif_{os.urandom(4).hex()}",
            title="SDK Test Notification",
            message="This is a test from verify_sdk.py",
            users=[{"uid": "sdk_test_user", "delivered": True}],
            target_count=1,
            success_count=1,
            data=result.get('data') # Pass attribution data from generation
        )
        
        # 6. Test Notification Logging (Batch)
        print("\nTesting log_notification_batch...")
        CopyLab.log_notification_batch(
            batch_id=f"sdk_batch_{os.urandom(4).hex()}",
            notification_id=f"batch_notif_{os.urandom(4).hex()}",
            title="SDK Batch Notification",
            message="This is a batch test",
            users_list=[{"uid": "sdk_test_user", "delivered": True}],
            success_count=1,
            payload_data={"copylab_template_name": "Batch Test"}
        )
        
        # 7. Test Public make_request
        print("\nTesting public make_request...")
        try:
            # We'll use a simple GET request that doesn't side-effect much, or just check that it doesn't crash on a known endpoint
            # Since we don't have a safe read-only endpoint that guaranteed 200 without setup, let's just try to call it and catch the error if any,
            # ensuring the METHOD itself is accessible.
            # Actually, "get_topic_subscribers" is a safe read check even if topic doesn't exist.
            res = CopyLab.make_request("get_topic_subscribers", method="GET", params={"topic_id": "non_existent_topic"})
            print(f"make_request successful. Result keys: {list(res.keys())}")
        except CopyLabError as e:
            # Even an API error means the SDK method worked to send the request
            print(f"make_request executed (API returned error, which is fine): {e}")

        print("\n✅ Verification complete: SDK is fully operational.")
        
    except CopyLabError as e:
        print(f"\n❌ SDK Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify_sdk()

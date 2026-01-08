
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
        
        print("\n✅ Verification complete: SDK is fully operational.")
        
    except CopyLabError as e:
        print(f"\n❌ SDK Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify_sdk()

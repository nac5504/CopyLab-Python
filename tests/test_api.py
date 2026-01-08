"""
CopyLab API Integration Tests

These tests verify that the deployed Cloud Functions are properly connected 
to Firestore and functioning correctly.

Usage:
    # Set your API key
    export COPYLAB_API_KEY="cl_yourapp_xxx..."
    
    # Run all tests
    python -m pytest tests/ -v
    
    # Or run directly
    python tests/test_api.py
"""

import os
import sys
import time
import requests
import unittest
from uuid import uuid4

# Configuration
API_KEY = os.environ.get("COPYLAB_API_KEY", "")
BASE_URL = os.environ.get("COPYLAB_BASE_URL", "https://us-central1-copylab-3f220.cloudfunctions.net")
TIMEOUT = 30


class TestCopyLabAPI(unittest.TestCase):
    """Integration tests for CopyLab Cloud Functions API."""
    
    @classmethod
    def setUpClass(cls):
        if not API_KEY:
            print("\n⚠️  Warning: COPYLAB_API_KEY not set. Some tests may fail.")
            print("   Set it with: export COPYLAB_API_KEY='cl_yourapp_xxx...'\n")
        cls.test_user_id = f"test_user_{uuid4().hex[:8]}"
        cls.test_topic_id = f"test_topic_{uuid4().hex[:8]}"
    
    def _make_request(self, endpoint: str, method: str = "POST", body: dict = None, params: dict = None):
        """Helper to make API requests."""
        url = f"{BASE_URL}/{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": API_KEY
        }
        
        if method == "GET":
            response = requests.get(url, headers=headers, params=params, timeout=TIMEOUT)
        else:
            response = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
        
        return response
    
    # =========================================================================
    # API Key Validation Tests
    # =========================================================================
    
    def test_01_missing_api_key(self):
        """Test that requests without API key are rejected."""
        response = requests.post(
            f"{BASE_URL}/log_app_open",
            headers={"Content-Type": "application/json"},
            json={"user_id": "test"},
            timeout=TIMEOUT
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.json())
        print("✅ Missing API key correctly rejected")
    
    def test_02_invalid_api_key(self):
        """Test that invalid API keys are rejected."""
        response = requests.post(
            f"{BASE_URL}/log_app_open",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": "invalid_key_123"
            },
            json={"user_id": "test"},
            timeout=TIMEOUT
        )
        self.assertEqual(response.status_code, 401)
        print("✅ Invalid API key correctly rejected")
    
    # =========================================================================
    # Topic Subscription Tests
    # =========================================================================
    
    def test_10_subscribe_to_topic(self):
        """Test subscribing a user to a topic."""
        if not API_KEY:
            self.skipTest("API key not configured")
        
        response = self._make_request("subscribe_to_topic", body={
            "topic_id": self.test_topic_id,
            "user_id": self.test_user_id
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("success"))
        print(f"✅ Subscribed {self.test_user_id} to topic {self.test_topic_id}")
    
    def test_11_get_topic_subscribers(self):
        """Test getting topic subscribers."""
        if not API_KEY:
            self.skipTest("API key not configured")
        
        # Wait a moment for Firestore consistency
        time.sleep(1)
        
        response = self._make_request(
            "get_topic_subscribers",
            method="GET",
            params={"topic_id": self.test_topic_id}
        )
        
        self.assertEqual(response.status_code, 200)
        subscribers = response.json().get("subscriber_ids", [])
        self.assertIn(self.test_user_id, subscribers)
        print(f"✅ Retrieved {len(subscribers)} subscribers for topic {self.test_topic_id}")
    
    def test_12_unsubscribe_from_topic(self):
        """Test unsubscribing a user from a topic."""
        if not API_KEY:
            self.skipTest("API key not configured")
        
        response = self._make_request("unsubscribe_from_topic", body={
            "topic_id": self.test_topic_id,
            "user_id": self.test_user_id
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("success"))
        print(f"✅ Unsubscribed {self.test_user_id} from topic {self.test_topic_id}")
    
    # =========================================================================
    # Analytics Tests
    # =========================================================================
    
    def test_20_log_app_open(self):
        """Test logging an app open event."""
        if not API_KEY:
            self.skipTest("API key not configured")
        
        response = self._make_request("log_app_open", body={
            "user_id": self.test_user_id,
            "platform": "python_test"
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("success"))
        print(f"✅ Logged app_open for {self.test_user_id}")
    
    def test_21_log_push_open(self):
        """Test logging a push notification open event."""
        if not API_KEY:
            self.skipTest("API key not configured")
        
        response = self._make_request("log_push_open", body={
            "user_id": self.test_user_id,
            "platform": "python_test",
            "notification_id": f"test_notif_{uuid4().hex[:8]}",
            "placement_id": "test_placement"
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("success"))
        print(f"✅ Logged push_open for {self.test_user_id}")
    
    def test_22_sync_notification_permission(self):
        """Test syncing notification permission status."""
        if not API_KEY:
            self.skipTest("API key not configured")
        
        response = self._make_request("sync_notification_permission", body={
            "user_id": self.test_user_id,
            "notification_status": "authorized",
            "platform": "python_test"
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("success"))
        print(f"✅ Synced notification permission for {self.test_user_id}")
    
    # =========================================================================
    # Generate Notification Tests
    # =========================================================================
    
    def test_30_generate_notification_with_fallback(self):
        """Test generating a notification with fallback values."""
        if not API_KEY:
            self.skipTest("API key not configured")
        
        response = self._make_request("generate_notification", body={
            "placement_id": "nonexistent_placement",
            "variables": {"user_name": "TestUser"},
            "fallback_title": "Hello {user_name}!",
            "fallback_message": "This is a test notification."
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Should return fallback since placement doesn't exist
        self.assertIn("title", data)
        self.assertIn("message", data)
        print(f"✅ Generated notification: {data.get('title', 'N/A')}")


def run_tests():
    """Run all tests and print summary."""
    print("\n" + "=" * 60)
    print("CopyLab API Integration Tests")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"API Key:  {'Configured ✓' if API_KEY else 'NOT SET ✗'}")
    print("=" * 60 + "\n")
    
    # Run tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestCopyLabAPI)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures:  {len(result.failures)}")
    print(f"Errors:    {len(result.errors)}")
    print(f"Skipped:   {len(result.skipped)}")
    print("=" * 60)
    
    return len(result.failures) == 0 and len(result.errors) == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

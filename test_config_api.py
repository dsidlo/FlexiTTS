#!/usr/bin/env python3
"""
Quick test script for FlexiTTS Configuration API
"""

import requests
import json
import time


def test_api():
    base_url = "http://127.0.0.1:8000"
    
    print("Testing FlexiTTS Configuration API...")
    
    try:
        # Test health endpoint
        response = requests.get(f"{base_url}/api/system/health")
        if response.status_code == 200:
            print("✓ Health check passed")
            health = response.json()
            print(f"  Status: {health['status']}")
        else:
            print(f"✗ Health check failed: {response.status_code}")
            return False
        
        # Test system info
        response = requests.get(f"{base_url}/api/system/info")
        if response.status_code == 200:
            print("✓ System info retrieved")
            info = response.json()
            config_status = info['configStatus']
            print(f"  Global config exists: {config_status['globalConfigExists']}")
            print(f"  Stories discovered: {config_status['storiesDiscovered']}")
        else:
            print(f"✗ System info failed: {response.status_code}")
        
        # Test stories discovery
        response = requests.get(f"{base_url}/api/stories")
        if response.status_code == 200:
            print("✓ Stories discovery successful")
            stories = response.json()
            print(f"  Found {stories['totalCount']} stories")
            if stories['stories']:
                print(f"  First story: {stories['stories'][0]['displayName']}")
        else:
            print(f"✗ Stories discovery failed: {response.status_code}")
        
        # Test global config
        response = requests.get(f"{base_url}/api/config/global")
        if response.status_code == 200:
            print("✓ Global config loaded")
        else:
            print(f"✗ Global config failed: {response.status_code}")
        
        print("\nAPI test completed successfully!")
        return True
        
    except requests.ConnectionError:
        print("✗ Could not connect to API. Make sure it's running:")
        print("  python start_config_api.py")
        return False
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        return False


if __name__ == "__main__":
    test_api()

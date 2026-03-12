#!/usr/bin/env python3
"""
Test script to verify Celery setup
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.tasks.celery_app import celery_app
from app.tasks.daily_tasks import debug_task

def test_celery():
    """Test Celery setup"""
    print("Testing Celery setup...")
    
    # Send a test task
    result = debug_task.delay()
    print(f"Task sent with ID: {result.id}")
    
    try:
        # Wait for result (timeout 30 seconds)
        task_result = result.get(timeout=30)
        print(f"✅ Task completed successfully: {task_result}")
        return True
    except Exception as e:
        print(f"❌ Task failed: {str(e)}")
        return False

if __name__ == '__main__':
    success = test_celery()
    sys.exit(0 if success else 1)

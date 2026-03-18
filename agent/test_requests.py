#!/usr/bin/env python
"""
Simple test to debug Ollama connection
"""

import json

import requests

OLLAMA_HOST = "http://localhost:11434"

print("=" * 60)
print("Testing Ollama Connection with requests library")
print("=" * 60 + "\n")

# Test 1: Check if Ollama is running
try:
    response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
    print(f"✓ Ollama API responded with status: {response.status_code}")
    models = response.json().get("models", [])
    print(f"✓ Available models: {[m['name'] for m in models]}\n")
except Exception as e:
    print(f"✗ Failed to connect: {e}\n")
    exit(1)

# Test 2: Try a simple chat message
print("Testing chat with qwen3:8b...\n")
try:
    chat_data = {
        "model": "qwen3:8b",
        "messages": [{"role": "user", "content": "What is 2+2?"}],
        "stream": False,
    }

    response = requests.post(f"{OLLAMA_HOST}/api/chat", json=chat_data, timeout=30)
    print(f"✓ Chat API responded with status: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"✓ Response: {result.get('message', {}).get('content', 'No content')}\n")
    else:
        print(f"✗ Error: {response.text}\n")

except Exception as e:
    print(f"✗ Chat failed: {e}\n")

#!/usr/bin/env python
"""Test script for LangChain-based agent"""

import sys

sys.path.insert(0, "/Users/lewisgong/code/agent-lab/agent")

from agent import IntegratedAgent

print("\n" + "=" * 70)
print("Testing LangChain Agent with Ollama")
print("=" * 70 + "\n")

try:
    # Initialize agent
    print("1. Initializing agent with Ollama provider...")
    agent = IntegratedAgent(provider="ollama")
    print("   ✓ Agent initialized\n")

    # Verify connection
    print("2. Verifying connection...")
    if not agent.verify_connection():
        print("   ✗ Connection verification failed")
        sys.exit(1)
    print("   ✓ Connection verified\n")

    # Test first message
    print("3. Testing first message...")
    response1 = agent.chat("What is Python?")
    print(f"   Response: {response1[:200]}...\n")

    # Test conversation memory
    print("4. Testing conversation memory...")
    response2 = agent.chat("What about Java?")
    print(f"   Response: {response2[:200]}...\n")

    # Test memory retrieval
    print("5. Showing conversation history...")
    history = agent.get_memory()
    print(f"   History:\n{history}\n")

    # Test memory clear
    print("6. Testing memory clear...")
    agent.clear_memory()
    print("   ✓ Memory cleared\n")

    print("=" * 70)
    print("✓ All LangChain agent tests PASSED")
    print("=" * 70 + "\n")

except Exception as e:
    print(f"\n✗ Test failed: {e}\n")
    import traceback

    traceback.print_exc()
    sys.exit(1)

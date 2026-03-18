#!/usr/bin/env python
"""
Quick test script to verify agent can connect to Ollama
"""

import sys

sys.path.insert(0, "/Users/lewisgong/code/agent-lab/agent")

from agent import IntegratedAgent

# Test connection
agent = IntegratedAgent()

print("\n" + "=" * 60)
print("Testing Agent Connection...")
print("=" * 60 + "\n")

if agent.verify_connection():
    print("\n✓ Connection test PASSED\n")

    # Test a simple query
    print("Testing agent with a simple query...")
    response = agent.chat("What is 2+2?")
    print(f"Response: {response}\n")
else:
    print("\n✗ Connection test FAILED\n")
    sys.exit(1)

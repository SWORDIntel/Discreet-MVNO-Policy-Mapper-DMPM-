#!/usr/bin/env python3
"""AI Assistant Integration Examples for GHOST DMPM"""
import asyncio
from mcp_client import GhostMCPClient
from ghost_mcp_nlp import GhostNLPProcessor

# Example 1: Claude/ChatGPT Context
AI_CONTEXT = """
You have access to GHOST DMPM (Discreet MVNO Policy Mapper) via natural language.
This system tracks US mobile carriers that allow anonymous SIM purchases.

Connection: ws://localhost:8765
Token: ghost-mcp-2024

Example queries you can ask:
- "Which carriers don't require ID?"
- "Check [carrier name] policy"
- "What changed recently?"
- "Show [carrier] trends"
- "System status"

The system will return formatted responses with anonymity scores (0-5):
- 5 = No ID required, cash payment OK
- 4 = Minimal verification
- 3 = Basic verification only
- 2 = Standard verification
- 1 = Enhanced verification
- 0 = Strict ID requirements
"""

async def demo_for_ai_assistant():
    """Demonstrate usage for AI assistants"""
    print("=== AI Assistant Integration Demo ===\n")
    print("Add this to your AI context:")
    print("-" * 50)
    print(AI_CONTEXT)
    print("-" * 50)
    print("\nThen use natural language queries...\n")

    # Ensure mcp_client is initialized correctly, assuming it handles ws URL and token by default
    # or from environment variables / config file as per its design.
    # If explicit configuration is needed:
    # client = GhostMCPClient(url="ws://localhost:8765", token="ghost-mcp-2024")
    client = GhostMCPClient()
    nlp = GhostNLPProcessor()

    # Simulate AI queries
    ai_queries = [
        "I need an anonymous phone. What are my options?",
        "Is Mint Mobile good for privacy?",
        "Have any carriers gotten stricter recently?",
        "What's the most anonymous carrier right now?"
    ]

    try:
        await client.connect()

        for query in ai_queries:
            print(f"\n🤖 AI: {query}")

            # Parse and execute
            method, params = nlp.parse_query(query)
            # Ensure that the client is connected before making a query
            if not client.websocket or not client.websocket.open:
                print("Error: Client not connected. Attempting to reconnect...")
                await client.connect() # Reconnect if necessary
                if not client.websocket or not client.websocket.open:
                    print("Error: Failed to reconnect. Skipping query.")
                    continue

            result = await client.query(method, params)

            # Format response
            response_data = result.get("result", {})
            if result.get("error"): # Handle top-level errors from query if any
                response_data = {"error": result.get("error_message", "Unknown error from MCP")}

            response = nlp.format_response(method, response_data) # Pass the actual result dict
            print(f"\n📊 GHOST DMPM:\n{response}")

            # Show follow-up suggestions
            suggestions = nlp.get_suggested_followups(method, response_data) # Pass the actual result dict
            if suggestions:
                print(f"\n💡 Suggested follow-ups:")
                for s in suggestions:
                    print(f"  • {s}")

    except Exception as e:
        print(f"An error occurred during AI demo: {e}")
    finally:
        if client.websocket and client.websocket.open:
            await client.close()

# Example 2: Operational Scenarios
async def operational_use_cases():
    """Real-world operational scenarios"""
    print("\n\n=== Operational Use Cases ===\n")

    client = GhostMCPClient()
    nlp = GhostNLPProcessor()

    scenarios = [
        {
            "name": "Emergency Burner Phone",
            "query": "I need a phone TODAY with no ID. What's my best option?",
            "action": "Find top carrier and nearest store"
        },
        {
            "name": "Bulk Acquisition Planning",
            "query": "Which 3 carriers should I use for 10 anonymous SIMs?",
            "action": "Diversify across top lenient carriers"
        },
        {
            "name": "Policy Monitoring",
            "query": "Alert me if any good carriers tighten their policies",
            "action": "Check recent alerts for POLICY_TIGHTENED"
        }
    ]

    try:
        await client.connect()

        for scenario in scenarios:
            print(f"\n📋 Scenario: {scenario['name']}")
            print(f"❓ Query: {scenario['query']}")
            print(f"🎯 Action: {scenario['action']}")

            # Process query
            method, params = nlp.parse_query(scenario['query'])
            if not client.websocket or not client.websocket.open:
                await client.connect()

            result = await client.query(method, params)

            # Show result
            response_data = result.get("result", {})
            if result.get("error"):
                 response_data = {"error": result.get("error_message", "Unknown error from MCP")}

            response = nlp.format_response(method, response_data)
            print(f"\n{response[:200]}...")  # First 200 chars

    except Exception as e:
        print(f"An error occurred during operational use cases: {e}")
    finally:
        if client.websocket and client.websocket.open:
            await client.close()

# Example 3: Conversational Flow
async def conversational_example():
    """Show multi-turn conversation"""
    print("\n\n=== Conversational Flow Example ===\n")

    client = GhostMCPClient()
    nlp = GhostNLPProcessor()

    conversation = [
        "Hi, I need help finding an anonymous phone carrier",
        "What's the best option right now?",
        "Tell me more about US Mobile",
        "Has their policy changed recently?",
        "What about Cricket?",
        "Thanks, that's helpful!"
    ]

    try:
        await client.connect()

        for turn, query in enumerate(conversation):
            print(f"\n👤 User: {query}")

            # Check if it's a substantive query
            if any(word in query.lower() for word in ["what", "tell", "has", "about", "best option"]):
                method, params = nlp.parse_query(query)
                if not client.websocket or not client.websocket.open:
                    await client.connect()

                result = await client.query(method, params)
                response_data = result.get("result", {})
                if result.get("error"):
                    response_data = {"error": result.get("error_message", "Unknown error from MCP")}

                response = nlp.format_response(method, response_data)
                print(f"\n🤖 Assistant: {response[:300]}...")
            else:
                # Handle greetings/thanks
                if "hi" in query.lower() or "help" in query.lower():
                    print("\n🤖 Assistant: I can help you find anonymous phone carriers. Ask me about carriers that don't require ID, recent policy changes, or specific MVNOs.")
                elif "thanks" in query.lower():
                    print("\n🤖 Assistant: You're welcome! Stay safe and anonymous. Remember to check back for policy updates.")

    except Exception as e:
        print(f"An error occurred during conversational example: {e}")
    finally:
        if client.websocket and client.websocket.open:
            await client.close()

if __name__ == "__main__":
    # Run all examples
    # It's better to run them sequentially to avoid issues if they share resources or if client has issues with rapid re-connections.
    async def main():
        await demo_for_ai_assistant()
        await operational_use_cases()
        await conversational_example()

    asyncio.run(main())

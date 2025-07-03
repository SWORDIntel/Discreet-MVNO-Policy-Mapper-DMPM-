# AI Platform Integration Guide

This guide covers integrating GHOST DMPM with major AI platforms for enhanced conversational intelligence gathering.

## Table of Contents
- [Overview](#overview)
- [OpenAI Integration](#openai-integration)
- [Claude Integration](#claude-integration)
- [Google Gemini Integration](#google-gemini-integration)
- [Comparison Matrix](#comparison-matrix)
- [Best Practices](#best-practices)

## Overview

GHOST DMPM provides multiple integration methods for AI assistants:
1. **MCP Server** - WebSocket API with natural language support
2. **REST API** - HTTP endpoints via the web dashboard
3. **Direct Python** - Import modules directly in Python environments

### Prerequisites
- GHOST DMPM running with MCP server enabled
- API keys for your chosen AI platform
- Network access between AI platform and GHOST DMPM

## OpenAI Integration

### Method 1: Function Calling (Recommended)

```python
import openai
from mcp_client import GhostMCPClient

# Configure OpenAI
openai.api_key = "your-openai-api-key"

# Define GHOST DMPM functions for OpenAI
ghost_functions = [
    {
        "name": "query_ghost_dmpm",
        "description": "Query GHOST DMPM for MVNO carrier information",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query about MVNOs"
                }
            },
            "required": ["query"]
        }
    }
]

async def handle_ghost_query(query):
    """Handle GHOST DMPM queries via MCP"""
    client = GhostMCPClient()
    await client.connect()

    # Use NLP to parse query
    from ghost_mcp_nlp import GhostNLPProcessor
    nlp = GhostNLPProcessor()
    method, params = nlp.parse_query(query)

    # Execute query
    result = await client.query(method, params)
    await client.close()

    # Format response
    return nlp.format_response(method, result.get("result", {}))

# Example conversation
async def openai_conversation():
    messages = [
        {"role": "system", "content": "You help users find anonymous phone carriers using GHOST DMPM."},
        {"role": "user", "content": "I need an anonymous phone. What are my options?"}
    ]

    response = await openai.ChatCompletion.create(
        model="gpt-4",
        messages=messages,
        functions=ghost_functions,
        function_call="auto"
    )

    # Handle function call
    if response.choices[0].message.get("function_call"):
        function_args = json.loads(response.choices[0].message.function_call.arguments)
        ghost_result = await handle_ghost_query(function_args["query"])

        # Add function result to conversation
        messages.append(response.choices[0].message)
        messages.append({
            "role": "function",
            "name": "query_ghost_dmpm",
            "content": ghost_result
        })

        # Get final response
        final_response = await openai.ChatCompletion.create(
            model="gpt-4",
            messages=messages
        )

        return final_response.choices[0].message.content
```

### Method 2: Custom GPT Configuration

```json
{
  "name": "GHOST DMPM Assistant",
  "description": "Expert on anonymous phone carriers and MVNOs",
  "instructions": "You have access to GHOST DMPM (Discreet MVNO Policy Mapper). Use the query_ghost_dmpm action to get real-time information about carrier policies.",
  "actions": [
    {
      "type": "function",
      "function": {
        "name": "query_ghost_dmpm",
        "description": "Query the GHOST DMPM system",
        "parameters": {
          "type": "object",
          "properties": {
            "query": {
              "type": "string",
              "description": "Natural language query"
            }
          }
        },
        "url": "https://your-domain.com/api/mcp/query"
      }
    }
  ]
}
```

### Method 3: Assistants API

```python
from openai import OpenAI

client = OpenAI()

# Create assistant with GHOST DMPM knowledge
assistant = client.beta.assistants.create(
    name="GHOST DMPM Analyst",
    instructions="""You are an expert on anonymous phone carriers. You have access to GHOST DMPM
    which tracks US MVNOs and their identity verification policies. Use the provided functions
    to query real-time data about carriers.""",
    tools=[{
        "type": "function",
        "function": {
            "name": "query_ghost_dmpm",
            "description": "Query GHOST DMPM for carrier information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    }],
    model="gpt-4-1106-preview"
)

# Run conversation
thread = client.beta.threads.create()
message = client.beta.threads.messages.create(
    thread_id=thread.id,
    role="user",
    content="Which carriers allow cash payment without ID?"
)

run = client.beta.threads.runs.create(
    thread_id=thread.id,
    assistant_id=assistant.id
)
```

## Claude Integration

### Method 1: Tool Use (Recommended)

```python
import anthropic
from mcp_client import GhostMCPClient

client = anthropic.Anthropic(api_key="your-claude-api-key")

# Define GHOST DMPM tool
ghost_tool = {
    "name": "query_ghost_dmpm",
    "description": "Query GHOST DMPM for anonymous carrier information",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language query about MVNOs"
            }
        },
        "required": ["query"]
    }
}

async def claude_with_ghost():
    message = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=1000,
        tools=[ghost_tool],
        messages=[{
            "role": "user",
            "content": "I need to buy 5 anonymous SIM cards. What's my best strategy?"
        }]
    )

    # Handle tool use
    if message.content[0].type == "tool_use":
        tool_use = message.content[0]

        # Query GHOST DMPM
        ghost_client = GhostMCPClient()
        await ghost_client.connect()

        from ghost_mcp_nlp import GhostNLPProcessor
        nlp = GhostNLPProcessor()
        method, params = nlp.parse_query(tool_use.input["query"])

        result = await ghost_client.query(method, params)
        formatted = nlp.format_response(method, result.get("result", {}))

        await ghost_client.close()

        # Continue conversation with tool result
        response = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1000,
            messages=[
                {"role": "user", "content": "I need to buy 5 anonymous SIM cards. What's my best strategy?"},
                {"role": "assistant", "content": message.content},
                {
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": formatted
                    }]
                }
            ]
        )

        return response.content[0].text
```

### Method 2: Project Knowledge

```markdown
# Add to Claude Project Knowledge

## GHOST DMPM Integration

You have access to GHOST DMPM (Discreet MVNO Policy Mapper) via MCP.

### Connection Details
- WebSocket URL: ws://localhost:8765
- Authentication: Token-based (ghost-mcp-2024)

### Available Queries
1. "Which carriers don't require ID?"
2. "Check [carrier] policy"
3. "Recent policy changes"
4. "Show [carrier] trends"
5. "System status"

### Scoring System
- 5.0 = No ID required, cash payment accepted
- 4.0+ = Minimal verification
- 3.0-3.9 = Basic verification
- 2.0-2.9 = Standard verification
- <2.0 = Strict requirements

### Usage Pattern
When users ask about anonymous phones, query GHOST DMPM for current data.
```

### Method 3: MCP Direct Integration

```python
# Claude can directly connect to MCP servers
# Configure in Claude's settings:

{
    "mcp_servers": {
        "ghost_dmpm": {
            "url": "ws://your-server:8765",
            "token": "ghost-mcp-2024",
            "capabilities": ["query", "natural_language"]
        }
    }
}
```

## Google Gemini Integration

### Method 1: Function Declarations

```python
import google.generativeai as genai

genai.configure(api_key="your-gemini-api-key")

# Define GHOST DMPM function
query_ghost = genai.FunctionDeclaration(
    name="query_ghost_dmpm",
    description="Query GHOST DMPM for anonymous carrier information",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language query about MVNOs"
            }
        },
        "required": ["query"]
    }
)

# Create model with function
model = genai.GenerativeModel(
    'gemini-pro',
    tools=[query_ghost]
)

async def gemini_conversation():
    chat = model.start_chat()

    response = chat.send_message(
        "What are the best carriers for anonymous activation?"
    )

    # Handle function call
    for part in response.parts:
        if part.function_call:
            # Query GHOST DMPM
            ghost_result = await handle_ghost_query(
                part.function_call.args["query"]
            )

            # Send function response
            response = chat.send_message(
                genai.FunctionResponse(
                    name="query_ghost_dmpm",
                    response={"result": ghost_result}
                )
            )

    return response.text
```

### Method 2: Grounding with External Data

```python
# Configure Gemini to use GHOST DMPM as external knowledge
model = genai.GenerativeModel(
    'gemini-pro',
    system_instruction="""You are an expert on anonymous phone carriers.
    You have access to GHOST DMPM which provides real-time data on MVNO policies.
    Always query current data before making recommendations."""
)

# Add GHOST data as context
ghost_context = await get_current_ghost_data()
response = model.generate_content([
    "User needs anonymous phone options",
    f"Current GHOST DMPM data: {ghost_context}"
])
```

### Method 3: Vertex AI Integration

```python
from google.cloud import aiplatform
from vertexai.preview.generative_models import GenerativeModel, Tool

# Define GHOST DMPM tool for Vertex
ghost_tool = Tool(
    function_declarations=[{
        "name": "query_ghost_dmpm",
        "description": "Query GHOST DMPM system",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            }
        }
    }]
)

model = GenerativeModel(
    "gemini-pro",
    tools=[ghost_tool]
)

response = model.generate_content(
    "Find carriers that accept cash without ID",
    generation_config={"temperature": 0.1}
)
```

## Comparison Matrix

| Feature | OpenAI | Claude | Gemini |
|---------|---------|---------|---------|
| Function Calling | ✅ Native | ✅ Tool Use | ✅ Function Declarations |
| Streaming | ✅ Yes | ✅ Yes | ✅ Yes |
| Context Window | 128k (GPT-4) | 200k (Claude 3) | 1M (Gemini 1.5) |
| Response Time | Fast | Fast | Moderate |
| Natural Language | Excellent | Excellent | Very Good |
| Cost | $$ | $$$ | $ |
| Best For | General queries | Complex analysis | Large context |

## Best Practices

### 1. Authentication & Security
```python
# Store credentials securely
import os
from cryptography.fernet import Fernet

class SecureConfig:
    def __init__(self):
        self.cipher = Fernet(os.environ['GHOST_ENCRYPTION_KEY'])

    def get_api_key(self, service):
        encrypted = os.environ.get(f'{service.upper()}_API_KEY')
        return self.cipher.decrypt(encrypted.encode()).decode()
```

### 2. Error Handling
```python
async def safe_ghost_query(query, max_retries=3):
    """Query GHOST with retry logic"""
    for attempt in range(max_retries):
        try:
            client = GhostMCPClient()
            await client.connect()
            # ... perform query ...
            return result
        except Exception as e:
            if attempt == max_retries - 1:
                return {
                    "error": "GHOST DMPM unavailable",
                    "fallback": "Based on cached data..."
                }
            await asyncio.sleep(2 ** attempt)
```

### 3. Caching for Performance
```python
from functools import lru_cache
from datetime import datetime, timedelta

class GhostCache:
    def __init__(self, ttl_minutes=5):
        self.cache = {}
        self.ttl = timedelta(minutes=ttl_minutes)

    async def get_or_fetch(self, query):
        if query in self.cache:
            entry = self.cache[query]
            if datetime.now() - entry['timestamp'] < self.ttl:
                return entry['data']

        # Fetch fresh data
        data = await fetch_from_ghost(query)
        self.cache[query] = {
            'data': data,
            'timestamp': datetime.now()
        }
        return data
```

### 4. Conversation Context Management
```python
class GhostConversation:
    def __init__(self):
        self.context = []
        self.mentioned_carriers = set()

    def add_turn(self, user_msg, assistant_msg, ghost_data=None):
        self.context.append({
            'user': user_msg,
            'assistant': assistant_msg,
            'ghost_data': ghost_data,
            'timestamp': datetime.now()
        })

        # Track mentioned carriers
        if ghost_data:
            for mvno in ghost_data.get('mvnos', []):
                self.mentioned_carriers.add(mvno['name'])

    def get_context_prompt(self):
        """Generate context for AI"""
        recent = self.context[-5:]  # Last 5 turns
        prompt = "Previous conversation:\n"
        for turn in recent:
            prompt += f"User: {turn['user']}\n"
            prompt += f"Assistant: {turn['assistant']}\n"

        if self.mentioned_carriers:
            prompt += f"\nCarriers discussed: {', '.join(self.mentioned_carriers)}\n"

        return prompt
```

### 5. Multi-Platform Abstraction
```python
class UnifiedAIClient:
    """Unified interface for all AI platforms"""

    def __init__(self, platform="openai"):
        self.platform = platform
        self.ghost_client = GhostMCPClient()

    async def query(self, user_message):
        # Platform-specific implementation
        if self.platform == "openai":
            return await self._query_openai(user_message)
        elif self.platform == "claude":
            return await self._query_claude(user_message)
        elif self.platform == "gemini":
            return await self._query_gemini(user_message)

    async def _handle_ghost_query(self, query):
        """Common GHOST query handler"""
        await self.ghost_client.connect()
        # ... implementation ...
```

## Example Conversations

### OpenAI Example
```
User: I need to set up anonymous phones for my team. What's the best approach?
```

#!/usr/bin/env python3
"""Simple MCP client for GHOST DMPM"""
import asyncio
import websockets
import json
from datetime import datetime
from websockets.connection import State

class GhostMCPClient:
    def __init__(self, url="ws://localhost:8765", token="ghost-mcp-2024"):
        self.url = url
        self.token = token
        self.websocket = None

    async def connect(self):
        """Connect to MCP server"""
        self.websocket = await websockets.connect(self.url)

        # Authenticate
        auth_message = {
            "method": "authenticate",
            "params": {"token": self.token}
        }
        await self.websocket.send(json.dumps(auth_message))
        response = await self.websocket.recv()

        auth_result = json.loads(response)
        # Check if 'result' key exists and then 'authenticated'
        if auth_result.get("result", {}).get("authenticated"):
            print("[✓] Connected to GHOST MCP Server")
            return True
        else:
            print(f"[✗] Authentication failed: {auth_result.get('result', {}).get('error', 'Unknown error')}")
            return False

    async def query(self, method, params=None):
        """Send query to MCP server"""
        if not self.websocket or self.websocket.state != State.OPEN:
            print("Connection lost or not established. Attempting to reconnect...")
            if not await self.connect():
                print("Failed to reconnect.")
                return {"error": "Failed to connect to server"}

        message = {
            "id": f"{method}_{datetime.now().timestamp()}",
            "method": method,
            "params": params or {}
        }

        await self.websocket.send(json.dumps(message))
        response = await self.websocket.recv()

        return json.loads(response)

    async def get_top_mvnos(self, n=10):
        """Get top anonymous MVNOs"""
        return await self.query("get_top_mvnos", {"n": n})

    async def search_mvno(self, name):
        """Search for specific MVNO"""
        return await self.query("search_mvno", {"mvno_name": name})

    async def get_alerts(self, days=7): # Renamed from get_recent_alerts to match client example
        """Get recent policy changes"""
        return await self.query("get_recent_alerts", {"days": days})

    async def get_mvno_trend(self, name, days=30):
        """Get historical trend for an MVNO"""
        return await self.query("get_mvno_trend", {"mvno_name": name, "days": days})

    async def get_system_status(self):
        """Get system status"""
        return await self.query("get_system_status")

    async def close(self):
        """Close connection"""
        if self.websocket:
            await self.websocket.close()
            print("Connection closed.")

# Test function
async def test_mcp_connection():
    """Test MCP server connection"""
    client = GhostMCPClient()

    try:
        # Connect
        connected = await client.connect()
        if not connected:
            return False

        # Test query: get_top_mvnos
        print("\n[*] Testing get_top_mvnos(5)...")
        result_top_mvnos = await client.get_top_mvnos(5)
        if "error" in result_top_mvnos:
            print(f"[✗] Query failed: {result_top_mvnos['error']}")
        else:
            mvnos_list = result_top_mvnos.get('result', {}).get('mvnos', [])
            print(f"[✓] Query successful: {len(mvnos_list)} MVNOs returned.")
            # for mvno in mvnos_list:
            #     print(f"    - {mvno.get('name')}: Score {mvno.get('score')}, Assessment: {mvno.get('assessment')}")

        # Test query: search_mvno (example: "Mint Mobile")
        # print("\n[*] Testing search_mvno('Mint Mobile')...")
        # result_search = await client.search_mvno("Mint Mobile")
        # if "error" in result_search:
        #     print(f"[✗] Query failed: {result_search['error']}")
        # elif result_search.get("result", {}).get("error"):
        #      print(f"[!] MVNO not found or error: {result_search['result']['error']}")
        # else:
        #     mvno_details = result_search.get('result', {}).get('mvno', {})
        #     print(f"[✓] Query successful: Found {mvno_details.get('name')}")
        #     print(f"    Score: {mvno_details.get('score')}, Assessment: {mvno_details.get('assessment')}")

        # Test query: get_recent_alerts
        # print("\n[*] Testing get_alerts(7)...")
        # result_alerts = await client.get_alerts(7)
        # if "error" in result_alerts:
        #     print(f"[✗] Query failed: {result_alerts['error']}")
        # else:
        #     alerts_list = result_alerts.get('result', {}).get('alerts', [])
        #     print(f"[✓] Query successful: {len(alerts_list)} alerts returned.")
            # for alert in alerts_list:
            #     print(f"    - {alert.get('mvno_name')}: {alert.get('change_type')} ({alert.get('detected_timestamp')})")

        # Close
        await client.close()
        return True

    except Exception as e:
        print(f"[✗] Connection or query failed: {e}")
        return False
    finally:
        # Ensure graceful close if error occurs mid-operation
        if client.websocket and client.websocket.state == State.OPEN:
            await client.close()


if __name__ == "__main__":
    # Run test
    print("Attempting to connect to MCP server and run tests...")
    import argparse

    parser = argparse.ArgumentParser(description="GHOST DMPM MCP Client")
    parser.add_argument("--method", type=str, required=True, help="Method to call on MCP server")
    parser.add_argument("--params", type=json.loads, default={}, help="JSON string of parameters for the method")
    # Use the token from the actual live config for consistency in demo
    parser.add_argument("--token", type=str, default="ghost-mcp-secret-token", help="Authentication token")
    parser.add_argument("--url", type=str, default="ws://localhost:8765", help="MCP Server URL")

    args = parser.parse_args()

    async def main_cli(args):
        client = GhostMCPClient(url=args.url, token=args.token)
        try:
            if not await client.connect():
                print(f"Failed to connect and authenticate with token: {args.token[:10]}...")
                return

            print(f"\n[*] Calling method: {args.method} with params: {args.params}")
            result = await client.query(args.method, args.params)
            print(json.dumps(result, indent=2))

        except Exception as e:
            print(f"[✗] Error during CLI execution: {e}")
        finally:
            if client.websocket and client.websocket.state == State.OPEN:
                await client.close()

    if args.method:
        asyncio.run(main_cli(args))
    else:
        # Fallback to test connection if no method specified, though `method` is required by argparse
        print("Attempting to connect to MCP server and run default tests...")
        asyncio.run(test_mcp_connection()) # test_mcp_connection would need token adjustment too

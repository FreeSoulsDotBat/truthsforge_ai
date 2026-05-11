"""MCP-like JSON-RPC servers that bridge the Truth's Forge backend to Blender/Fusion.

Each server is meant to run as a separate process (``python -m
app.modeling.mcp_servers.blender_server``), speaking line-delimited JSON-RPC 2.0
over ``stdin``/``stdout``. The stdio transport is opt-in; the in-process
``LocalMCPClient`` remains the default so existing behaviour stays unchanged.
"""

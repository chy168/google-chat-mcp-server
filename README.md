# Run MCP server (all function)
```
fastmcp dev server.py --with-editable .
```

# Run auth server (login google only)
```
python server.py -local-auth --port 8000
```

# config in mcp.json
```
"zz_mcp": {
    "command": "uv",
    "args": [
        "--directory",
        "/Users/zzchen/codes/AI/mcp-gcp-chat-py",
        "run",
        "server.py"
    ]
}
```
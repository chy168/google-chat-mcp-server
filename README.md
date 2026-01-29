# Introduction

This project provides a Google Chat integration for MCP (Model Control Protocol) servers written by Python with FastMCP. It allows you to access and interact with Google Chat spaces and messages through MCP tools.

## Structure
The project consists of two main components:

1. **MCP Server with Google Chat Tools**: Provides tools for interacting with Google Chat through the Model Control Protocol.
   - Written by FastMCP
   - `server.py`: Main MCP server implementation with Google Chat tools
   - `google_chat.py`: Google Chat API integration and authentication handling

2. **Authentication Server**: Standalone component for Google account authentication
   - Written by FastAPI
   - Handles OAuth2 flow with Google
   - Stores and manages access tokens
   - Can be run independently or as part of the MCP server
   - `server_auth.py`: Authentication server implementation

The authentication flow allows you to obtain and refresh Google API tokens, which are then used by the MCP tools to access Google Chat data. (Your spaces and messages)


## Features

- OAuth2 authentication with Google Chat API
- List available Google Chat spaces
- Retrieve messages from specific spaces with date filtering
- Local authentication server for easy setup

## Requirements

- Python 3.8+
- Google Cloud project with Chat API enabled
- OAuth2 credentials from Google Cloud Console

# How to use?

## Prepare Google Oauth Login
1. Clone this project
   ```
   git clone https://github.com/chy168/google-chat-mcp-server.git
   cd google-chat-mcp-server
   ```
2. Prepare a Google Cloud Project (GCP)
3. Google Cloud Conolse (https://console.cloud.google.com/auth/overview?project=<YOUR_PROJECT_NAME>)
4. Google Auth Platform > Clients > (+) Create client > Web application
reference: https://developers.google.com/identity/protocols/oauth2/?hl=en
Authorized JavaScript origins add: `http://localhost:8000`
Authorized redirect URIs: `http://localhost:8000/auth/callback`
5. After you create a OAuth 2.0 Client, download the client secrets as `.json` file. Save as `credentials.json` at top level of project.


## Run Auth server and get your Google access token (login google only, not MCP server yet)
```
python server.py -local-auth --port 8000
```

- Open browser at http://localhost:8000/auth
- login it!
- after loggined, you access token will be saved as `token.json`

## MCP Configuration (mcp.json)
```
{
    "mcpServers": {
        "google_chat": {
            "command": "uv",
            "args": [
                "--directory",
                "<YOUR_REPO_PATH>/google-chat-mcp-server",
                "run",
                "server.py",
                "--token-path",
                "<YOUR_REPO_PATH>/google-chat-mcp-server/token.json"
            ]
        }
    }
```

## Docker / Podman

### Run Container
```bash
# Mount your project directory containing token.json
docker run -it --rm \
  -v /path/to/your/project:/data \
  google-chat-mcp-server \
  --token-path=/data/token.json

# or with podman
podman run -it --rm \
  -v /path/to/your/project:/data \
  google-chat-mcp-server \
  --token-path=/data/token.json
```

### Run Auth Server in Container
```bash
docker run -it --rm \
  -p 8000:8000 \
  -v /path/to/your/project:/data \
  google-chat-mcp-server \
  -local-auth --host 0.0.0.0 --port 8000 --token-path=/data/token.json
```


## Tools
The MCP server provides the following tools:

### Google Chat Tools
- `get_chat_spaces()` - List all Google Chat spaces the bot has access to
- `get_space_messages(space_name: str, start_date: str, end_date: str = None)` - List messages from a specific Google Chat space with optional time filtering


## Development and Debug

### Build Image
```bash
docker build -t google-chat-mcp-server .
# or
podman build -t google-chat-mcp-server .
```

### Debug
```
fastmcp dev server.py --with-editable .
```


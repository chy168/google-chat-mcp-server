#!/usr/bin/env python3
"""CLI-based OAuth authentication for headless environments.

Usage:
    python auth_cli.py
    # or via server.py:
    python server.py --auth cli

This script will:
1. Display an authorization URL
2. Wait for you to paste the authorization code
3. Exchange the code for credentials and save them
"""

import os
# Relax scope check - Google may return additional scopes that were previously granted
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

from google_chat import (
    get_credentials,
    save_credentials,
    SCOPES,
    token_info
)


def run_cli_auth(credentials_path: str = 'credentials.json'):
    """Run OAuth authentication via CLI (for headless environments)."""

    # Check if we already have valid credentials
    creds = get_credentials()
    if creds:
        print("Valid credentials already exist.")
        print(f"Token file: {token_info['token_path']}")
        return

    # Check for credentials.json
    creds_file = Path(credentials_path)
    if not creds_file.exists():
        print(f"ERROR: {credentials_path} not found.")
        print("Please download it from Google Cloud Console and save it in the current directory.")
        return

    # Use OOB-style redirect for manual code entry
    # Since Google deprecated OOB, we use localhost but handle it manually
    flow = InstalledAppFlow.from_client_secrets_file(
        str(creds_file),
        SCOPES,
        redirect_uri='http://localhost:8000/auth/callback'
    )

    # Generate authorization URL
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        prompt='consent',
        include_granted_scopes='true'
    )

    print("\n" + "=" * 60)
    print("AUTHORIZATION REQUIRED")
    print("=" * 60)
    print("\n1. Open this URL in a browser (can be on another device):\n")
    print(f"   {auth_url}\n")
    print("2. Complete the authorization flow")
    print("3. You will be redirected to a localhost URL that may fail to load")
    print("4. Copy the FULL URL from your browser's address bar")
    print("   (It will look like: http://localhost:8000/auth/callback?code=...&scope=...)")
    print("\n" + "=" * 60)

    # Get the redirect URL from user
    redirect_url = input("\nPaste the full redirect URL here: ").strip()

    if not redirect_url:
        print("ERROR: No URL provided.")
        return

    try:
        # Extract the authorization code from the URL
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(redirect_url)
        params = parse_qs(parsed.query)

        if 'error' in params:
            print(f"ERROR: Authorization failed: {params['error'][0]}")
            return

        if 'code' not in params:
            print("ERROR: No authorization code found in URL.")
            print("Make sure you copied the complete URL including the ?code=... part")
            return

        code = params['code'][0]

        # Exchange the code for credentials
        print("\nExchanging authorization code for credentials...")
        flow.fetch_token(code=code)
        creds = flow.credentials

        if not creds.refresh_token:
            print("WARNING: No refresh token received. You may need to re-authorize later.")

        # Save credentials
        save_credentials(creds)

        print("\n" + "=" * 60)
        print("SUCCESS!")
        print("=" * 60)
        print(f"Token saved to: {token_info['token_path']}")
        print(f"Expires at: {creds.expiry.isoformat() if creds.expiry else 'N/A'}")
        print(f"Has refresh token: {bool(creds.refresh_token)}")

    except Exception as e:
        print(f"\nERROR: Failed to complete authorization: {e}")


if __name__ == "__main__":
    run_cli_auth()

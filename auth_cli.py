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


def _read_line_raw(prompt: str) -> str:
    """Read a line from the terminal without TTY line-discipline buffer limits.

    Switches to raw mode so pasted content of any length is captured correctly.
    Falls back to sys.stdin.readline() when stdin is not a TTY (e.g. piped input).
    """
    import sys
    print(prompt, end='', flush=True)

    if not sys.stdin.isatty():
        return sys.stdin.readline().strip()

    import tty
    import termios

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    chars: list = []
    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch in ('\r', '\n'):
                break
            if ch == '\x03':  # Ctrl-C
                raise KeyboardInterrupt
            if ch == '\x1b':
                # Check if this is an escape sequence (arrow keys: \x1b[A/B/C/D)
                # or a bare ESC keypress (clear input).
                # We peek at the next byte with a short timeout to distinguish.
                import select
                if select.select([sys.stdin], [], [], 0.05)[0]:
                    sys.stdin.read(2)  # consume remaining bytes of the sequence
                else:
                    # Bare ESC — clear the current line, reprint the prompt.
                    # Use only the last line of the prompt for the clear width,
                    # since \r only moves to the start of the current line.
                    last_prompt_line = prompt.rsplit('\n', 1)[-1]
                    sys.stdout.write('\r' + ' ' * (len(last_prompt_line) + len(chars)) + '\r')
                    sys.stdout.write(prompt)
                    sys.stdout.flush()
                    chars.clear()
                continue
            if ch == '\x7f':  # backspace
                if chars:
                    chars.pop()
                    sys.stdout.write('\b \b')
                    sys.stdout.flush()
                continue
            chars.append(ch)
            sys.stdout.write(ch)
            sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        print(f"\n({len(chars)} characters received)")

    return ''.join(chars)


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
    print("4. From the browser address bar, find the 'code=' parameter and copy its value")
    print("   URL looks like: http://localhost:8000/auth/callback?code=<CODE>&scope=...")
    print("   Copy only the <CODE> part (between 'code=' and the next '&')")
    print("   Alternatively, paste the full URL — both are accepted")
    print("\n" + "=" * 60)

    # Get the code or full redirect URL from user.
    # Long redirect URLs exceed the TTY line-discipline buffer (~1 KB on macOS,
    # ~4 KB on Linux), causing truncation with input() or readline().
    # We switch the terminal to raw mode so characters are read one-by-one,
    # completely bypassing that buffer.
    import sys
    raw = _read_line_raw("\nPaste the authorization code (or full redirect URL), then press Enter\n(Press ESC to clear and re-paste): ")

    if not raw:
        print("ERROR: No input provided.")
        return

    try:
        from urllib.parse import urlparse, parse_qs

        # Accept either a bare code or a full redirect URL
        if raw.startswith('http'):
            parsed = urlparse(raw)
            params = parse_qs(parsed.query)

            if 'error' in params:
                print(f"ERROR: Authorization failed: {params['error'][0]}")
                return

            if 'code' not in params:
                print("ERROR: No authorization code found in URL.")
                print("Make sure you copied the complete URL including the ?code=... part")
                return

            code = params['code'][0]
        else:
            # Treat the input as a bare authorization code
            code = raw

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

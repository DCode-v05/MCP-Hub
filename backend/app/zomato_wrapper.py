"""Wrapper for mcp-remote that captures the OAuth URL from stderr.

This script is used as a transparent proxy between fastmcp's StdioTransport
and the real mcp-remote process.  stdin/stdout pass through unchanged (for the
MCP JSON-RPC protocol), while stderr is intercepted to extract the OAuth
authorization URL that mcp-remote prints.

Usage (called automatically by mcp_manager):
    python3 zomato_wrapper.py <url_file> npx -y mcp-remote <remote_url>
"""

import os
import re
import subprocess
import sys
import threading


def main():
    url_file = sys.argv[1]
    args = sys.argv[2:]

    # Spawn mcp-remote with stdin/stdout inherited (MCP protocol passthrough)
    # and stderr piped so we can capture the OAuth URL.
    proc = subprocess.Popen(
        args,
        stdin=sys.stdin.fileno(),
        stdout=sys.stdout.fileno(),
        stderr=subprocess.PIPE,
    )

    url_found = False

    def read_stderr():
        """Read mcp-remote stderr, capture OAuth URL, relay to parent stderr."""
        nonlocal url_found
        for raw_line in proc.stderr:
            # Relay to our own stderr so fastmcp can still log it
            sys.stderr.buffer.write(raw_line)
            sys.stderr.buffer.flush()

            if url_found:
                continue

            text = raw_line.decode("utf-8", errors="replace")
            # mcp-remote prints the OAuth URL on its own line, e.g.:
            #   Please authorize this client by visiting:
            #   https://mcp-server.zomato.com/authorize?...
            # Match any line containing an https URL with "authorize" in it.
            match = re.search(r"(https?://\S*authorize\S*)", text)
            if match:
                url_found = True
                try:
                    with open(url_file, "w") as f:
                        f.write(match.group(1))
                except OSError:
                    pass

    t = threading.Thread(target=read_stderr, daemon=True)
    t.start()

    returncode = proc.wait()
    t.join(timeout=2)
    sys.exit(returncode)


if __name__ == "__main__":
    main()

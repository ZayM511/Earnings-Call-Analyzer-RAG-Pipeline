# playwright (MCP)

Microsoft's official Playwright MCP server. Gives Claude Code real browser control during a task — beyond what the `playwright-browser-automation` skill describes for ad-hoc scripts.

## Config (in .mcp.json)

```json
"playwright": {
  "command": "npx",
  "args": ["-y", "@playwright/mcp@latest"]
}
```

No credentials required.

## Tools it exposes

Once connected, Claude Code can:

- `browser_navigate` — open a URL.
- `browser_click`, `browser_type`, `browser_fill_form` — interact with the DOM.
- `browser_snapshot` — get an accessibility tree of the current page (text + roles, much smaller than HTML).
- `browser_take_screenshot` — save a PNG.
- `browser_console_messages`, `browser_network_requests` — inspect what the page is doing.
- `browser_evaluate` — run JS in the page context.
- `browser_wait_for` — wait for selectors or text.
- `browser_resize` — change viewport for responsive testing.

Full tool list grows over time; check the Playwright MCP repo for the current set.

## When to use this vs the skill

Use **this MCP server** when:

- You want Claude Code to drive the browser interactively during a debugging session.
- You're capturing a one-off screenshot and don't want to commit a script.
- You're walking through the demo to verify a fix.

Use the **`playwright-browser-automation` skill** (write a script in `/tmp/`) when:

- The check should be repeatable.
- The output (screenshot, log) is going in the repo.
- You'll run the same flow more than three times.

## Common workflows

### Verify a UI fix end-to-end

> "Open localhost:3000, ask the chat 'How did Apple frame Vision Pro in Q1 2024?', take a screenshot of the answer, and check that every citation chip carries a ticker and a quarter."

Claude Code uses `browser_navigate` → `browser_fill_form` → `browser_wait_for` → `browser_take_screenshot` → `browser_snapshot`.

### Capture README screenshots in one pass

> "Walk the demo: home page, single-call deep dive on AAPL Q1 2024, multi-quarter trend on MSFT AI capex, cross-company comparison on China risk. Save each PNG to `docs/screenshots/`."

### Inspect a network call

> "When I submit the multi-quarter query, what's the request payload to /api/synthesize?"

Uses `browser_network_requests` plus a filter.

## Cost / safety notes

- The MCP server launches a real Chromium. Don't aim it at sites with authentication you wouldn't want exposed.
- `browser_evaluate` can run arbitrary JS in the page. Treat it like a foot-gun; use it sparingly.
- Don't navigate to URLs from untrusted user input — that's a server-side request forgery surface.

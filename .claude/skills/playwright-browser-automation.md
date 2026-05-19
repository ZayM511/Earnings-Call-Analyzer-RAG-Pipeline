# Playwright Browser Automation

This skill is for testing the UI in a real browser. Use it for README screenshot capture, chat-flow validation, responsive testing, and Loom rehearsal. For Claude-Code-driven browser tasks during a session, use the Playwright MCP server (see `.claude/mcp/playwright.md`) instead — this skill is for ad-hoc scripts.

## Smart defaults

When generating a Playwright script:

1. **Run with a visible browser by default** (`headless: false`). You're testing the UI; you should see it run.
2. **Write the script to `/tmp/`**, not the repo. These are throwaway artifacts.
3. **Parameterize the URL at the top** so the same script works against local dev and a deployed Vercel URL.
4. **One script, one purpose.** Don't fold three test flows into a single file.
5. **Use Chromium unless there's a reason not to.** It's the closest to the broadest user base.
6. **Save screenshots to `docs/screenshots/`** with a stable name, so the README can reference them.

## Setup

Once per machine:

```bash
uv add --dev playwright
uv run playwright install chromium
```

## Script template

```python
# /tmp/test_single_call_flow.py
import asyncio
from playwright.async_api import async_playwright

URL = "http://localhost:3000"  # change to the Vercel URL when deployed

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await ctx.new_page()
        await page.goto(URL)

        # Test the single-call deep-dive flow
        await page.get_by_role("button", name="Single-call").click()
        await page.get_by_label("Ticker").select_option("AAPL")
        await page.get_by_label("Quarter").select_option("Q3 2024")
        await page.get_by_placeholder("Ask anything").fill(
            "What did Tim Cook say about Apple Intelligence?"
        )
        await page.keyboard.press("Enter")

        # Wait for the answer + citation chips
        await page.wait_for_selector('[data-testid="citation-chip"]', timeout=15_000)

        await page.screenshot(path="docs/screenshots/single-call-aapl-q3-2024.png", full_page=True)

        await browser.close()

asyncio.run(main())
```

## Common uses

### README screenshot capture

Walk the demo once with screenshots after each meaningful state. Save them to `docs/screenshots/` with names like `01-home.png`, `02-single-call.png`, `03-multi-quarter.png`, `04-cross-company.png`, `05-hedging-heatmap.png`. README references them directly.

### Chat-flow validation

After any meaningful UI change, run a smoke-test script that submits one query per type (single_call / multi_quarter / cross_company) and asserts:

- The answer renders within 15 seconds.
- At least one citation chip per factual claim.
- The hedging-heatmap colors render for any Q&A view.

### Responsive testing

Run the same script at three widths to confirm the layout doesn't break:

```python
for width, label in [(375, "iphone-se"), (768, "ipad-portrait"), (1280, "laptop")]:
    ctx = await browser.new_context(viewport={"width": width, "height": 800})
    page = await ctx.new_page()
    await page.goto(URL)
    await page.screenshot(path=f"docs/screenshots/responsive-{label}.png", full_page=True)
```

### Loom rehearsal

Before recording a Loom video, run the demo flow end-to-end in a real browser. Time it. Note the steps that lag (probably the cold-start vector search). Pre-warm those before hitting record.

## Anti-patterns

- **Running headless when you're debugging UI.** You can't see what's happening. Set `headless=False`.
- **Hardcoded sleeps.** Use `wait_for_selector` or `wait_for_load_state("networkidle")` instead of `await asyncio.sleep(5)`.
- **Selectors based on Tailwind classes.** Classes change with refactors. Use `data-testid="..."` attributes on the elements you'll test against.
- **One mega-script.** Each scenario gets its own file in `/tmp/`. Easier to debug, faster to re-run.
- **Committing scripts in `/tmp/`.** These are throwaway. The screenshots go in `docs/screenshots/`; the scripts do not.

## When to prefer the Playwright MCP server instead

Use the MCP server (see `.claude/mcp/playwright.md`) when:

- You want Claude Code to drive the browser interactively during a debugging session.
- You need to capture an arbitrary screenshot ad hoc and don't want to write a script for it.
- You're checking a single thing once and don't need to commit it as repeatable test code.

Use this skill (write a script) when:

- The check should be repeatable.
- The output (screenshot, log) goes in the repo or in `docs/`.
- You're going to run the same flow more than three times.

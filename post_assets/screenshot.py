"""Take three cropped screenshots of the GIAE HTML reports."""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent
LAMBDA = (ROOT / "lambda" / "lambda.html").resolve().as_uri()
PHIX = (ROOT / "phiX174" / "phiX174.html").resolve().as_uri()
SHOTS = ROOT / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)


def shot(page, selector: str, out_path: Path) -> None:
    el = page.locator(selector).first
    el.scroll_into_view_if_needed()
    el.screenshot(path=str(out_path))
    print(f"Saved {out_path.name}")


with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(viewport={"width": 1400, "height": 900}, device_scale_factor=2)

    # 1. phiX174 dark matter — filter to DARK then capture the table
    page = context.new_page()
    page.goto(PHIX)
    page.wait_for_load_state("networkidle")
    # Click "Dark Matter" filter button
    page.locator("button.filter-btn", has_text="Dark Matter").click()
    page.wait_for_timeout(300)
    # Capture stat cards + the gene-explorer card together
    shot(
        page,
        ".container:has(.gene-table)",
        SHOTS / "phiX174_dark_matter.png",
    )

    # 2. lambda nu1 — search for "terminase small subunit" (unique to nu1) then crop tight
    page2 = context.new_page()
    page2.goto(LAMBDA)
    page2.wait_for_load_state("networkidle")
    page2.locator("#searchInput").fill("terminase small subunit")
    # The page binds filtering to onkeyup; fill() doesn't trigger it.
    page2.evaluate("filterTable()")
    page2.wait_for_timeout(400)
    # Capture just the gene-table (header + nu1 row)
    shot(
        page2,
        "#geneTable",
        SHOTS / "lambda_nu1_reasoning.png",
    )

    # 3. lambda confidence distribution — top dashboard with the 4 stat cards
    page3 = context.new_page()
    page3.goto(LAMBDA)
    page3.wait_for_load_state("networkidle")
    shot(
        page3,
        ".dashboard",
        SHOTS / "lambda_confidence_distribution.png",
    )

    browser.close()

print("All screenshots saved.")

"""Manual Amazon Shipping demo capture.

Use only with a company account and access you are authorised to use.
Do not place Amazon usernames or passwords in this file.
"""

from datetime import datetime
from pathlib import Path
import re

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PROFILE = BASE_DIR / "amazon_poc_profile"
OUTPUT_DIR = BASE_DIR / "amazon_demo_captures"
AMAZON_URL = "https://ship.amazon.co.uk/"


def main():
    print("Amazon Shipping: manual demo capture")
    shipping_id = input("Enter Amazon Shipping ID (for example UK4946273407): ").strip()
    if not shipping_id:
        print("No Shipping ID entered. Nothing to do.")
        return

    entered_profile = input(
        f"Existing Playwright profile folder [Enter = {DEFAULT_PROFILE}]: "
    ).strip().strip('"')
    profile_dir = Path(entered_profile).expanduser() if entered_profile else DEFAULT_PROFILE
    profile_dir = profile_dir.resolve()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^A-Z0-9_-]", "_", shipping_id.upper())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=True,
            viewport={"width": 1450, "height": 950},
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(AMAZON_URL, wait_until="domcontentloaded", timeout=60000)

            print("\nThe Amazon browser is open.")
            print("If necessary, sign in MANUALLY in the browser (never in this script).")
            print("Then find the shipment using the Shipping ID below.")

            # Only prefill search when the recorded search box is available.
            try:
                search = page.get_by_role(
                    "textbox", name="Search by tracking #, order #"
                )
                search.wait_for(state="visible", timeout=12000)
                search.fill(shipping_id)
                print(f"Search filled with: {shipping_id}")
            except PlaywrightTimeoutError:
                print("Search box not detected; search for the Shipping ID manually.")

            print("\nIn Amazon, click the matching shipment, then 'See all updates'.")
            input("When Delivery history is visible, RETURN HERE and press Enter to capture...")

            # Keep the page currently displaying the shipment or history.
            current_page = next(
                (p for p in reversed(context.pages) if not p.is_closed()), page
            )
            text_path = OUTPUT_DIR / f"{safe_id}_{timestamp}_shipment_page.txt"
            image_path = OUTPUT_DIR / f"{safe_id}_{timestamp}_shipment_page.png"

            visible_text = current_page.locator("body").inner_text(timeout=15000)
            text_path.write_text(visible_text, encoding="utf-8")
            current_page.screenshot(path=str(image_path), full_page=True)

            print("\nShipment history captured.")
            print(f"Confirm this is shipment: {shipping_id}")
            print("Close the Delivery history popup if it is open.")

            input(
                "When the shipment's document buttons are visible, "
                "press Enter to capture PDF and Package details Excel..."
            )

            capture_amazon_documents(
                current_page,
                context,
                safe_id,
            )

            print("\nCapture complete:")
            print(f"Text:       {text_path}")
            print(f"Screenshot: {image_path}")
            print("These files may contain customer personal data. Redact before sharing.")
        finally:
            context.close()


if __name__ == "__main__":
    main()

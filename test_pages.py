"""Tests for the JavaScript embedded in pages/.

The host-detection predicate decides which data source a display uses, so it
is evaluated in a real browser rather than pattern-matched in the source.
"""
import re
import unittest
from pathlib import Path

PAGES = ("pages/display.html", "pages/room.html")

# Hosts that are genuinely Princeton, and lookalikes that must not pass.
PRINCETON_HOSTS = ("princeton.edu", "www.princeton.edu", "orfe.princeton.edu")
IMPOSTOR_HOSTS = (
    "evilprinceton.edu",          # bare endsWith('princeton.edu') accepted this
    "notprinceton.edu",
    "xn--princeton.edu",
    "princeton.edu.attacker.net",  # domain in a left-hand label
    "example.com",
    "",
)


def extract_predicate(html):
    """Pull the isPrincetonHost function source out of a page."""
    match = re.search(
        r"function isPrincetonHost\(h\)\s*\{.*?\n\s*\}", html, re.DOTALL
    )
    return match.group(0) if match else None


class TestPrincetonHostDetection(unittest.TestCase):
    def test_every_page_defines_the_predicate(self):
        for page in PAGES:
            with self.subTest(page=page):
                html = Path(page).read_text()
                self.assertIsNotNone(
                    extract_predicate(html),
                    f"{page} does not define isPrincetonHost",
                )

    def test_bare_suffix_check_is_not_reintroduced(self):
        """endsWith('princeton.edu') without a leading dot matches lookalikes."""
        for page in PAGES:
            with self.subTest(page=page):
                html = Path(page).read_text()
                self.assertNotIn(
                    "endsWith('princeton.edu')",
                    html,
                    f"{page} uses an unanchored host suffix check",
                )

    def test_predicate_accepts_princeton_and_rejects_lookalikes(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:  # pragma: no cover
            self.skipTest("playwright not installed")

        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as exc:  # pragma: no cover
                self.skipTest(f"chromium unavailable: {exc}")
            try:
                page = browser.new_page()
                for path in PAGES:
                    predicate = extract_predicate(Path(path).read_text())
                    self.assertIsNotNone(predicate, f"{path}: predicate not found")
                    fn = f"(h) => {{ {predicate}; return isPrincetonHost(h); }}"
                    for host in PRINCETON_HOSTS:
                        with self.subTest(page=path, host=host, expect=True):
                            self.assertTrue(
                                page.evaluate(fn, host),
                                f"{path}: {host!r} should be treated as Princeton",
                            )
                    for host in IMPOSTOR_HOSTS:
                        with self.subTest(page=path, host=host, expect=False):
                            self.assertFalse(
                                page.evaluate(fn, host),
                                f"{path}: {host!r} must NOT be treated as Princeton",
                            )
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()

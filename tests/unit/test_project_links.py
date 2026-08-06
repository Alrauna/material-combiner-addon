from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

# Runtime modules that ship to users. Historical attribution in README.md is
# intentional and is checked separately.
SHIPPED_SOURCES = [
    ROOT / "ui" / "credits_panel.py",
    ROOT / "operators" / "browser.py",
]

STALE_OWNERS = ("teamneoneko", "neoneko.xyz", "Grim-es")


class ProjectLinkTests(unittest.TestCase):
    def test_shipped_sources_have_no_stale_owner_urls(self):
        for source in SHIPPED_SOURCES:
            text = source.read_text(encoding="utf-8")
            for owner in STALE_OWNERS:
                with self.subTest(source=source.name, owner=owner):
                    self.assertNotIn(owner, text)

    def test_credits_panel_does_not_link_discord(self):
        text = (ROOT / "ui" / "credits_panel.py").read_text(encoding="utf-8")
        self.assertNotIn("discord.", text)
        self.assertNotIn("DISCORD_URL", text)

    def test_readme_credits_previous_and_current_maintainers(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Previously maintained by [Team Neoneko]", text)
        self.assertIn("Currently maintained by [Alrauna]", text)


if __name__ == "__main__":
    unittest.main()

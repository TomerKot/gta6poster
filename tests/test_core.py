import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gta6bot import filters, formatting, state as st  # noqa: E402
from gta6bot.models import Item  # noqa: E402

import tomllib  # noqa: E402

CFG = tomllib.loads((Path(__file__).resolve().parents[1] / "config/config.toml").read_text(encoding="utf-8"))


class FilterTests(unittest.TestCase):
    def setUp(self):
        self.kw = filters.compile_patterns(CFG["filters"]["keywords"])
        self.block = filters.compile_patterns(CFG["filters"]["block"])
        self.rumor = filters.compile_patterns(CFG["filters"]["rumor"])

    def test_keywords(self):
        for t in ["GTA 6 trailer 3", "gta6 release", "GTA VI news", "Grand Theft Auto VI map", "Leonida", "GTAVI hype"]:
            self.assertTrue(filters.matches_any(t, self.kw), t)
        for t in ["GTA Online update", "Grand Theft Auto V sale", "GTA 60 fps"]:
            self.assertFalse(filters.matches_any(t, self.kw), t)

    def test_block_malware_lures(self):
        for t in ["GTA 6 APK download", "GTA 6 free download PC", "GTA 6 torrent", "GTA 6 beta key giveaway",
                  "Leaked gameplay of GTA 6"]:
            self.assertTrue(filters.matches_any(t, self.block), t)
        self.assertFalse(filters.matches_any("GTA 6 trailer breaks YouTube record", self.block))

    def test_rumor(self):
        self.assertTrue(filters.matches_any("GTA 6 insider claims date", self.rumor))
        self.assertFalse(filters.matches_any("Rockstar confirms GTA 6 date", self.rumor))

    def test_canonical_url(self):
        self.assertEqual(
            filters.canonical_url("HTTPS://Example.com/a/b/?utm_source=x&id=5&fbclid=1#frag"),
            "https://example.com/a/b?id=5",
        )
        self.assertIsNone(filters.canonical_url("javascript:alert(1)"))
        self.assertIsNone(filters.canonical_url("ftp://x.com/a"))
        self.assertIsNone(filters.canonical_url(""))

    def test_clean_text(self):
        raw = "<p>Hello <b>world</b><script>evil()</script> &amp; more</p>" + " word" * 100
        out = filters.clean_text(raw, 40)
        self.assertNotIn("<", out)
        self.assertNotIn("evil", out)
        self.assertLessEqual(len(out), 41)
        self.assertTrue(out.endswith("…"))

    def test_title_dedupe_key(self):
        self.assertEqual(filters.title_key("GTA 6: New Trailer!"), filters.title_key("gta 6 new   trailer"))


class FormattingTests(unittest.TestCase):
    def test_html_escaped(self):
        it = Item(title='<b>"x"</b> & y', url='https://e.com/a?b=1&c="2"', summary="<script>", published=None,
                  source="<Src>", rumor=True)
        msg = formatting.build_message(it)
        self.assertNotIn("<script>", msg)
        self.assertIn("&lt;b&gt;", msg)
        self.assertIn("&quot;2&quot;", msg)
        self.assertIn("Неперевірена", msg)
        self.assertLessEqual(len(msg), 4096)


class StateTests(unittest.TestCase):
    def test_prune_and_roundtrip(self):
        import tempfile

        now = datetime.now(timezone.utc)
        s = st.new_state()
        s["urls"]["old"] = (now - timedelta(days=60)).isoformat()
        s["urls"]["new"] = now.isoformat()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "seen.json"
            self.assertIsNone(st.load(p))
            st.save(p, s, now)
            loaded = st.load(p)
        self.assertNotIn("old", loaded["urls"])
        self.assertIn("new", loaded["urls"])
        self.assertEqual(loaded["heartbeat"], now.strftime("%Y-%m"))


class PipelineTests(unittest.TestCase):
    """Наскрізно: підміняємо мережу, перевіряємо seed, дедуп, фільтри, ліміти."""

    def test_end_to_end(self):
        import argparse
        import tempfile
        import types

        now = datetime.now(timezone.utc)

        def mk(title, url, official=False, age_h=1, src="S"):
            return Item(title=title, url=url, summary="sum", published=now - timedelta(hours=age_h),
                        source=src, official=official)

        batch = [
            mk("GTA 6 trailer 3 released", "https://a.com/1", official=True),
            mk("Gta 6 Trailer 3 Released!", "https://b.com/dup"),          # дубль за заголовком
            mk("GTA 6 APK free download", "https://evil.com/x"),           # блок
            mk("Cooking tips", "https://c.com/cook"),                      # нерелевантно
            mk("GTA 6 insider claims date", "https://d.com/r"),            # чутки
            mk("GTA 6 very old news", "https://e.com/old", age_h=500),     # застаріле
        ]
        fake = types.ModuleType("gta6bot.fetch")
        fake.fetch_source = lambda src, n: list(batch)
        sys.modules["gta6bot.fetch"] = fake
        sent = []
        fake_tg = types.ModuleType("gta6bot.telegram")
        fake_tg.send = lambda tok, chat, text, url: sent.append(text) or True
        sys.modules["gta6bot.telegram"] = fake_tg

        from gta6bot import main as m
        import os
        os.environ["TELEGRAM_BOT_TOKEN"] = "x"
        os.environ["TELEGRAM_CHAT_ID"] = "y"
        m.time.sleep = lambda s: None
        with tempfile.TemporaryDirectory() as d:
            cfgp = Path(d) / "c.toml"
            cfgp.write_text(
                (Path(__file__).resolve().parents[1] / "config/config.toml").read_text(encoding="utf-8")
                .split("[[sources]]")[0]
                + '[[sources]]\nname = "T"\nurl = "https://t.example/rss"\n', encoding="utf-8")
            sp = Path(d) / "seen.json"
            args = argparse.Namespace(config=str(cfgp), state=str(sp), dry_run=False, post_initial=False)
            self.assertEqual(m.run(args), 0)
            self.assertEqual(sent, [])                 # перший запуск лише засіває стан
            self.assertTrue(sp.exists())
            self.assertEqual(m.run(args), 0)
            self.assertEqual(sent, [])                 # нічого нового
            batch.append(mk("Rockstar confirms GTA 6 map size", "https://f.com/new"))
            self.assertEqual(m.run(args), 0)
            self.assertEqual(len(sent), 1)
            self.assertIn("map size", sent[0])
            self.assertEqual(m.run(args), 0)
            self.assertEqual(len(sent), 1)             # повторно не постить


if __name__ == "__main__":
    unittest.main()

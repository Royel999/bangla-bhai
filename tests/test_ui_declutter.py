"""Offline checks for the v4 main-interface declutter (Mamoni defaults, no duplicate voice orb)."""
import os, re, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


class UiDeclutter(unittest.TestCase):
    def test_mamoni_defaults_medium_and_parked(self):
        js = read("static", "notes", "float.js")
        self.assertIn("({small:90,medium:150,large:225}[localStorage.rbtSize]||150)", js)
        self.assertNotIn("||225)", js)
        self.assertIn("const roamOn=()=>localStorage.rbtRoam==='1'", js)
        self.assertNotIn("rbtRoam!=='0'", js)
        self.assertIn("parkPos=", js)
        self.assertIn("innerWidth>=900?248+pad:pad", js)
        self.assertIn("innerHeight-FOOT-lift", js)
        self.assertNotIn("{x:innerWidth-110,y:innerHeight-FOOT-4}", js)

    def test_v4_does_not_load_floating_voice_orb(self):
        html = read("static", "v4", "index.html")
        self.assertNotIn("orb.js", html)
        self.assertIn("float.js?v=11", html)
        self.assertIn("v4.css?v=1.1-ui", html)
        orb = read("static", "v4", "orb.js")
        self.assertIn("const isV4=!!document.getElementById('app')&&!!document.getElementById('tabs')", orb)
        self.assertIn("if(isV4){document.body.append(vo)}", orb)

    def test_hero_seal_breath_respects_reduced_motion(self):
        css = read("static", "v4", "v4.css")
        self.assertIn("@keyframes breath", css)
        self.assertRegex(
            css,
            r"@media \(prefers-reduced-motion:\s*no-preference\)\s*\{[^}]*\.hero \.ava",
        )
        self.assertIn("@media (prefers-reduced-motion:reduce)", css)

    def test_panel_orb_keeps_features_behind_more(self):
        html = read("static", "notes", "panel.html")
        for key in ("note", "clip", "ai", "task", "find", "agent", "design", "sec", "bird"):
            self.assertIn('id="p-%s"' % key, html)
        self.assertIn('id="orbMore"', html)
        self.assertIn("PRIMARY=['note','clip','ai','bird']", html)
        self.assertIn("@media (prefers-reduced-motion:reduce)", html)
        self.assertIn("@media (prefers-reduced-motion:no-preference)", html)


if __name__ == "__main__":
    unittest.main()

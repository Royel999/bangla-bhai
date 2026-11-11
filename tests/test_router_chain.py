"""P0: free chain only has live, card-free providers; PRIVATE chain never leaks to training-tier providers."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import router as RT

DEAD = ("mistral:", "github:", "hf:", "huggingface:", "cerebras:")
TRAINING_TIER = ("gemini:", "openrouter:", "zai:", "pollinations:")

class RouterChain(unittest.TestCase):
    def test_no_dead_provider_anywhere(self):
        for mid in list(RT.CHAIN) + RT.DEFAULT + RT.DEV + RT.PRIVATE:
            self.assertFalse(mid.startswith(DEAD), mid)
        self.assertNotIn("mistral", RT.PROV_FLAG)
        self.assertNotIn("mistral", RT.PROVIDERS)

    def test_chains_reference_known_models(self):
        for mid in RT.DEFAULT + RT.DEV + RT.PRIVATE:
            self.assertIn(mid, RT.CHAIN, mid)

    def test_default_order(self):
        self.assertEqual(RT.DEFAULT[0], "groq:openai/gpt-oss-120b")
        self.assertEqual(RT.DEFAULT[-1], "openrouter:openrouter/free")   # 50 RPD: last resort only
        self.assertLess(RT.DEFAULT.index("gemini:gemini-3.1-flash-lite"), RT.DEFAULT.index("cf:openai/gpt-oss-120b"))

    def test_private_chain_excludes_training_tier(self):
        self.assertTrue(RT.PRIVATE)
        for mid in RT.PRIVATE:
            self.assertFalse(mid.startswith(TRAINING_TIER), mid)

    def test_flags_have_no_mistral(self):
        import flags as FL
        self.assertFalse(any("mistral" in k for k in FL.FLAGS))

if __name__ == "__main__":
    unittest.main()

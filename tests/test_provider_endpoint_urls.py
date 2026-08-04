import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class ProviderEndpointUrlTests(unittest.TestCase):
    def test_replaces_openai_version_with_gemini_version(self):
        provider = {"base_url": "https://api.apib.ai/v1"}

        self.assertEqual(
            main.gemini_endpoint_url(provider, "gemini-3-pro-image-preview"),
            "https://api.apib.ai/v1beta/models/gemini-3-pro-image-preview:generateContent",
        )

    def test_deduplicates_matching_api_version(self):
        provider = {"base_url": "https://example.com/v1"}

        self.assertEqual(
            main.provider_endpoint_url(provider, "image_generation_endpoint", "/v1/images/generations"),
            "https://example.com/v1/images/generations",
        )

    def test_keeps_explicit_absolute_override(self):
        provider = {
            "base_url": "https://example.com/v1",
            "image_generation_endpoint": "https://proxy.example/generate",
        }

        self.assertEqual(
            main.provider_endpoint_url(provider, "image_generation_endpoint", "/v1beta/models/demo:generateContent"),
            "https://proxy.example/generate",
        )


if __name__ == "__main__":
    unittest.main()

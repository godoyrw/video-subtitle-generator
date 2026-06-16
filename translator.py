#!/usr/bin/env python3

import argostranslate.package
import argostranslate.translate


class ArgosTranslator:
    """Translate text or Whisper segments using Argos Translate (offline)."""

    def __init__(self, source_lang: str, target_lang: str):
        self.source_lang = source_lang
        self.target_lang = target_lang
        self._install_package()

    def _install_package(self):
        """Download and install translation package (idempotent)."""
        argostranslate.package.update_package_index()
        available_packages = argostranslate.package.get_available_packages()
        package = next(
            (
                pkg
                for pkg in available_packages
                if pkg.from_code == self.source_lang and pkg.to_code == self.target_lang
            ),
            None,
        )
        if package is None:
            raise ValueError(f"No translation package found for {self.source_lang} -> {self.target_lang}")
        package.install()

    def translate_text(self, text: str) -> str:
        """Translate a single string."""
        translation = argostranslate.translate.translate(
            text, self.source_lang, self.target_lang
        )
        return str(translation)

    def translate_segments(self, whisper_result: dict) -> dict:
        """Translate all segments in Whisper result and return a new result dict."""
        translated_segments = []
        full_text_parts = []
        for seg in whisper_result["segments"]:
            original_text = seg["text"].strip()
            if not original_text:
                continue
            translated_text = self.translate_text(original_text)
            new_seg = seg.copy()
            new_seg["text"] = translated_text
            translated_segments.append(new_seg)
            full_text_parts.append(translated_text)

        return {
            "text": " ".join(full_text_parts),
            "segments": translated_segments,
            "language": self.target_lang,
        }
#!/usr/bin/env python3

from pathlib import Path
import argparse
import logging
import sys
import torch
import whisper

from translator import ArgosTranslator


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
        force=True,  # Garante que override qualquer configuração anterior
    )
    # Silencia logs de bibliotecas terceiras quando não verbose
    if not verbose:
        logging.getLogger("whisper").setLevel(logging.WARNING)
        logging.getLogger("argostranslate").setLevel(logging.WARNING)
        logging.getLogger("torch").setLevel(logging.WARNING)


def validate_file(file_path: Path) -> None:
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if not file_path.is_file():
        raise ValueError(f"Invalid file: {file_path}")


def get_device():
    if torch.cuda.is_available():
        try:
            total_vram = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            logging.info("CUDA detected | VRAM %.2f GB", total_vram)
            return "cuda", total_vram
        except Exception:
            pass
    logging.info("Using CPU")
    return "cpu", 0.0


def select_model(model_name: str, vram: float) -> str:
    if model_name != "auto":
        return model_name
    if vram >= 10:
        return "large"
    if vram >= 6:
        return "medium"
    if vram >= 4:
        return "small"
    return "base"


def format_timestamp(seconds: float) -> str:
    millis = int(seconds * 1000)
    hours = millis // 3_600_000
    millis %= 3_600_000
    minutes = millis // 60_000
    millis %= 60_000
    secs = millis // 1000
    millis %= 1000
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def save_srt(result: dict, output_file: Path) -> None:
    with open(output_file, "w", encoding="utf-8") as f:
        for idx, segment in enumerate(result["segments"], start=1):
            start = format_timestamp(segment["start"])
            end = format_timestamp(segment["end"])
            text = segment["text"].strip()
            f.write(f"{idx}\n")
            f.write(f"{start} --> {end}\n")
            f.write(text)
            f.write("\n\n")


def transcribe(
    input_file: Path,
    output_dir: Path,
    model_name: str,
    language: str,
    translate: bool,
    target_lang: str,
) -> None:
    device, vram = get_device()
    selected_model = select_model(model_name, vram)
    logging.info("Loading Whisper model: %s on %s", selected_model, device)

    try:
        model = whisper.load_model(selected_model, device=device)
    except RuntimeError as ex:
        if "CUDA out of memory" in str(ex):
            logging.warning("CUDA OOM. Falling back to CPU.")
            torch.cuda.empty_cache()
            device = "cpu"
            model = whisper.load_model(selected_model, device=device)
        else:
            raise

    result = model.transcribe(
        str(input_file),
        language=language,
        verbose=False,      # Desativa barra de progresso
        fp16=(device == "cuda"),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    srt_file = output_dir / f"{input_file.stem}.srt"
    txt_file = output_dir / f"{input_file.stem}.txt"
    save_srt(result, srt_file)
    txt_file.write_text(result["text"], encoding="utf-8")
    logging.info("Generated: %s", srt_file)

    if translate:
        translator = ArgosTranslator(source_lang=language, target_lang=target_lang)
        translated_result = translator.translate_segments(result)
        translated_srt = output_dir / f"{input_file.stem}.{target_lang}.srt"
        translated_txt = output_dir / f"{input_file.stem}.{target_lang}.txt"
        save_srt(translated_result, translated_srt)
        translated_txt.write_text(translated_result["text"], encoding="utf-8")
        logging.info("Generated: %s", translated_srt)


def parse_args():
    parser = argparse.ArgumentParser(description="Video Subtitle Generator with Whisper and optional translation")
    parser.add_argument("file", help="Input video or audio file")
    parser.add_argument("--model", default="auto", choices=["auto", "tiny", "base", "small", "medium", "large"])
    parser.add_argument("--language", default="en", help="Source language code (e.g., en, pt, es)")
    parser.add_argument("--translate", action="store_true", help="Translate subtitles to target language")
    parser.add_argument("--target-lang", default="pt", help="Target language for translation (default: pt)")
    parser.add_argument("--output", default="output", help="Output directory")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logs")
    return parser.parse_args()


def main():
    args = parse_args()
    setup_logging(args.verbose)
    try:
        transcribe(
            input_file=Path(args.file),
            output_dir=Path(args.output),
            model_name=args.model,
            language=args.language,
            translate=args.translate,
            target_lang=args.target_lang,
        )
        logging.info("Finished successfully")
    except Exception as exc:
        logging.exception(exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
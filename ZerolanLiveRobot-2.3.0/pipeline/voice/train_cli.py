"""CLI tool for training voice cloning models for IGEM-sama.

Provides commands for:
  - dataset: Preparing and validating audio datasets
  - train: Training the RVC model
  - test: Testing the trained model on sample audio

Usage:
    python -m pipeline.voice.train_cli dataset --dir data/voice_dataset
    python -m pipeline.voice.train_cli train --epochs 200 --batch_size 8
    python -m pipeline.voice.train_cli test --input test.wav --model models/rvc/igem_sama.pth
"""

import argparse
import os
import sys

from loguru import logger


def cmd_dataset(args):
    """Prepare and validate audio dataset for training."""
    dataset_dir = args.dir
    if not os.path.exists(dataset_dir):
        os.makedirs(dataset_dir, exist_ok=True)
        logger.info(f"Created dataset directory: {dataset_dir}")

    # Check for audio files
    valid_extensions = {'.wav', '.mp3', '.flac', '.ogg'}
    audio_files = []
    for f in os.listdir(dataset_dir):
        ext = os.path.splitext(f)[1].lower()
        if ext in valid_extensions:
            audio_files.append(f)

    if not audio_files:
        logger.info(f"No audio files found in {dataset_dir}")
        logger.info("Please place audio files (WAV/MP3/FLAC) in this directory.")
        logger.info("Recommended: 10-30 minutes of clean speech audio.")
        return

    logger.info(f"Found {len(audio_files)} audio files in {dataset_dir}")
    for f in audio_files:
        path = os.path.join(dataset_dir, f)
        size_mb = os.path.getsize(path) / (1024 * 1024)
        logger.info(f"  {f} ({size_mb:.1f} MB)")

    logger.info("Dataset validation complete. Ready for training.")


def cmd_train(args):
    """Train the RVC voice model."""
    try:
        from rvc_python.train import RVCTrainer
    except ImportError:
        logger.error("rvc-python not installed. Install with: pip install rvc-python")
        logger.error("Also ensure PyTorch is installed: pip install torch")
        sys.exit(1)

    from pipeline.voice.config import VoiceTrainConfig

    config = VoiceTrainConfig(
        dataset_dir=args.dataset_dir,
        output_dir=args.output_dir,
        model_name=args.model_name,
        batch_size=args.batch_size,
        epochs=args.epochs,
        save_every_n_epochs=args.save_every,
        sample_rate=args.sample_rate,
    )

    logger.info(f"Starting RVC training: {config.model_name}")
    logger.info(f"  Dataset: {config.dataset_dir}")
    logger.info(f"  Output: {config.output_dir}")
    logger.info(f"  Epochs: {config.epochs}")
    logger.info(f"  Batch size: {config.batch_size}")

    try:
        trainer = RVCTrainer(
            dataset_dir=config.dataset_dir,
            output_dir=config.output_dir,
            model_name=config.model_name,
            batch_size=config.batch_size,
            epochs=config.epochs,
            save_every_n_epochs=config.save_every_n_epochs,
            sample_rate=config.sample_rate,
            version=config.version,
        )
        trainer.train()
        logger.info("Training complete!")
    except Exception as e:
        logger.error(f"Training failed: {e}")
        sys.exit(1)


def cmd_test(args):
    """Test the trained voice model on sample audio."""
    try:
        import soundfile as sf
    except ImportError:
        logger.error("soundfile not installed. Install with: pip install soundfile")
        sys.exit(1)

    from pipeline.voice.config import RVCConfig
    from pipeline.voice.voice_converter import VoiceConverter

    if not os.path.exists(args.input):
        logger.error(f"Input audio not found: {args.input}")
        sys.exit(1)

    if not os.path.exists(args.model):
        logger.error(f"Model not found: {args.model}")
        sys.exit(1)

    config = RVCConfig(model_path=args.model, device=args.device)
    converter = VoiceConverter(config)

    logger.info("Loading model...")
    if not converter.load_model():
        logger.error("Failed to load model.")
        sys.exit(1)

    output_path = args.output or args.input.replace(".wav", "_converted.wav")
    logger.info(f"Converting: {args.input} -> {output_path}")
    result = converter.convert(args.input, output_path)

    if result != args.input:
        logger.info(f"Conversion successful: {output_path}")
    else:
        logger.error("Conversion failed.")


def main():
    parser = argparse.ArgumentParser(description="IGEM-sama Voice Training CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # dataset command
    ds_parser = subparsers.add_parser("dataset", help="Prepare audio dataset")
    ds_parser.add_argument("--dir", default="data/voice_dataset", help="Dataset directory")

    # train command
    tr_parser = subparsers.add_parser("train", help="Train voice model")
    tr_parser.add_argument("--dataset_dir", default="data/voice_dataset")
    tr_parser.add_argument("--output_dir", default="models/rvc")
    tr_parser.add_argument("--model_name", default="igem_sama")
    tr_parser.add_argument("--epochs", type=int, default=200)
    tr_parser.add_argument("--batch_size", type=int, default=8)
    tr_parser.add_argument("--save_every", type=int, default=25)
    tr_parser.add_argument("--sample_rate", type=int, default=40000)
    tr_parser.add_argument("--version", default="v2")

    # test command
    te_parser = subparsers.add_parser("test", help="Test voice model")
    te_parser.add_argument("--input", required=True, help="Input audio file")
    te_parser.add_argument("--model", required=True, help="RVC model path")
    te_parser.add_argument("--output", default=None, help="Output audio path")
    te_parser.add_argument("--device", default="cuda", help="Device (cuda/cpu)")

    args = parser.parse_args()

    if args.command == "dataset":
        cmd_dataset(args)
    elif args.command == "train":
        cmd_train(args)
    elif args.command == "test":
        cmd_test(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

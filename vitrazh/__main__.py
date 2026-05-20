from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

from vitrazh.models import Config


def main() -> None:
    parser = argparse.ArgumentParser(description="Vitrazh — interactive stained-glass installation")
    parser.add_argument("--config", type=str, default="config/config_example.yaml", help="Config YAML path")
    parser.add_argument("--source", type=str, default=None, help="Override camera source (file path, RTSP, or webcam index)")
    parser.add_argument("--dashboard", action="store_true", help="Run with web dashboard")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    )

    config_path = Path(args.config)
    if config_path.exists():
        with open(config_path) as f:
            raw = yaml.safe_load(f) or {}
        config = Config(**raw)
    else:
        logging.warning("Config %s not found, using defaults", config_path)
        config = Config()

    if args.source is not None:
        try:
            config.camera.source = int(args.source)
        except ValueError:
            config.camera.source = args.source

    if args.dashboard:
        from vitrazh.dashboard.server import run_dashboard
        run_dashboard(config)
    else:
        from vitrazh.pipeline import VitrazPipeline
        pipeline = VitrazPipeline(config)
        try:
            pipeline.run()
        except KeyboardInterrupt:
            logging.info("Interrupted")
        finally:
            pipeline.shutdown()


if __name__ == "__main__":
    main()

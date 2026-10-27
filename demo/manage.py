"""Run demo stages: python -m demo.manage --config local/config.json assets."""

import argparse
import json
import logging
import sys
from pathlib import Path

from demo.endpoint import deploy, verify
from demo.pipeline import external_tracking, register_assets, register_components, run_pipelines
from demo.workspace import client, create_compute


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("local") / "config.json")
    parser.add_argument(
        "action",
        choices=["compute", "assets", "components", "train", "external", "deploy", "verify", "all"],
    )
    return parser


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    args = create_parser().parse_args()
    ml = client(args.config)
    actions = {
        "compute": create_compute,
        "assets": register_assets,
        "components": register_components,
        "train": run_pipelines,
        "external": external_tracking,
        "deploy": deploy,
        "verify": verify,
    }
    selected = (
        [name for name in actions if name != "components"]
        if args.action == "all"
        else [args.action]
    )
    for name in selected:
        result = actions[name](ml)
        if result is not None:
            print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

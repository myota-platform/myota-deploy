#!/usr/bin/env python3
"""Record digests behind production :latest or test :testing image tags."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALUES = ROOT / "deploy/helm/myota/values-image-digests.yaml"
IMAGES = {
    "identity": "ghcr.io/myota-platform/myota-identity-service:latest",
    "programmes": "ghcr.io/myota-platform/myota-programme-service:latest",
    "geodata": "ghcr.io/myota-platform/myota-geodata-service:latest",
    "activity": "ghcr.io/myota-platform/myota-activity-service:latest",
    "gateway": "ghcr.io/myota-platform/myota-gateway:latest",
    "adminWeb": "ghcr.io/myota-platform/myota-admin-web:latest",
    "platform": "ghcr.io/myota-platform/myota-service:latest",
}
TEST_VALUES = ROOT / "deploy/helm/myota-test/values-image-digests-testing.yaml"
TEST_IMAGES = {
    key: image.rsplit(":", 1)[0] + ":testing" for key, image in IMAGES.items()
}
TEST_IMAGES["web"] = "ghcr.io/myota-platform/myota-web:testing"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tag", choices=("latest", "testing"), default="latest"
    )
    args = parser.parse_args()
    output = TEST_VALUES if args.tag == "testing" else VALUES
    images = TEST_IMAGES if args.tag == "testing" else IMAGES
    contents = output.read_text(encoding="utf-8")
    indent = "      " if args.tag == "testing" else "    "
    for key, image in images.items():
        digest = subprocess.check_output(
            ["crane", "digest", image], text=True, stderr=subprocess.STDOUT
        ).strip()
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise SystemExit(
                f"Unexpected digest returned for {image}: {digest!r}"
            )
        pattern = re.compile(
            rf"(?m)^({re.escape(indent + key)}:\s*)\"[^\"]*\"$"
        )
        contents, count = pattern.subn(rf'\g<1>"{digest}"', contents)
        if count != 1:
            raise SystemExit(
                f"Expected exactly one {args.tag} imageRollout.digests.{key} entry; found {count}"
            )
        print(f"{key}: {digest}")
    output.write_text(contents, encoding="utf-8")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Copy filesystem-adapter objects into a SeaweedFS/S3-compatible endpoint.

The filesystem adapter stores objects as <source>/<bucket>/<object-key>. This
one-shot tool preserves those bucket and key names, so database metadata does
not need to change during the storage migration.
"""
from __future__ import annotations

import argparse
import mimetypes
import os
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default=os.environ.get("MYOTA_OBJECT_STORAGE_LOCAL_DIR", "/tmp/myota-object-storage"),
        help="filesystem adapter root (default: MYOTA_OBJECT_STORAGE_LOCAL_DIR)",
    )
    parser.add_argument("--dry-run", action="store_true", help="list objects without uploading")
    args = parser.parse_args()
    source = Path(args.source).expanduser().resolve()
    if not source.exists():
        print(f"No filesystem object-store directory found at {source}; nothing to migrate.")
        return 0

    try:
        import boto3
        from botocore.client import Config
        from botocore.exceptions import ClientError
    except ImportError as exc:
        raise SystemExit("boto3 is required; install the deployment requirements first") from exc

    endpoint = os.environ.get("MYOTA_OBJECT_STORAGE_ENDPOINT", "http://seaweedfs:8333")
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ.get("MYOTA_OBJECT_STORAGE_ACCESS_KEY", "myota-s3"),
        aws_secret_access_key=os.environ.get("MYOTA_OBJECT_STORAGE_SECRET_KEY", "myota-s3-dev-only"),
        region_name=os.environ.get("MYOTA_OBJECT_STORAGE_REGION", "us-east-1"),
        config=Config(signature_version="s3v4", s3={"addressing_style": os.environ.get("MYOTA_OBJECT_STORAGE_ADDRESSING_STYLE", "path")}),
    )

    copied = 0
    for bucket_path in sorted(path for path in source.iterdir() if path.is_dir()):
        bucket = bucket_path.name
        if not args.dry_run:
            try:
                client.head_bucket(Bucket=bucket)
            except ClientError as exc:
                status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                if status != 404:
                    raise
                client.create_bucket(Bucket=bucket)
        for object_path in sorted(path for path in bucket_path.rglob("*") if path.is_file()):
            key = object_path.relative_to(bucket_path).as_posix()
            content_type = mimetypes.guess_type(object_path.name)[0] or "application/octet-stream"
            print(f"{'would copy' if args.dry_run else 'copying'} s3://{bucket}/{key}")
            if not args.dry_run:
                client.upload_file(str(object_path), bucket, key, ExtraArgs={"ContentType": content_type})
            copied += 1
    print(f"Processed {copied} filesystem object(s) from {source}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

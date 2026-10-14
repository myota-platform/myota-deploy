#!/usr/bin/env python3
"""Copy MyOTA's live application buckets into the isolated test SeaweedFS."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Iterator
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


BUCKETS = (
    "myota-award-assets",
    "myota-award-signatures",
    "myota-certificates",
    "myota-adif",
    "myota-geodata-imports",
)
COPY_FIELDS = (
    "CacheControl",
    "ContentDisposition",
    "ContentEncoding",
    "ContentLanguage",
    "ContentType",
    "Expires",
)


def client(endpoint: str, access_key: str, secret_key: str) -> Any:
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name="us-east-1",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(s3={"addressing_style": "path"}),
    )


def objects(s3: Any, bucket: str) -> Iterator[dict[str, Any]]:
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        yield from page.get("Contents", [])


def main() -> None:
    source = client(
        os.environ["LIVE_S3_ENDPOINT"],
        os.environ["LIVE_S3_ACCESS_KEY"],
        os.environ["LIVE_S3_SECRET_KEY"],
    )
    target = client(
        os.environ["TEST_S3_ENDPOINT"],
        os.environ["AWS_ACCESS_KEY_ID"],
        os.environ["AWS_SECRET_ACCESS_KEY"],
    )
    for bucket in BUCKETS:
        try:
            source.head_bucket(Bucket=bucket)
        except ClientError as error:
            if (
                error.response.get("ResponseMetadata", {}).get(
                    "HTTPStatusCode"
                )
                == 404
            ):
                print(f"Source bucket absent, skipping {bucket}")
                continue
            raise
        try:
            target.head_bucket(Bucket=bucket)
        except ClientError as error:
            if (
                error.response.get("ResponseMetadata", {}).get(
                    "HTTPStatusCode"
                )
                != 404
            ):
                raise
            target.create_bucket(Bucket=bucket)

        count = 0
        byte_count = 0
        for item in objects(source, bucket):
            key = item["Key"]
            result = source.get_object(Bucket=bucket, Key=key)
            body = result["Body"]
            try:
                with tempfile.SpooledTemporaryFile(
                    max_size=8 * 1024 * 1024
                ) as payload:
                    shutil.copyfileobj(body, payload)
                    payload.seek(0)
                    request: dict[str, Any] = {
                        "Bucket": bucket,
                        "Key": key,
                        "Body": payload,
                        "ContentLength": int(result["ContentLength"]),
                        "Metadata": result.get("Metadata", {}),
                    }
                    request.update(
                        {
                            field: result[field]
                            for field in COPY_FIELDS
                            if field in result
                        }
                    )
                    target.put_object(**request)
            finally:
                body.close()
            tags = source.get_object_tagging(Bucket=bucket, Key=key).get(
                "TagSet", []
            )
            if tags:
                target.put_object_tagging(
                    Bucket=bucket,
                    Key=key,
                    Tagging={"TagSet": tags},
                )
            count += 1
            byte_count += int(item.get("Size", 0))
        print(f"Copied bucket {bucket}: {count} objects, {byte_count} bytes")


if __name__ == "__main__":
    main()

"""
AWS Operations
Part of SOVEREIGN PYTHON LLM ENGINE

AWS cloud operations using boto3.
"""

from typing import Any
from pathlib import Path
from dataclasses import dataclass

from ...core.evidence import WORMLedger


@dataclass
class S3Object:
    """S3 object metadata"""
    key: str
    size: int
    last_modified: str
    etag: str


class AWSOperations:
    """
    AWS cloud operations.

    Supports:
    - S3 (storage)
    - Lambda (functions)
    - Secrets Manager
    - SSM Parameter Store
    """

    def __init__(
        self,
        region: str = "us-east-1",
        worm_ledger: WORMLedger | None = None
    ):
        """
        Initialize AWS operations.

        Args:
            region: AWS region
            worm_ledger: Optional WORM ledger
        """
        self.region = region
        self.worm_ledger = worm_ledger

        try:
            import boto3
        except ImportError:
            raise ImportError("boto3 is required. Install: pip install boto3")

        self.boto3 = boto3

    # S3 Operations

    async def s3_upload(
        self,
        bucket: str,
        key: str,
        file_path: Path
    ) -> str:
        """
        Upload file to S3.

        Args:
            bucket: S3 bucket name
            key: Object key
            file_path: Local file path

        Returns:
            S3 URL
        """
        import asyncio

        def _sync_upload():
            s3 = self.boto3.client("s3", region_name=self.region)
            s3.upload_file(str(file_path), bucket, key)
            return f"s3://{bucket}/{key}"

        url = await asyncio.to_thread(_sync_upload)

        # Log to WORM
        if self.worm_ledger:
            await self.worm_ledger.append({
                "event": "s3_upload",
                "bucket": bucket,
                "key": key,
                "size": file_path.stat().st_size
            })

        return url

    async def s3_download(
        self,
        bucket: str,
        key: str,
        file_path: Path
    ) -> None:
        """
        Download file from S3.

        Args:
            bucket: S3 bucket name
            key: Object key
            file_path: Local file path
        """
        import asyncio

        def _sync_download():
            s3 = self.boto3.client("s3", region_name=self.region)
            s3.download_file(bucket, key, str(file_path))

        await asyncio.to_thread(_sync_download)

    async def s3_list(
        self,
        bucket: str,
        prefix: str = ""
    ) -> list[S3Object]:
        """
        List objects in S3 bucket.

        Args:
            bucket: S3 bucket name
            prefix: Optional prefix filter

        Returns:
            List of S3Object
        """
        import asyncio

        def _sync_list():
            s3 = self.boto3.client("s3", region_name=self.region)
            response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)

            objects = []
            for obj in response.get("Contents", []):
                objects.append(S3Object(
                    key=obj["Key"],
                    size=obj["Size"],
                    last_modified=obj["LastModified"].isoformat(),
                    etag=obj["ETag"]
                ))

            return objects

        return await asyncio.to_thread(_sync_list)

    async def s3_delete(
        self,
        bucket: str,
        key: str
    ) -> None:
        """
        Delete object from S3.

        Args:
            bucket: S3 bucket name
            key: Object key
        """
        import asyncio

        def _sync_delete():
            s3 = self.boto3.client("s3", region_name=self.region)
            s3.delete_object(Bucket=bucket, Key=key)

        await asyncio.to_thread(_sync_delete)

        # Log to WORM
        if self.worm_ledger:
            await self.worm_ledger.append({
                "event": "s3_delete",
                "bucket": bucket,
                "key": key
            })

    # Secrets Manager Operations

    async def get_secret(
        self,
        secret_id: str
    ) -> dict[str, Any]:
        """
        Get secret from Secrets Manager.

        Args:
            secret_id: Secret ID or ARN

        Returns:
            Secret value (as dict if JSON)
        """
        import asyncio
        import json

        def _sync_get_secret():
            sm = self.boto3.client("secretsmanager", region_name=self.region)
            response = sm.get_secret_value(SecretId=secret_id)

            secret_string = response["SecretString"]

            # Try to parse as JSON
            try:
                return json.loads(secret_string)
            except json.JSONDecodeError:
                return {"value": secret_string}

        return await asyncio.to_thread(_sync_get_secret)

    async def put_secret(
        self,
        secret_id: str,
        secret_value: dict[str, Any] | str
    ) -> None:
        """
        Put secret to Secrets Manager.

        Args:
            secret_id: Secret ID
            secret_value: Secret value (dict or string)
        """
        import asyncio
        import json

        def _sync_put_secret():
            sm = self.boto3.client("secretsmanager", region_name=self.region)

            # Convert dict to JSON string
            if isinstance(secret_value, dict):
                secret_string = json.dumps(secret_value)
            else:
                secret_string = secret_value

            try:
                sm.update_secret(SecretId=secret_id, SecretString=secret_string)
            except sm.exceptions.ResourceNotFoundException:
                sm.create_secret(Name=secret_id, SecretString=secret_string)

        await asyncio.to_thread(_sync_put_secret)

        # Log to WORM
        if self.worm_ledger:
            await self.worm_ledger.append({
                "event": "secrets_manager_put",
                "secret_id": secret_id
            })

    # Lambda Operations

    async def invoke_lambda(
        self,
        function_name: str,
        payload: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Invoke Lambda function.

        Args:
            function_name: Function name or ARN
            payload: Function payload

        Returns:
            Function response
        """
        import asyncio
        import json

        def _sync_invoke():
            lambda_client = self.boto3.client("lambda", region_name=self.region)

            response = lambda_client.invoke(
                FunctionName=function_name,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload)
            )

            result_payload = json.loads(response["Payload"].read())
            return result_payload

        result = await asyncio.to_thread(_sync_invoke)

        # Log to WORM
        if self.worm_ledger:
            await self.worm_ledger.append({
                "event": "lambda_invoke",
                "function": function_name
            })

        return result


# Tool registration helpers
async def s3_upload_tool(
    bucket: str,
    key: str,
    file_path: str,
    region: str = "us-east-1"
) -> dict:
    """Upload to S3 tool"""
    aws = AWSOperations(region=region)
    url = await aws.s3_upload(bucket, key, Path(file_path))

    return {
        "url": url,
        "bucket": bucket,
        "key": key
    }


async def s3_list_tool(
    bucket: str,
    prefix: str = "",
    region: str = "us-east-1"
) -> dict:
    """List S3 objects tool"""
    aws = AWSOperations(region=region)
    objects = await aws.s3_list(bucket, prefix)

    return {
        "objects": [
            {
                "key": obj.key,
                "size": obj.size,
                "last_modified": obj.last_modified
            }
            for obj in objects
        ],
        "count": len(objects)
    }


async def get_secret_tool(
    secret_id: str,
    region: str = "us-east-1"
) -> dict:
    """Get secret tool"""
    aws = AWSOperations(region=region)
    secret = await aws.get_secret(secret_id)

    return {
        "secret_id": secret_id,
        "value": secret
    }


async def invoke_lambda_tool(
    function_name: str,
    payload: dict,
    region: str = "us-east-1"
) -> dict:
    """Invoke Lambda tool"""
    aws = AWSOperations(region=region)
    result = await aws.invoke_lambda(function_name, payload)

    return {
        "function": function_name,
        "result": result
    }

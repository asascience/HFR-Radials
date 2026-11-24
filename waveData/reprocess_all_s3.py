import asyncio
import aioboto3
import os
import json

BUCKET_NAME = 'rps-nccf-hfrnet-dissemination-uat'
PROCESSED_BUCKET = os.environ.get("PROCESSED_ROOT", "rps-nccf-hfrnet-processed-uat").replace("s3://", "")
PREFIX = 'waves'
LAMBDA_FUNCTION = 'convert_hfr_wave_data_to_csv'

async def head_object_exists(s3_client, bucket, key):
    try:
        await s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except s3_client.exceptions.ClientError:
        return False

async def process_object(s3_client, lambda_client, obj):
    key = obj["Key"]
    print(key)

    s3_loc = f"s3://{BUCKET_NAME}/{key}"
    print(s3_loc)

    csv_key = key.rsplit(".", 1)[0] + ".csv"
    exists = await head_object_exists(s3_client, PROCESSED_BUCKET, csv_key)

    if exists:
        print(f"Output exists for {csv_key}, skipping invocation.")
        return

    print(f"Attempting data backfill for {csv_key}")
    event = {
        "Records": [
            {"s3": {"bucket": {"name": BUCKET_NAME}, "object": {"key": key}}}
        ]
    }

    response = await lambda_client.invoke(
        FunctionName=LAMBDA_FUNCTION,
        InvocationType='Event',  # asynchronous invocation
        Payload=json.dumps(event).encode('utf-8')
    )
    print(f"Invoked Lambda for {key}, StatusCode: {response['StatusCode']}")

async def main():
    session = aioboto3.Session()
    async with session.client('s3') as s3_client, session.client('lambda') as lambda_client:
        paginator = s3_client.get_paginator('list_objects_v2')
        async for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=PREFIX):
            if 'Contents' in page:
                tasks = [
                    process_object(s3_client, lambda_client, obj)
                    for obj in page['Contents']
                ]
                await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())

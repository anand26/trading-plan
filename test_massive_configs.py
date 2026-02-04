"""Test different S3 configurations for Massive.com"""

import boto3
from botocore.config import Config
import os

os.makedirs('./Data/massive', exist_ok=True)

ACCESS_KEY = '49396bfa-bc7d-4998-b177-bfe701369439'
SECRET_KEY = 'WCZBkB2cU6m8sU4YNejf5lR704GPwuQh'
ENDPOINT = 'https://files.massive.com'
BUCKET = 'flatfiles'
TEST_KEY = 'us_stocks_sip/minute_aggs_v1/2025/01/2025-01-02.csv.gz'

configs_to_try = [
    # Config 1: Original
    {
        'name': 'Original (s3v4)',
        'config': Config(signature_version='s3v4'),
    },
    # Config 2: Path style addressing
    {
        'name': 'Path style + s3v4',
        'config': Config(signature_version='s3v4', s3={'addressing_style': 'path'}),
    },
    # Config 3: Virtual style addressing
    {
        'name': 'Virtual style + s3v4',
        'config': Config(signature_version='s3v4', s3={'addressing_style': 'virtual'}),
    },
    # Config 4: No signature version specified
    {
        'name': 'Path style (no sig version)',
        'config': Config(s3={'addressing_style': 'path'}),
    },
    # Config 5: With region
    {
        'name': 'With us-east-1 region',
        'config': Config(signature_version='s3v4', s3={'addressing_style': 'path'}),
        'region': 'us-east-1',
    },
]

for cfg in configs_to_try:
    print(f"\n{'='*60}")
    print(f"Testing: {cfg['name']}")
    print('='*60)
    
    try:
        session = boto3.Session(
            aws_access_key_id=ACCESS_KEY,
            aws_secret_access_key=SECRET_KEY,
            region_name=cfg.get('region', None),
        )
        
        s3 = session.client(
            's3',
            endpoint_url=ENDPOINT,
            config=cfg['config'],
        )
        
        # Test listing first
        print("Testing list_objects_v2...")
        response = s3.list_objects_v2(Bucket=BUCKET, Prefix='us_stocks_sip/minute_aggs_v1/2025/01/', MaxKeys=3)
        if 'Contents' in response:
            print(f"  [OK] Listed {len(response['Contents'])} objects")
            for obj in response['Contents'][:2]:
                print(f"       - {obj['Key']}")
        
        # Test download
        print(f"\nTesting download: {TEST_KEY}")
        response = s3.get_object(Bucket=BUCKET, Key=TEST_KEY)
        content = response['Body'].read(1000)  # Just read first 1000 bytes
        print(f"  [OK] Downloaded! First bytes: {len(content)}")
        print(f"  Content-Type: {response.get('ContentType', 'unknown')}")
        break  # Success! Stop trying
        
    except Exception as e:
        print(f"  [FAIL] {e}")

print("\n" + "="*60)
print("Testing complete")
print("="*60)

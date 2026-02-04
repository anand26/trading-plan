"""Explore Massive.com bucket structure and test downloads."""

import boto3
from botocore.config import Config

session = boto3.Session(
    aws_access_key_id='49396bfa-bc7d-4998-b177-bfe701369439',
    aws_secret_access_key='WCZBkB2cU6m8sU4YNejf5lR704GPwuQh',
)

s3 = session.client(
    's3',
    endpoint_url='https://files.massive.com',
    config=Config(signature_version='s3v4'),
)

BUCKET = 'flatfiles'

def explore_prefix(prefix, depth=0, max_depth=3):
    """Recursively explore a prefix."""
    if depth > max_depth:
        return
    
    indent = "  " * depth
    try:
        response = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix, Delimiter='/', MaxKeys=20)
        
        # Print sub-prefixes
        for p in response.get('CommonPrefixes', []):
            print(f"{indent}[DIR] {p['Prefix']}")
            if depth < max_depth:
                explore_prefix(p['Prefix'], depth + 1, max_depth)
        
        # Print files (first 5)
        for obj in response.get('Contents', [])[:5]:
            print(f"{indent}[FILE] {obj['Key']} ({obj['Size']} bytes)")
            
    except Exception as e:
        print(f"{indent}Error: {e}")


def test_download(key):
    """Test downloading a specific file."""
    print(f"\nTesting download: {key}")
    try:
        response = s3.get_object(Bucket=BUCKET, Key=key)
        content = response['Body'].read()
        print(f"  SUCCESS! Downloaded {len(content)} bytes")
        
        # Show first 500 chars if it's text
        import gzip
        import io
        if key.endswith('.gz'):
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as gz:
                text = gz.read(1000).decode('utf-8', errors='ignore')
                print(f"  Preview:\n{text[:500]}")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False


def main():
    print("=" * 60)
    print("Exploring Massive.com Flat Files Bucket")
    print("=" * 60)
    
    # Explore root
    print("\n=== Root Level ===")
    explore_prefix('', depth=0, max_depth=1)
    
    # Explore us_stocks_sip specifically
    print("\n=== US Stocks SIP Structure ===")
    explore_prefix('us_stocks_sip/', depth=0, max_depth=2)
    
    # List some recent files
    print("\n=== Recent minute_aggs files (2025) ===")
    try:
        response = s3.list_objects_v2(
            Bucket=BUCKET, 
            Prefix='us_stocks_sip/minute_aggs_v1/2025/01/',
            MaxKeys=10
        )
        for obj in response.get('Contents', []):
            print(f"  {obj['Key']} ({obj['Size']} bytes)")
            # Try to download first one
            test_download(obj['Key'])
            break
    except Exception as e:
        print(f"  Error: {e}")
    
    # Also check if there are other paths
    print("\n=== Checking alternative paths ===")
    alt_prefixes = [
        'stocks/',
        'equity/',
        'minute/',
        'tqqq/',
        'TQQQ/',
    ]
    for prefix in alt_prefixes:
        try:
            response = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix, MaxKeys=5)
            if response.get('Contents'):
                print(f"  Found data at: {prefix}")
                for obj in response.get('Contents', [])[:3]:
                    print(f"    {obj['Key']}")
        except:
            pass


if __name__ == "__main__":
    main()

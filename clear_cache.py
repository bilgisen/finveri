import os
import sys

# Add parent directory to path to allow importing app module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.redis_client import get_redis

def clear_summary_cache():
    print("Connecting to Upstash Redis...")
    r = get_redis()
    
    # In Upstash Redis, we can get keys matching a pattern
    try:
        keys = r.keys("summary:text:*")
        print(f"Found summary keys: {keys}")
        if keys:
            count = 0
            for key in keys:
                # Key might be string or bytes
                key_str = key if isinstance(key, str) else key.decode('utf-8') if hasattr(key, 'decode') else str(key)
                r.delete(key_str)
                print(f"Deleted key: {key_str}")
                count += 1
            print(f"Successfully cleared {count} cached summary keys!")
        else:
            print("No cached summary keys found.")
    except Exception as e:
        print(f"Error while clearing Redis keys: {e}")

if __name__ == "__main__":
    clear_summary_cache()

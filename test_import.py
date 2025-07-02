import sys
print("Attempting to import cryptography.fernet", file=sys.stderr)
try:
    from cryptography.fernet import Fernet
    print("Successfully imported cryptography.fernet", file=sys.stderr)
    # Try to instantiate it to see if that triggers anything
    Fernet.generate_key()
    print("Successfully instantiated Fernet and generated key", file=sys.stderr)
except Exception as e:
    print(f"Error importing or using cryptography.fernet: {e}", file=sys.stderr)
    sys.exit(1)
print("Script finished.", file=sys.stderr)

import firebase_admin
from firebase_admin import credentials, storage
import os

# Get the absolute path to the directory where this file is located
dir_path = os.path.dirname(os.path.realpath(__file__))
# Construct the path to the service account key file
# This assumes 'serviceAccountKey.json' is in the root directory
key_path = os.path.join(dir_path, "..", "..", "serviceAccountKey.json")

# TODO: Replace 'your-bucket-name.appspot.com' with your actual Firebase Storage bucket name.
BUCKET_NAME = 'your-bucket-name.appspot.com'

# Check if the service account key file exists.
# If you have not done so, download it from your Firebase project settings
# and place it in the root of this project as 'serviceAccountKey.json'.
if not os.path.exists(key_path):
    raise FileNotFoundError(
        f"serviceAccountKey.json not found at {os.path.abspath(key_path)}. "
        "Please add it to the root directory of the project."
    )

try:
    # Try to get the default app if it's already initialized.
    firebase_admin.get_app()
except ValueError:
    # If the app is not initialized, initialize it.
    cred = credentials.Certificate(key_path)
    firebase_admin.initialize_app(cred, {
        'storageBucket': BUCKET_NAME
    })

# Get a reference to the storage bucket.
bucket = storage.bucket()

import pytest
import subprocess
import os
import hashlib
import tempfile

# Path to the built binary
BINARY_PATH = os.path.join(os.path.dirname(__file__), "..", "dist", "gphoto-get")


def calculate_sha256(filepath):
    """Calculates the SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def test_gphoto_get_integration():
    """
    Integration test that runs the built binary against a known URL
    and verifies the downloaded file's name and SHA256 hash.
    """
    # Ensure binary exists
    if not os.path.exists(BINARY_PATH):
        pytest.fail(f"Binary not found at {BINARY_PATH}. Please run ./build.sh first.")

    target_url = "https://photos.app.goo.gl/37BDAZgMJ9XCPzke8"
    expected_filename = "OlxzhFkv.png"
    expected_sha256 = "87aea14c3c6cf8ad73291f24c878d6d360145cf8b5389588a7bfc658cffa6ffd"

    with tempfile.TemporaryDirectory() as tmpdirname:
        print(f"Running binary against {target_url} in {tmpdirname}")

        # Execute the binary
        result = subprocess.run(
            [BINARY_PATH, target_url, "-o", tmpdirname, "--verbose"],
            capture_output=True,
            text=True,
        )

        # Check return code
        if result.returncode != 0:
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)

        assert result.returncode == 0, "Binary execution failed"

        # Check if file exists
        downloaded_file = os.path.join(tmpdirname, expected_filename)
        assert os.path.exists(downloaded_file), (
            f"Expected file {expected_filename} not found in output directory"
        )

        # Check SHA256 hash
        actual_sha256 = calculate_sha256(downloaded_file)
        assert actual_sha256 == expected_sha256, (
            f"SHA256 mismatch. Expected {expected_sha256}, got {actual_sha256}"
        )

import requests
import argparse
import sys
from justhtml import JustHTML
import re
import json
import os
import mimetypes
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
)
from rich.theme import Theme

# Setup Rich Console
custom_theme = Theme(
    {
        "info": "dim cyan",
        "warning": "magenta",
        "danger": "bold red",
        "success": "green",
        "url": "underline blue",
    }
)
console = Console(theme=custom_theme)


def log(message, verbose=False, style="info"):
    """Prints a message only if verbose is True, or uses console.print if not verbose controlled."""
    if verbose:
        console.print(message, style=style)


def resolve_url(url, verbose=False):
    """
    Resolves the short URL (e.g., photos.app.goo.gl) to the full URL.
    """
    log(f"Resolving: {url}...", verbose)
    try:
        response = requests.head(url, allow_redirects=True)
        if response.status_code != 200:
            response = requests.get(url, allow_redirects=True, stream=True)
            response.close()

        final_url = response.url
        log(f"Resolved to: {final_url}", verbose)
        return final_url
    except Exception as e:
        console.print(f"Error resolving URL: {e}", style="danger")
        return None


def fetch_page_content(url, verbose=False):
    """
    Fetches the HTML content of a given URL.
    """
    log(f"Fetching page content from: {url}...", verbose)
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        log(
            f"Successfully fetched page content ({len(response.text)} bytes)",
            verbose,
            style="success",
        )
        return response.text
    except requests.exceptions.RequestException as e:
        console.print(f"Error fetching page content from {url}: {e}", style="danger")
        return None


def check_file_exists(output_dir, base_name):
    """Checks if a file with the base_name exists in output_dir (ignoring extension)."""
    if not os.path.exists(output_dir):
        return None

    for existing_file in os.listdir(output_dir):
        # We look for files starting with base_name
        if existing_file.startswith(base_name) and os.path.isfile(
            os.path.join(output_dir, existing_file)
        ):
            # Strict check: ensure the stem matches exactly
            name_part, _ = os.path.splitext(existing_file)
            if name_part == base_name:
                return os.path.join(output_dir, existing_file)
    return None


def download_photo(url, output_dir, photo_id, verbose=False):
    """
    Downloads a photo. Returns the filepath if successful, None if failed.
    """
    base_name = photo_id

    log(f"Processing {url}...", verbose)
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type")
        extension = mimetypes.guess_extension(content_type)

        if not extension:
            if "image/jpeg" in content_type:
                extension = ".jpg"
            elif "image/png" in content_type:
                extension = ".png"
            elif "video/mp4" in content_type:
                extension = ".mp4"
            else:
                extension = ".bin"

        filename = f"{base_name}{extension}"
        filepath = os.path.join(output_dir, filename)

        log(f"Downloading to {filepath}...", verbose)
        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        log(f"Successfully downloaded {filename}", verbose, style="success")
        return filepath
    except requests.exceptions.RequestException as e:
        console.print(f"Error downloading {url}: {e}", style="danger")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Google Photos Shared Album Downloader"
    )
    parser.add_argument("url", help="Shared album URL")
    parser.add_argument("-o", "--output-dir", default=".", help="Output directory")
    parser.add_argument(
        "-s", "--sync", action="store_true", help="Sync mode (skip existing)"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    # 1. Resolve URL
    full_url = resolve_url(args.url, args.verbose)
    if not full_url:
        sys.exit(1)

    # 2. Fetch Content
    with console.status("[bold green]Fetching album metadata...") as status:
        html_content = fetch_page_content(full_url, args.verbose)
        if not html_content:
            sys.exit(1)

        doc = JustHTML(html_content)
        script_tags = doc.query("script")

        photo_entries_found = []

        status.update("[bold green]Parsing photos...")
        for script in script_tags:
            script_content = script.to_text()
            if script_content and "AF_initDataCallback" in script_content:
                match = re.search(
                    r"AF_initDataCallback\((.*?)\);?", script_content, re.DOTALL
                )
                if match:
                    full_json_arg_str = match.group(1)
                    cleaned_json_str = full_json_arg_str.replace("'", '"')
                    cleaned_json_str = re.sub(
                        r"([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:",
                        r'\1"\2":',
                        cleaned_json_str,
                    )

                    try:
                        parsed_callback_data = json.loads(cleaned_json_str)
                        data_array = parsed_callback_data.get("data")

                        if (
                            data_array
                            and isinstance(data_array, list)
                            and len(data_array) > 1
                            and isinstance(data_array[1], list)
                        ):
                            photos_data = data_array[1]
                            for photo_entry in photos_data:
                                if (
                                    isinstance(photo_entry, list)
                                    and len(photo_entry) > 1
                                    and isinstance(photo_entry[1], list)
                                    and len(photo_entry[1]) > 0
                                    and isinstance(photo_entry[1][0], str)
                                    and "googleusercontent.com" in photo_entry[1][0]
                                ):
                                    raw_id = photo_entry[0]
                                    photo_url = photo_entry[1][0]

                                    clean_id = raw_id
                                    if isinstance(clean_id, str) and len(clean_id) >= 6:
                                        # Strip first 6 chars, then take the next 8 chars
                                        clean_id = clean_id[6:14]

                                    photo_entries_found.append((photo_url, clean_id))
                    except json.JSONDecodeError:
                        pass

    total_photos = len(photo_entries_found)
    if total_photos == 0:
        console.print("No photos found in album.", style="warning")
        sys.exit(0)

    # 3. Analyze Sync State
    to_download = []
    skipped_count = 0

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    console.print(f"Found [bold]{total_photos}[/bold] photos in album.")

    if args.sync:
        with console.status("[bold green]Checking existing files...") as status:
            for url, pid in photo_entries_found:
                existing = check_file_exists(args.output_dir, pid)
                if existing:
                    skipped_count += 1
                    log(f"Skipping {pid} (exists)", args.verbose, style="info")
                else:
                    to_download.append((url, pid))
    else:
        to_download = photo_entries_found

    console.print(
        f"Local: [bold]{skipped_count}[/bold] | To Download: [bold]{len(to_download)}[/bold]"
    )

    # 4. Download Loop
    if not to_download:
        console.print("[bold green]All photos up to date![/bold]")
        sys.exit(0)

    success_count = 0
    fail_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=True,  # Disappear when done
    ) as progress:
        task = progress.add_task("[cyan]Downloading...", total=len(to_download))

        for url, pid in to_download:
            result = download_photo(url, args.output_dir, pid, args.verbose)
            if result:
                success_count += 1
            else:
                fail_count += 1
            progress.advance(task)

    # 5. Summary
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Total Album: {total_photos}")
    console.print(f"  Skipped:     {skipped_count}")
    console.print(f"  Downloaded:  [green]{success_count}[/green]")
    if fail_count > 0:
        console.print(f"  Failed:      [red]{fail_count}[/red]")

    console.print(f"Output Directory: [blue]{os.path.abspath(args.output_dir)}[/blue]")


if __name__ == "__main__":
    main()

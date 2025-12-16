# gphoto-get

Google Photos Shared Album Downloader.

## Usage

```bash
gphoto-get <URL>
```

## Development

### Install Dependencies

```bash
uv sync
```

### Build Binary

```bash
uv run --with pyinstaller pyinstaller --onefile gphoto_get.py --name gphoto-get
```

The executable will be located in `dist/gphoto-get`.

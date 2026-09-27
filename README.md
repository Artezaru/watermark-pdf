# watermark-pdf

watermark-pdf is a local, offline desktop application (PyQt5) to add a repeated text watermark to your PDF files — a single document or a whole folder at once.

Everything runs on your own machine — your documents are never uploaded anywhere, and no internet connection is required.

## Features

- **Single file or whole folder**: watermark one PDF, or every PDF in a folder (optionally including subfolders, whose structure is reproduced in the output).
- **Live preview**: see exactly what the result will look like while you type — same position, angle, font size and line spacing as the generated PDF — on the real page size of your document or on a standard format (A3, A4, A5, Letter, Legal, portrait or landscape).
- **Fully customizable watermark**: multi-line text, font (the 12 standard PDF fonts), size, color, opacity, rotation angle, number of columns and rows, and page margin.
- **Safe output**: files are saved with a suffix of your choice (e.g. `report_watermarked.pdf`), or overwrite the originals if you leave the suffix empty. Files are written atomically, so an interrupted run never leaves a half-written PDF.
- **Faithful to the original document**: bookmarks, metadata, links and form fields are preserved; rotated and cropped pages are handled correctly so the watermark always appears upright and centered.
- **Drag & drop**: drop a PDF or a folder onto the window to select it.
- **Progress and cancellation**: page-by-page progress bar, a cancel button that stops the processing immediately, and a log of every file created.
- **Light/dark theme** and **5 languages** (English, French, Spanish, Italian, German); your settings are remembered between runs.

## Installing

### Prebuilt executables (recommended for most users)

Download the latest release for your platform from the [Releases page](https://github.com/Artezaru/watermark-pdf/releases):

- **Windows**: download and run `watermark-pdf-windows.exe` directly — no installation needed.
- **Linux (Debian/Ubuntu)**: download the `.deb` package and install it with:
  ```bash
  sudo dpkg -i watermark-pdf_*.deb
  ```
  watermark-pdf will then appear in your applications menu as *PDF Watermark*, or can be launched from a terminal with `watermark-pdf`.

### From source (developers)

Requires Python 3.10 or later.

```bash
git clone https://github.com/Artezaru/watermark-pdf.git
cd watermark-pdf
pip install .
```

Run it with:

```bash
watermark-pdf
```

or:

```bash
python -m watermark_pdf
```

## Using it as a Python library

The watermarking engine can also be used without the interface:

```python
from watermark_pdf.watermark import add_watermark, batch_watermark_directory

# One file -> report_watermarked.pdf
add_watermark(
    "report.pdf",
    "CONFIDENTIAL\nDo not distribute",
    horizontal_boxes=3,
    vertical_boxes=6,
    opacity=0.15,
    angle=45,
    color="#DC2626",
    font="Helvetica-Bold",
    size=24,
)

# Every PDF of a folder -> documents_watermarked/
batch_watermark_directory("documents", "CONFIDENTIAL", recursive=True)
```

Install the optional `tqdm` dependency (`pip install .[progress]`) to get a progress bar in the console.

## Building the executables yourself

watermark-pdf uses [PyInstaller](https://pyinstaller.org/) to produce standalone executables. From the project root:

```bash
pip install pyinstaller pillow
pyinstaller --name watermark-pdf --windowed --onefile \
    --add-data "watermark_pdf/resources:watermark_pdf/resources" \
    --icon watermark_pdf/resources/app.png \
    watermark_pdf/__main__.py
```

(On Windows, replace the `:` in `--add-data` with `;`.)

A GitHub Actions workflow is included (`.github/workflows/build.yml`) that builds Windows and Linux executables (plus a `.deb` package) automatically and publishes them to a GitHub Release whenever a `v*` tag is pushed.

## Credits

The application icon is from Flaticon: <a href="https://www.flaticon.com/free-icons/watermark" title="watermark icons">Watermark icons created by Magnific - Flaticon</a>.

## License

watermark-pdf is free software, licensed under the **GNU General Public License v3.0 or later** — see [LICENSE](LICENSE) for the full text.

## Contributing

Bug reports and pull requests are welcome — please open an issue on the [tracker](https://github.com/Artezaru/watermark-pdf/issues) first to discuss any significant change.

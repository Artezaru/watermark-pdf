# watermark-pdf

watermark-pdf is a local, offline desktop application (PyQt5) to add a text watermark to your PDF files — a single document or a whole folder at once.

Everything runs on your own machine: your documents are never uploaded anywhere, and no internet connection is required.

![watermark-pdf interface](https://raw.githubusercontent.com/Artezaru/watermark-pdf/master/watermark_pdf/resources/ui.png)

## Features

- **One file or a whole folder**, subfolders included if you want.
- **Live preview** that matches the generated PDF exactly.
- **Customizable watermark**: multi-line text, font, size, color, opacity, angle, grid and margin.
- **Safe output**: files saved with a suffix of your choice (or overwrite the originals), written atomically.
- **Faithful to the original**: bookmarks, metadata, links and form fields are preserved; rotated and cropped pages are handled.
- **Drag & drop**, progress bar, cancellation and log.
- **Light/dark theme** and **5 languages** (English, French, Spanish, Italian, German).

## Installing

### Prebuilt executables (recommended)

Download the latest release for your platform from the [Releases page](https://github.com/Artezaru/watermark-pdf/releases):

- **Windows**: download and run `watermark-pdf-windows.exe` directly, no installation needed.
- **Linux (Debian/Ubuntu)**: download the `.deb` package and install it with:
  ```bash
  sudo dpkg -i watermark-pdf_*.deb
  ```
  watermark-pdf then appears in your applications menu as *PDF Watermark*, or can be launched from a terminal with `watermark-pdf`.

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

## Credits

The application icon is from Flaticon: <a href="https://www.flaticon.com/free-icons/watermark" title="watermark icons">Watermark icons created by Magnific - Flaticon</a>.

## License

watermark-pdf is free software, licensed under the **GNU General Public License v3.0 or later**. See [LICENSE](LICENSE) for the full text.

## Contributing

Bug reports and pull requests are welcome. Please open an issue on the [tracker](https://github.com/Artezaru/watermark-pdf/issues) first to discuss any significant change.

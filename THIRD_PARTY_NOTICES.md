# Third-party components

AI-ditor Plus source code is MIT licensed (see LICENSE). Dependencies retain their own licenses.

PDF images in editable Word output are rendered locally using [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) and [PDFium](https://pdfium.googlesource.com/pdfium/). pypdfium2 uses Apache-2.0 or BSD-3-Clause; PDFium and its bundled dependencies include additional notices. Their license texts and binary build notices are distributed in the application under `pypdfium2-*.dist-info/licenses/` (macOS: inside Contents/Resources). No article contents are sent to an external conversion service.

Other dependencies include Python, Flask/Werkzeug/Jinja, python-docx, lxml, Pillow, pypdf, pywebview and the operating system's embedded browser. Source installations obtain the dependency licenses with the Python packages. Generated articles retain the license selected by their authors/journals; neither the application MIT license nor dependency licenses assign an article license.

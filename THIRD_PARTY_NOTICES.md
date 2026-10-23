# OCR components

This application includes RapidOCR 3.9.2, copyright 2021 RapidOCR Authors,
licensed under Apache License 2.0. Its bundled ONNX recognition models are
derived from PaddleOCR models, whose upstream rights are held by Baidu and the
respective contributors and are distributed under Apache License 2.0.

Source and model attribution: https://github.com/RapidAI/RapidOCR
License text: `THIRD_PARTY_LICENSES/Apache-2.0.txt`

# Office format libraries

Office conversions use python-docx, openpyxl, python-pptx, odfpy, striprtf,
and ReportLab. The release does not contain LibreOffice. odfpy is distributed
under the Apache License 2.0 and GPL v2+ options; striprtf uses BSD 3-Clause.
The respective source and license files are available at
https://github.com/eea/odfpy and https://github.com/joshy/striprtf .

# python-pptx

The Dazzle workspace uses python-pptx 1.0.2 for PowerPoint files.
It is licensed under MIT. The license is at
`THIRD_PARTY_LICENSES/python-pptx-MIT.txt`.

# Windows Office automation

Windows downloads include pywin32 to invoke an installed Microsoft Office
application through its documented COM interface. pywin32's package metadata
identifies the Python Software Foundation license; its COM and Win32 component
license texts are at `THIRD_PARTY_LICENSES/pywin32-com-License.txt` and
`THIRD_PARTY_LICENSES/pywin32-win32-License.txt`. Microsoft Office and
LibreOffice are not included in the download.

# WatchIT playback

WatchIT uses the unmodified VLC/libVLC runtime and its plugins from VideoLAN,
plus the `python-vlc` Python binding. The VLC runtime contains components under
GPL, LGPL, and other compatible free software licenses. See the bundled
`VLC-COPYING.txt` and the component notices in the upstream distribution.
The `python-vlc` binding is LGPL 2.1 or later; its license is at
`THIRD_PARTY_LICENSES/python-vlc-LGPL-2.1.txt`.
The exact VLC version shipped in each release can be printed with
`LocalFileConverter --watchit-self-check`. Source code for VLC and its
contributed libraries is available from
https://www.videolan.org/vlc/download-sources.html . The Python binding is
available at https://github.com/oaubert/python-vlc . FreeConvert's own source
remains licensed under MIT; the included VLC components retain their own
licenses.

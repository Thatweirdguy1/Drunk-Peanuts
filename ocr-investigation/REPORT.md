# OCR investigation and implementation

## Evidence

| Finding | Basis |
| --- | --- |
| RapidOCR 3.9.2 wheel contains PP-OCRv6 detection and recognition ONNX files and a PP-OCRv4 orientation model. | REA archive inspection of the 27.3 MB wheel (SHA-256 `04d6b8d151f823d930bd91910555f57bea897c0c44fa6794267b94cf9c1ef9a0`); static artifact observation, not a runtime claim. |
| PaddleOCR 3.7.0 wheel contains no ONNX model files and depends on PaddleX. | REA archive inspection of the wheel (SHA-256 `c0f0a81ad4112727f30c6fcf986ac0ef6a120d31ee0991a01fae0357ee32d338`); static artifact observation. |
| RapidOCR uses PaddleOCR-derived models converted for ONNX deployment. PP-OCRv6 small supports Latin-script languages, Chinese and Japanese, while PP-OCRv5 offers separate Cyrillic, Devanagari, Korean and Arabic recognition models. | [RapidOCR overview](https://rapidai.github.io/RapidOCRDocs/latest/) and [model list](https://rapidai.github.io/RapidOCRDocs/latest/model_list/); documented facts. |
| FreeConvert recognizes sample images with accented Latin, Cyrillic, Hindi, Korean and Arabic text using local models with network connections blocked. | `test_converter.py::test_ocr_multilingual_models`; experiment result. The tests show support for these samples, not universal accuracy. |

The added PP-OCRv5 ONNX recognition files come from the versioned RapidOCR model repository. Their SHA-256 values match RapidOCR 3.9.2 `default_models.yaml`: Cyrillic `90f761b4bfcce0c8c561c0cb5c887b0971d3ec01c32164bdf7374a35b0982711`, Devanagari `d6f0a906580e3fa6b324a318718f1f31f268b6ea8ef985f91c2012a37f52c91e`, Korean `cd6e2ea50f6943ca7271eb8c56a877a5a90720b7047fe9c41a2e541a25773c9b`, Arabic `c1192e632d0baa9146ae5b756a0e635e3dc63c1733737ebfd1629e87144e9295`.

## Product decisions and limits

FreeConvert retains RapidOCR/ONNX as its local inference path. Adding PaddleOCR itself would add its PaddleX runtime without solving recognition quality automatically; the selected PaddleOCR-derived models already run through RapidOCR. Users select the text's script for OCR. No model is downloaded at runtime or uploaded to a service.

The recognizer may miss lines, misread glyphs, or lose reading order in mixed scripts, tables, handwriting, skewed pages, and poor scans. Arabic text ordering is adjusted for UTF-8 output, but punctuation and mixed Latin/Arabic lines still need review. Multilingual support means tested script families, not every language or perfect transcription.

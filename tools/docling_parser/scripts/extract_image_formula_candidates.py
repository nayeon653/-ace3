"""그림 중 Docling이 수식으로 판정한 영역만 로컬 OCR로 보강한다."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from docling_team_parser.docling_engine import DoclingEngine
from docling_team_parser.profiles import profile_for_provider
from PIL import Image, ImageOps

_OFFICE_EXTENSIONS = frozenset({".docx", ".pptx", ".xlsx"})
_OFFICE_MEDIA_RE = re.compile(r"^(?:word|ppt|xl)/media/")
_FORMULA_CHARACTER_RE = re.compile(
    r"[=+\-*/^%]|\\(?:frac|sum|sqrt|times|div|cdot)|\b(?:MIN|MAX)\s*\(",
    re.IGNORECASE,
)


def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            output.write("\n")


def _is_margin_decoration(
    bbox: dict[str, Any], page_size: dict[str, Any], *, area_limit: float = 0.02
) -> bool:
    """작고 페이지 상·하단에 붙은 로고/쪽번호 그림을 수식 검사에서 제외한다."""

    width = float(page_size["width"])
    height = float(page_size["height"])
    picture_width = max(0.0, float(bbox["r"]) - float(bbox["l"]))
    picture_height = max(0.0, float(bbox["t"]) - float(bbox["b"]))
    area_ratio = picture_width * picture_height / max(width * height, 1.0)
    center_y = (float(bbox["t"]) + float(bbox["b"])) / 2
    margin_distance = min(center_y, height - center_y) / max(height, 1.0)
    return area_ratio <= area_limit and margin_distance <= 0.12


def _visual_fingerprint(image: Image.Image) -> str:
    """렌더링 오차에 둔감한 흑백 지문으로 동일 그림 재검사를 줄인다."""

    normalized = ImageOps.autocontrast(image.convert("L")).resize((32, 32))
    pixels = list(normalized.get_flattened_data())
    median = sorted(pixels)[len(pixels) // 2]
    bits = bytes(1 if value >= median else 0 for value in pixels)
    aspect_bucket = round(image.width / max(image.height, 1), 2)
    return hashlib.sha256(repr(aspect_bucket).encode() + bits).hexdigest()


def _crop_pdf_picture(
    source: Path,
    page_no: int,
    bbox: dict[str, Any],
    *,
    scale: float = 3.0,
) -> Image.Image:
    import pypdfium2

    document = pypdfium2.PdfDocument(source)
    try:
        page = document[page_no - 1]
        rendered = page.render(scale=scale).to_pil().convert("RGB")
        page_width, page_height = page.get_size()
        left = max(0, round(float(bbox["l"]) / page_width * rendered.width))
        right = min(rendered.width, round(float(bbox["r"]) / page_width * rendered.width))
        top = max(
            0,
            round((page_height - float(bbox["t"])) / page_height * rendered.height),
        )
        bottom = min(
            rendered.height,
            round((page_height - float(bbox["b"])) / page_height * rendered.height),
        )
        if right <= left or bottom <= top:
            raise ValueError("invalid picture bounding box")
        return rendered.crop((left, top, right, bottom))
    finally:
        document.close()


def _office_images(source: Path) -> Iterable[tuple[str, Image.Image]]:
    with zipfile.ZipFile(source) as archive:
        for name in sorted(archive.namelist()):
            if not _OFFICE_MEDIA_RE.match(name):
                continue
            try:
                with Image.open(io.BytesIO(archive.read(name))) as image:
                    yield name, image.convert("RGB")
            except (OSError, ValueError):
                continue


def _formula_converter():
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter, ImageFormatOption

    profile = profile_for_provider("none")
    options = DoclingEngine(profile)._pdf_pipeline_options(
        profile.office_picture_ocr_mode,
        image_input=True,
    )
    return DocumentConverter(
        allowed_formats=[InputFormat.IMAGE],
        format_options={InputFormat.IMAGE: ImageFormatOption(pipeline_options=options)},
    )


def _docling_formula_detection(
    converter: Any, image: Image.Image, name: str
) -> tuple[int, list[str]]:
    from docling.datamodel.base_models import ConversionStatus, DocumentStream

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    conversion = converter.convert(DocumentStream(name=name, stream=buffer), raises_on_error=True)
    if conversion.status is not ConversionStatus.SUCCESS:
        return 0, []
    formula_items = [
        item
        for item in conversion.document.texts
        if str(item.label) in {"formula", "DocItemLabel.FORMULA"}
    ]
    texts = [(item.text or "").strip() for item in formula_items]
    return len(formula_items), [text for text in texts if text]


def _easyocr_reader():
    import easyocr

    return easyocr.Reader(["ko", "en"], gpu=False, download_enabled=False)


def _easyocr_text(reader: Any, image: Image.Image) -> tuple[str, list[float]]:
    import numpy as np

    results = reader.readtext(np.asarray(image), detail=1, paragraph=False)
    text = " ".join(str(item[1]).strip() for item in results if str(item[1]).strip())
    confidence = [round(float(item[2]), 6) for item in results]
    return text, confidence


def _formula_is_usable(texts: list[str]) -> bool:
    return any(_FORMULA_CHARACTER_RE.search(text) for text in texts)


def _candidate(
    *,
    formula_texts: list[str],
    ocr_text: str,
    confidences: list[float],
    image_key: str,
    occurrence: dict[str, Any],
) -> dict[str, Any]:
    formula_text = " ; ".join(formula_texts)
    evidence_text = formula_text if _formula_is_usable(formula_texts) else ocr_text
    identity = "|".join(
        (
            occurrence["source_sha256"],
            occurrence["location_ref"],
            image_key,
            evidence_text,
        )
    )
    normalized = re.sub(r"\s+", " ", evidence_text).strip()
    fingerprint = hashlib.sha256(normalized.casefold().encode()).hexdigest()
    return {
        "schema_version": 1,
        "candidate_id": hashlib.sha256(identity.encode()).hexdigest()[:20],
        "fingerprint": fingerprint,
        "kind": "image_formula",
        "source": occurrence["source"],
        "location": occurrence["location"],
        "evidence_text": evidence_text,
        "context_text": ocr_text,
        "normalized_text": normalized,
        "signals": {
            "keywords": [],
            "numeric_terms": re.findall(r"\d[\d,.]*%?", normalized),
            "operators": sorted(set(_FORMULA_CHARACTER_RE.findall(normalized))),
        },
        "image_formula_extraction": {
            "candidate_gate": "docling-CodeFormulaV2-formula-label",
            "formula_model_text": formula_text,
            "ocr_applied": True,
            "ocr_provider": "easyocr-local-ko-en",
            "ocr_text": ocr_text,
            "ocr_confidences": confidences,
            "image_fingerprint": image_key,
        },
        "requires_human_validation": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle_root", type=Path)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))["files"]
    inventory_by_filename: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in inventory:
        inventory_by_filename[item["title"]].append(item)

    occurrences_by_image: dict[str, list[dict[str, Any]]] = defaultdict(list)
    representative_images: dict[str, Image.Image] = {}
    counts: Counter[str] = Counter()
    errors: list[dict[str, str]] = []

    for manifest_path in sorted(args.bundle_root.glob("*/manifest.json")):
        bundle_dir = manifest_path.parent
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        filename = manifest["source"]["filename"]
        matches = inventory_by_filename.get(filename, [])
        if len(matches) != 1:
            counts["ambiguous_inventory"] += 1
            continue
        item = matches[0]
        source_path = args.raw_root / item["collection"] / item["parent_title"] / item["title"]
        source_payload = {
            "filename": filename,
            "sha256": manifest["source"]["sha256"],
            "drive_file_id": item["id"],
            "collection": item["collection"],
            "parent_title": item["parent_title"],
            "bundle_dir": bundle_dir.name,
            "profile_id": manifest["profile"]["id"],
            "profile_digest": manifest["profile"]["digest"],
        }
        try:
            if source_path.suffix.lower() == ".pdf":
                document = json.loads(
                    (bundle_dir / "document.docling.json").read_text(encoding="utf-8")
                )
                pages = document.get("pages", {})
                for picture in document.get("pictures", []):
                    prov = picture.get("prov") or []
                    if not prov:
                        continue
                    page_no = int(prov[0]["page_no"])
                    bbox = prov[0]["bbox"]
                    page = pages.get(str(page_no), {})
                    page_size = page.get("size")
                    counts["pdf_picture_regions"] += 1
                    if page_size and _is_margin_decoration(bbox, page_size):
                        counts["margin_decorations_skipped"] += 1
                        continue
                    image = _crop_pdf_picture(source_path, page_no, bbox)
                    location_ref = str(picture.get("self_ref") or f"page:{page_no}")
                    location = {
                        "self_ref": picture.get("self_ref"),
                        "label": "picture",
                        "page_no": page_no,
                        "bbox": bbox,
                        "section": None,
                        "table_row_index": None,
                    }
                    image_key = _visual_fingerprint(image)
                    representative_images.setdefault(image_key, image)
                    occurrences_by_image[image_key].append(
                        {
                            "source_sha256": manifest["source"]["sha256"],
                            "source": source_payload,
                            "location_ref": location_ref,
                            "location": location,
                        }
                    )
            elif source_path.suffix.lower() in _OFFICE_EXTENSIONS:
                for media_name, image in _office_images(source_path):
                    counts["office_embedded_images"] += 1
                    image_key = _visual_fingerprint(image)
                    representative_images.setdefault(image_key, image)
                    occurrences_by_image[image_key].append(
                        {
                            "source_sha256": manifest["source"]["sha256"],
                            "source": source_payload,
                            "location_ref": media_name,
                            "location": {
                                "self_ref": media_name,
                                "label": "embedded_picture",
                                "page_no": None,
                                "bbox": None,
                                "section": None,
                                "table_row_index": None,
                            },
                        }
                    )
        except Exception as exc:  # noqa: BLE001 - 한 이미지 오류로 전체 작업을 버리지 않는다.
            errors.append({"filename": filename, "error": str(exc)})

    converter = _formula_converter()
    ocr_reader = None
    candidates: list[dict[str, Any]] = []
    for index, (image_key, image) in enumerate(representative_images.items(), start=1):
        try:
            formula_labels, formula_texts = _docling_formula_detection(
                converter, image, f"picture-candidate-{index}.png"
            )
            counts["unique_images_examined"] += 1
            if not formula_labels:
                continue
            counts["docling_formula_labeled_images"] += 1
            if ocr_reader is None:
                ocr_reader = _easyocr_reader()
            ocr_text, confidences = _easyocr_text(ocr_reader, image)
            counts["images_ocrd_after_formula_gate"] += 1
            if not (_formula_is_usable(formula_texts) or _formula_is_usable([ocr_text])):
                counts["formula_labeled_without_formula_syntax"] += 1
                continue
            counts["formula_images_retained"] += 1
            for occurrence in occurrences_by_image[image_key]:
                candidates.append(
                    _candidate(
                        formula_texts=formula_texts,
                        ocr_text=ocr_text,
                        confidences=confidences,
                        image_key=image_key,
                        occurrence=occurrence,
                    )
                )
        except Exception as exc:  # noqa: BLE001 - 이미지별 오류를 manifest에 격리한다.
            errors.append({"image_fingerprint": image_key, "error": str(exc)})

    candidates.sort(
        key=lambda item: (
            item["source"]["filename"],
            item["location"].get("page_no") or 0,
            item["candidate_id"],
        )
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output_dir / "image_formula_candidates.jsonl", candidates)
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "policy": {
            "body_ocr": False,
            "candidate_gate": "Docling CodeFormulaV2 formula label",
            "retention_gate": "formula syntax in model or OCR text",
            "ocr_scope": "only images passing the candidate gate",
            "ocr_provider": "local EasyOCR ko/en",
            "external_data_transfer": False,
        },
        "counts": {**dict(counts), "candidate_occurrences": len(candidates)},
        "errors": errors,
        "candidates": "image_formula_candidates.jsonl",
    }
    (args.output_dir / "image_formula_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

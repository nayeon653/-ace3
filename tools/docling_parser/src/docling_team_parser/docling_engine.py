"""Docling 전용 변환 파이프라인과 Office 그림 OCR 단계."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import NaverOcrError, ParserError
from .io_utils import sha256_bytes
from .models import OcrProvider, ParserProfile


@dataclass(slots=True)
class EngineResult:
    document: Any
    pages: int
    pictures_found: int
    office_pictures_ocrd: int
    warnings: list[str]
    conversion_version: dict[str, Any]


class DoclingEngine:
    """불변 프로필 하나를 기준으로 Docling 파이프라인을 구성한다."""

    def __init__(self, profile: ParserProfile):
        self.profile = profile

    def convert(self, source: Path) -> EngineResult:
        from docling.datamodel.base_models import ConversionStatus, InputFormat
        from docling.document_converter import DocumentConverter, PdfFormatOption

        pdf_options = self._pdf_pipeline_options(self.profile.ocr_mode)
        converter = DocumentConverter(
            allowed_formats=[
                InputFormat.PDF,
                InputFormat.DOCX,
                InputFormat.PPTX,
                InputFormat.XLSX,
            ],
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
            },
        )

        try:
            conversion = converter.convert(source, raises_on_error=True)
        except NaverOcrError:
            raise
        except Exception as exc:
            code = (
                "NAVER_OCR_FAILED"
                if self.profile.ocr_provider is OcrProvider.NAVER
                and self._exception_is_naver_ocr(exc)
                else "PARSE_FAILED"
            )
            raise ParserError(code, self._safe_exception(exc)) from exc

        if conversion.status is not ConversionStatus.SUCCESS:
            errors = "; ".join(
                self._safe_exception(item.error_message)
                for item in conversion.errors[:5]
            )
            code = (
                "NAVER_OCR_FAILED"
                if self.profile.ocr_provider is OcrProvider.NAVER
                and self._errors_include_naver_ocr(conversion.errors)
                else "PARSE_FAILED"
            )
            raise ParserError(
                code,
                f"Docling returned {conversion.status.value}: {errors or 'no details'}",
            )

        document = conversion.document
        warnings: list[str] = []
        picture_count = len(document.pictures)
        office_picture_count = 0

        if source.suffix.lower() in {".docx", ".pptx", ".xlsx"} and picture_count:
            office_picture_count, picture_warnings = self._ocr_office_pictures(document)
            warnings.extend(picture_warnings)

        version = conversion.version.model_dump(mode="json")
        return EngineResult(
            document=document,
            pages=len(document.pages),
            pictures_found=picture_count,
            office_pictures_ocrd=office_picture_count,
            warnings=warnings,
            conversion_version=version,
        )

    def _pdf_pipeline_options(self, mode: str, *, image_input: bool = False):
        from docling.datamodel.accelerator_options import AcceleratorOptions
        from docling.datamodel.pipeline_options import (
            EasyOcrOptions,
            OcrMode,
            PdfPipelineOptions,
            TableFormerMode,
        )

        options = PdfPipelineOptions()
        options.do_ocr = True
        options.do_table_structure = self.profile.do_table_structure
        options.table_structure_options.mode = TableFormerMode(self.profile.table_mode)
        layout_model_spec = options.layout_options.model_spec.model_copy(
            update={
                "repo_id": self.profile.layout_model_repo_id,
                "revision": self.profile.layout_model_revision,
            }
        )
        options.layout_options = options.layout_options.model_copy(
            update={"model_spec": layout_model_spec}
        )
        options.images_scale = self.profile.images_scale
        options.generate_picture_images = self.profile.generate_picture_images
        options.generate_page_images = False
        options.accelerator_options = AcceleratorOptions(
            num_threads=self.profile.accelerator_threads,
            device=self.profile.accelerator_device,
        )

        ocr_mode = OcrMode(mode)
        if self.profile.ocr_provider is OcrProvider.LOCAL:
            options.ocr_options = EasyOcrOptions(
                mode=ocr_mode,
                lang=list(self.profile.languages),
                scale=(
                    self.profile.office_picture_image_scale
                    if image_input
                    else self.profile.local_image_scale or 3.0
                ),
                confidence_threshold=self.profile.local_confidence_threshold or 0.35,
                download_enabled=True,
            )
            options.allow_external_plugins = False
            options.enable_remote_services = False
        else:
            from .ocr.naver_plugin import NaverOcrOptions

            options.ocr_options = NaverOcrOptions(
                mode=ocr_mode,
                lang=list(self.profile.languages),
                scale=(
                    self.profile.office_picture_image_scale
                    if image_input
                    else self.profile.naver_image_scale or 3.0
                ),
                timeout_seconds=self.profile.naver_timeout_seconds or 60.0,
                max_attempts=self.profile.naver_max_attempts or 3,
                enable_table_detection=bool(self.profile.naver_enable_table_detection),
                max_image_edge=self.profile.naver_max_image_edge or 7_900,
                max_image_bytes=self.profile.naver_max_image_bytes or 49_000_000,
            )
            options.allow_external_plugins = True
            options.enable_remote_services = True
            options.ocr_batch_size = 1

        return options

    def _ocr_office_pictures(self, document: Any) -> tuple[int, list[str]]:
        from docling.datamodel.base_models import (
            ConversionStatus,
            DocumentStream,
            InputFormat,
        )
        from docling.document_converter import DocumentConverter, ImageFormatOption
        from docling_core.types.doc import PictureItem

        image_options = self._pdf_pipeline_options(
            self.profile.office_picture_ocr_mode,
            image_input=True,
        )
        image_converter = DocumentConverter(
            allowed_formats=[InputFormat.IMAGE],
            format_options={
                InputFormat.IMAGE: ImageFormatOption(pipeline_options=image_options),
            },
        )

        warnings: list[str] = []
        parsed_by_hash: dict[str, Any] = {}
        inserted_count = 0

        for index, picture in enumerate(list(document.pictures), start=1):
            if not isinstance(picture, PictureItem):
                continue
            image = picture.get_image(document)
            if image is None:
                warnings.append(
                    f"picture {index} has no Docling image payload and could not be OCRed"
                )
                continue

            image_bytes = self._serialize_picture_png(image)
            image_hash = sha256_bytes(image_bytes)
            image_document = parsed_by_hash.get(image_hash)

            if image_document is None:
                stream = DocumentStream(
                    name=f"office-picture-{index}.png",
                    stream=io.BytesIO(image_bytes),
                )
                try:
                    conversion = image_converter.convert(stream, raises_on_error=True)
                except NaverOcrError:
                    raise
                except Exception as exc:
                    code = (
                        "NAVER_OCR_FAILED"
                        if self.profile.ocr_provider is OcrProvider.NAVER
                        and self._exception_is_naver_ocr(exc)
                        else "OFFICE_PICTURE_OCR_FAILED"
                    )
                    raise ParserError(
                        code,
                        f"picture {index}: {self._safe_exception(exc)}",
                    ) from exc

                if conversion.status is not ConversionStatus.SUCCESS:
                    code = (
                        "NAVER_OCR_FAILED"
                        if self.profile.ocr_provider is OcrProvider.NAVER
                        and self._errors_include_naver_ocr(conversion.errors)
                        else "OFFICE_PICTURE_OCR_FAILED"
                    )
                    raise ParserError(
                        code,
                        f"picture {index}: Docling returned {conversion.status.value}",
                    )
                image_document = conversion.document
                self._remove_image_page_provenance(image_document)
                parsed_by_hash[image_hash] = image_document

            roots = self._ocr_content_roots(image_document)
            if not roots:
                continue
            document.insert_node_items(
                sibling=picture,
                node_items=roots,
                doc=image_document,
                after=True,
            )
            inserted_count += 1

        return inserted_count, warnings

    @staticmethod
    def _ocr_content_roots(image_document: Any) -> list[Any]:
        from docling_core.types.doc import PictureItem

        roots: list[Any] = []
        for ref in image_document.body.children:
            item = ref.resolve(image_document)
            if isinstance(item, PictureItem):
                roots.extend(child.resolve(image_document) for child in item.children)
            else:
                roots.append(item)
        return roots

    @staticmethod
    def _serialize_picture_png(image: Any) -> bytes:
        """투명한 Office 이미지를 OCR 전에 흰색 배경으로 합성한다."""

        from PIL import Image

        has_alpha = "A" in image.getbands() or (
            image.mode == "P" and "transparency" in image.info
        )
        if has_alpha:
            rgba_image = image.convert("RGBA")
            rgb_image = Image.new("RGB", rgba_image.size, "white")
            try:
                alpha = rgba_image.getchannel("A")
                try:
                    rgb_image.paste(rgba_image, mask=alpha)
                finally:
                    alpha.close()
            finally:
                rgba_image.close()
        else:
            rgb_image = image.convert("RGB")

        try:
            with io.BytesIO() as buffer:
                rgb_image.save(buffer, format="PNG")
                return buffer.getvalue()
        finally:
            rgb_image.close()

    @staticmethod
    def _remove_image_page_provenance(image_document: Any) -> None:
        for item, _level in image_document.iterate_items(
            with_groups=True,
            traverse_pictures=True,
        ):
            if hasattr(item, "prov"):
                item.prov = []
            if hasattr(item, "source"):
                item.source = []
        image_document.pages = {}

    @staticmethod
    def _safe_exception(value: object) -> str:
        text = str(value) or value.__class__.__name__
        # 사용자에게 표시하는 오류에 원격 응답 본문이나 인증정보를 포함하지 않는다.
        if len(text) > 500:
            text = text[:500] + "…"
        return text.replace("\n", " ")

    @staticmethod
    def _exception_is_naver_ocr(exc: BaseException) -> bool:
        """Docling이 감싼 예외에서 NAVER 실패를 식별한다."""

        current: BaseException | None = exc
        seen: set[int] = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            if (
                isinstance(current, NaverOcrError)
                or "naverocr" in type(current).__name__.replace("_", "").lower()
            ):
                return True
            message = str(current).strip()
            if (
                message.startswith("NAVER OCR")
                or "Errors: NAVER OCR" in message
                or "; NAVER OCR" in message
            ):
                return True
            current = current.__cause__ or current.__context__
        return False

    @staticmethod
    def _errors_include_naver_ocr(errors: list[Any]) -> bool:
        for item in errors:
            module_name = str(getattr(item, "module_name", ""))
            message = str(getattr(item, "error_message", "")).strip()
            if "naverocr" in module_name.replace("_", "").lower() or message.startswith(
                "NAVER OCR"
            ):
                return True
        return False

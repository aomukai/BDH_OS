#!/usr/bin/env python3
"""Render a compiled or draft Ninereeds lesson as an operator-review PDF."""

from __future__ import annotations

import argparse
import hashlib
import json
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, KeepTogether, PageBreak, PageTemplate, Paragraph,
    Spacer, Table, TableStyle,
)
from PIL import Image as PillowImage


REPO_ROOT = Path(__file__).resolve().parents[4]
PHASE_LABELS = {
    "presentation": "Presentation",
    "presentation_affirmative": "Affirmative presentation",
    "presentation_negative": "Negative presentation",
    "presentation_W_question": "W-question presentation",
    "presentation_OR_question": "OR-question presentation",
    "presentation_reciprocity": "Reciprocity presentation",
    "affirmative": "Affirmative practice",
    "negative": "Negative practice",
    "W_question": "W-question practice",
    "OR_question": "OR-question practice",
    "reciprocity": "Reciprocity practice",
    "mixed_practice": "Mixed practice",
    "transfer": "Transfer",
    "closing_recap": "Closing recap",
    "picture_book": "Picture-book comprehension",
    "story_interface": "Story-interface teaching",
    "unseen_transfer": "Unseen transfer",
}
TOOL_LABELS = [
    "SHOW_ASSET", "SHOW_CROP", "SHOW_HIGHLIGHT", "REPLAY_PRESENTATION",
    "USE_MARKERS", "ASK_BOUNDED_CLARIFICATION", "CHECK_UNDERSTANDING",
    "PRESENT_AGAIN", "TRAIN_MORE", "TRAIN_LONGER", "REPLAY_LESSON",
    "FINISH", "ALARM",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_lesson(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("lesson must be one JSON object")
    for key in ("lesson_id", "topic", "point", "phases", "assets"):
        if key not in value:
            raise ValueError(f"lesson is missing {key}")
    return value


def text(value: object) -> str:
    if value is None:
        return "-"
    return escape(str(value)).replace("\n", "<br/>")


def register_fonts() -> tuple[str, str]:
    regular = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    bold = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    if regular.is_file() and bold.is_file():
        pdfmetrics.registerFont(TTFont("LessonSans", str(regular)))
        pdfmetrics.registerFont(TTFont("LessonSansBold", str(bold)))
        return "LessonSans", "LessonSansBold"
    return "Helvetica", "Helvetica-Bold"


def styles_for(font: str, bold: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("LessonTitle", parent=base["Title"], fontName=bold, fontSize=24, leading=29, textColor=colors.HexColor("#17324D"), spaceAfter=8 * mm),
        "subtitle": ParagraphStyle("LessonSubtitle", parent=base["Normal"], fontName=font, fontSize=11, leading=16, textColor=colors.HexColor("#4A6075"), alignment=TA_CENTER),
        "h1": ParagraphStyle("LessonH1", parent=base["Heading1"], fontName=bold, fontSize=17, leading=21, textColor=colors.HexColor("#17324D"), spaceBefore=5 * mm, spaceAfter=3 * mm),
        "h2": ParagraphStyle("LessonH2", parent=base["Heading2"], fontName=bold, fontSize=12, leading=15, textColor=colors.HexColor("#24536F"), spaceBefore=3 * mm, spaceAfter=2 * mm),
        "body": ParagraphStyle("LessonBody", parent=base["BodyText"], fontName=font, fontSize=9.4, leading=13, textColor=colors.HexColor("#1D2935"), alignment=TA_LEFT),
        "small": ParagraphStyle("LessonSmall", parent=base["BodyText"], fontName=font, fontSize=7.8, leading=10.5, textColor=colors.HexColor("#4A6075")),
        "label": ParagraphStyle("LessonLabel", parent=base["BodyText"], fontName=bold, fontSize=8.3, leading=11, textColor=colors.HexColor("#17324D")),
        "quote": ParagraphStyle("LessonQuote", parent=base["BodyText"], fontName=font, fontSize=10.5, leading=15, textColor=colors.HexColor("#102A43"), leftIndent=4 * mm, rightIndent=4 * mm),
        "warning": ParagraphStyle("LessonWarning", parent=base["BodyText"], fontName=bold, fontSize=9, leading=13, textColor=colors.HexColor("#8C2F1F")),
    }


def paragraph(value: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text(value), style)


def resolve_asset(raw: object, lesson_path: Path) -> Path | None:
    if not isinstance(raw, str) or not raw:
        return None
    candidate = Path(raw)
    choices = [candidate] if candidate.is_absolute() else [lesson_path.parent / candidate, REPO_ROOT / candidate]
    for path in choices:
        if path.is_file():
            return path.resolve()
    return None


def phase_pools(lesson: dict) -> list[tuple[str, list[dict]]]:
    phases = lesson.get("phases", {})
    controlled = phases.get("controlled_practice", {})
    presentations = {
        item.get("id"): item for item in phases.get("presentation", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    bindings = phases.get("presentation_bindings")
    result = []
    if isinstance(bindings, dict):
        for key in ("affirmative", "negative", "W_question", "OR_question", "reciprocity"):
            if key not in controlled:
                continue
            local = [presentations[item] for item in bindings.get(key, []) if item in presentations]
            result.append((f"presentation_{key}", local))
            result.append((key, controlled.get(key, [])))
    else:
        result = [("presentation", phases.get("presentation", []))]
        result.extend((key, controlled.get(key, [])) for key in ("affirmative", "negative", "W_question", "OR_question", "reciprocity"))
    result.append(("mixed_practice", phases.get("mixed_practice", [])))
    return [(name, [item for item in pool if isinstance(item, dict)]) for name, pool in result if isinstance(pool, list)]


def picture_book_exercise_pools(picture_book: dict) -> list[tuple[str, list[dict]]]:
    pools = {"story_interface": [], "picture_book": [], "unseen_transfer": []}
    for exercise in picture_book.get("comprehension", []):
        if not isinstance(exercise, dict):
            continue
        identifier = str(exercise.get("id", ""))
        if "story-interface" in identifier:
            pools["story_interface"].append(exercise)
        elif "-transfer-" in identifier:
            pools["unseen_transfer"].append(exercise)
        else:
            pools["picture_book"].append(exercise)
    return [(name, pool) for name, pool in pools.items() if pool]


def exercise_card(exercise: dict, styles: dict[str, ParagraphStyle]) -> Table:
    answers = exercise.get("expected_answers", [])
    invariants = exercise.get("invariants", [])
    assets = exercise.get("asset_ids", [])
    teacher_turns = exercise.get("teacher_turns", [])
    if teacher_turns:
        teacher_display = "\n".join(
            f"{turn.get('speaker', '-')}: {turn.get('text', '-')}"
            for turn in teacher_turns if isinstance(turn, dict)
        )
    else:
        speaker = exercise.get("teacher_speaker")
        teacher_display = f"{speaker}: {exercise.get('teacher_text', '-')}" if speaker else exercise.get("teacher_text", "-")
    rows = [
        [paragraph(f"Exercise {exercise.get('id', '-')}", styles["label"])],
        [paragraph(teacher_display, styles["quote"])],
        [Table([
            [paragraph("Expected", styles["label"]), paragraph("; ".join(map(str, answers)) or "-", styles["small"])],
            [paragraph("Must remain true", styles["label"]), paragraph("; ".join(map(str, invariants)) or "-", styles["small"])],
            [paragraph("Visuals", styles["label"]), paragraph(", ".join(map(str, assets)) or "None", styles["small"])],
            [paragraph("Target production", styles["label"]), paragraph("Required" if exercise.get("target_language_required") else "Not required", styles["small"])],
        ], colWidths=[35 * mm, 125 * mm], style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#D8E2EA")),
            ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 1.3 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.3 * mm),
        ]))],
    ]
    control = exercise.get("nonverbal_control")
    if isinstance(control, dict):
        demonstrations = "; ".join(
            f"{item.get('turn_id', '-')}: {item.get('replay_text', '-')} → {item.get('correct_option_asset_id', '-')}"
            for item in control.get("demonstrations", []) if isinstance(item, dict)
        ) or "None"
        options = "; ".join(
            f"{item.get('id', '-')}: {item.get('display_value', item.get('visual_entity', '-'))} ({item.get('asset_id', '-')})"
            for item in control.get("options", []) if isinstance(item, dict)
        ) or "None"
        worked_items = "; ".join(
            f"{item.get('label', '-')}: mismatch {item.get('displayed_mismatch_label', '-')}"
            for item in control.get("worked_items", []) if isinstance(item, dict)
        ) or "None"
        control_rows = [
            [paragraph("Machine action", styles["label"]), paragraph(control.get("machine_action", "-"), styles["small"])],
            [paragraph("Semantic task", styles["label"]), paragraph(control.get("semantic_task", "-"), styles["small"])],
            [paragraph("Displayed mismatch", styles["label"]), paragraph(control.get("displayed_mismatch_label", "-"), styles["small"])],
            [paragraph("Story anchor", styles["label"]), paragraph(control.get("anchor_asset_id", "-"), styles["small"])],
            [paragraph("Worked items", styles["label"]), paragraph(worked_items, styles["small"])],
            [paragraph("Worked demos", styles["label"]), paragraph(demonstrations, styles["small"])],
            [paragraph("Visual options", styles["label"]), paragraph(options, styles["small"])],
        ]
        rows.append([Table(control_rows, colWidths=[35 * mm, 125 * mm], style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#D8E2EA")),
            ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 1.3 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.3 * mm),
        ]))])
    return Table(rows, colWidths=[170 * mm], repeatRows=1, style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF3F8")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#A8C1D1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
    ]))


def image_flowable(path: Path, max_width: float, max_height: float) -> Image:
    # A canonical master can be many megabytes. The PDF is a review projection,
    # so embed a print-resolution derivative rather than duplicating master bytes.
    with PillowImage.open(path) as source:
        rendered = source.convert("RGB")
        rendered.thumbnail((1800, 1800), PillowImage.Resampling.LANCZOS)
        payload = BytesIO()
        rendered.save(payload, format="JPEG", quality=88, optimize=True)
    payload.seek(0)
    image = Image(payload)
    image._ninereeds_payload = payload
    scale = min(max_width / image.imageWidth, max_height / image.imageHeight)
    image.drawWidth = image.imageWidth * scale
    image.drawHeight = image.imageHeight * scale
    return image


def exercise_visual_block(
    exercise: dict,
    assets: dict[str, dict],
    operations: dict[str, dict],
    lesson_path: Path,
    styles: dict[str, ParagraphStyle],
) -> list:
    asset_ids = exercise.get("asset_ids", [])
    if not asset_ids:
        return [
            paragraph("What Luna shows", styles["h2"]),
            paragraph("No visual is licensed for this exchange.", styles["small"]),
        ]
    result = []
    if len(asset_ids) > 1:
        result.append(paragraph("What Luna shows - bounded visual choices", styles["h2"]))
        cells = []
        for asset_id in asset_ids:
            asset = assets.get(asset_id)
            if asset is None:
                cells.append(Table(
                    [[paragraph(f"BLOCKED: undeclared asset {asset_id}", styles["warning"]) ]],
                    colWidths=[78 * mm], rowHeights=[55 * mm],
                    style=TableStyle([
                        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#C46A55")),
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF3EF")),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ]),
                ))
                continue
            operation = operations.get(asset_id, {})
            path = resolve_asset(asset.get("path"), lesson_path)
            visual = (
                image_flowable(path, 74 * mm, 45 * mm)
                if path is not None
                else paragraph(f"BLOCKER: image bytes for {asset_id} are unavailable.", styles["warning"])
            )
            crop = operation.get("crop_xywh") or asset.get("crop_xywh")
            source = f"Asset {asset_id}"
            if crop:
                source += f"; crop {crop}"
            cells.append([
                visual,
                Spacer(1, 1.5 * mm),
                paragraph(asset.get("purpose", "-"), styles["small"]),
                paragraph(source, styles["small"]),
            ])
        for start in range(0, len(cells), 2):
            row = cells[start:start + 2]
            if len(row) == 1:
                row.append("")
            result.append(Table([row], colWidths=[82.5 * mm, 82.5 * mm], style=TableStyle([
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#C8D6E0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
            ])))
            result.append(Spacer(1, 3 * mm))
        return result

    for asset_id in asset_ids:
        asset = assets.get(asset_id)
        if asset is None:
            result.extend([
                paragraph("What Luna shows - BLOCKED", styles["h2"]),
                paragraph(f"Exercise references undeclared asset {asset_id}.", styles["warning"]),
            ])
            continue
        operation = operations.get(asset_id, {})
        operation_type = str(operation.get("type", "unrecorded")).replace("_", " ").upper()
        result.append(paragraph(f"What Luna shows - {operation_type}", styles["h2"]))
        path = resolve_asset(asset.get("path"), lesson_path)
        if path is None:
            result.append(Table(
                [[paragraph(f"BLOCKER: image bytes for {asset_id} are unavailable.", styles["warning"]) ]],
                colWidths=[165 * mm], rowHeights=[38 * mm],
                style=TableStyle([
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#C46A55")),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF3EF")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ]),
            ))
        else:
            result.append(image_flowable(path, 165 * mm, 92 * mm))
        claim = "; ".join(map(str, operation.get("teaching_claims", []))) or "No teaching claim recorded."
        crop = operation.get("crop_xywh") or asset.get("crop_xywh")
        provenance = f"Asset {asset_id}"
        if crop:
            provenance += f"; crop [x={crop[0]}, y={crop[1]}, width={crop[2]}, height={crop[3]}]"
        result.extend([
            Spacer(1, 2 * mm),
            Table([
                [paragraph("Caption", styles["label"]), paragraph(asset.get("purpose", "-"), styles["small"])],
                [paragraph("Proof", styles["label"]), paragraph(claim, styles["small"])],
                [paragraph("Source", styles["label"]), paragraph(provenance, styles["small"])],
            ], colWidths=[28 * mm, 137 * mm], style=TableStyle([
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF3F8")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#C8D6E0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 1.2 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2 * mm),
            ])),
            Spacer(1, 3 * mm),
        ])
    return result


def render(lesson_path: Path, output: Path, *, force: bool = False) -> None:
    lesson = load_lesson(lesson_path)
    if output.exists() and not force:
        raise ValueError(f"refusing to overwrite {output}; pass --force to replace it")
    output.parent.mkdir(parents=True, exist_ok=True)
    font, bold = register_fonts()
    styles = styles_for(font, bold)

    doc = BaseDocTemplate(
        str(output), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=19 * mm, bottomMargin=18 * mm,
        title=str(lesson.get("lesson_id")), author="Ninereeds lesson compiler",
        invariant=1,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="lesson-frame")

    def decorate(canvas, document):
        canvas.saveState()
        canvas.setFont(font, 7.5)
        canvas.setFillColor(colors.HexColor("#60778B"))
        canvas.drawString(20 * mm, 10 * mm, str(lesson.get("lesson_id")))
        canvas.drawRightString(A4[0] - 20 * mm, 10 * mm, f"Page {document.page}")
        canvas.setStrokeColor(colors.HexColor("#D6E1E8"))
        canvas.line(20 * mm, 14 * mm, A4[0] - 20 * mm, 14 * mm)
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="lesson", frames=[frame], onPage=decorate)])
    story = []

    status = lesson.get("status", "draft")
    story.extend([
        Spacer(1, 20 * mm),
        paragraph(f"{lesson.get('assembly', {}).get('conducted_entry_id', 'Lesson')} - {lesson.get('topic', '-')}", styles["title"]),
        paragraph(lesson.get("lesson_id"), styles["subtitle"]),
        Spacer(1, 9 * mm),
    ])
    point = lesson.get("point", {})
    overview = [
        [paragraph("Status", styles["label"]), paragraph(status, styles["body"])],
        [paragraph("Variant", styles["label"]), paragraph(lesson.get("variant", "-"), styles["body"])],
        [paragraph("Target language", styles["label"]), paragraph(lesson.get("target_language", "-"), styles["body"])],
        [paragraph("Principal Point", styles["label"]), paragraph(f"{point.get('id', '-')}: {point.get('claim', '-')}", styles["body"])],
        [paragraph("Lesson SHA-256", styles["label"]), paragraph(sha256(lesson_path), styles["small"])],
    ]
    story.append(Table(overview, colWidths=[40 * mm, 125 * mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF3F8")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#A8C1D1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D6E1E8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
    ])))
    if status != "frozen":
        story.extend([Spacer(1, 5 * mm), paragraph("DRAFT - This proof is for inspection and cannot authorize teaching or training.", styles["warning"])])
    story.append(PageBreak())

    story.append(paragraph("Lesson map", styles["h1"]))
    phase_rows = [[paragraph("Phase", styles["label"]), paragraph("Exercises", styles["label"])]]
    for phase, pool in phase_pools(lesson):
        phase_rows.append([paragraph(PHASE_LABELS[phase], styles["body"]), paragraph(str(len(pool)), styles["body"])])
    book_for_map = lesson.get("picture_book", {})
    book_pools = picture_book_exercise_pools(book_for_map) if isinstance(book_for_map, dict) else []
    transfer_for_map = lesson.get("phases", {}).get("transfer", [])
    for phase, pool in book_pools:
        phase_rows.append([paragraph(PHASE_LABELS[phase], styles["body"]), paragraph(str(len(pool)), styles["body"])])
    recap_label = "closing_recap" if lesson.get("point", {}).get("novelty_kind") == "lexical_set" else "transfer"
    phase_rows.append([paragraph(PHASE_LABELS[recap_label], styles["body"]), paragraph(str(len(transfer_for_map) if isinstance(transfer_for_map, list) else 0), styles["body"])])
    story.append(Table(phase_rows, colWidths=[125 * mm, 40 * mm], repeatRows=1, style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17324D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C8D6E0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
    ])))
    selection = lesson.get("selection", {})
    story.extend([
        paragraph("Why this lesson is next", styles["h2"]),
        paragraph(selection.get("rationale", "No rationale recorded."), styles["body"]),
        paragraph("Predicted dosage", styles["h2"]),
        paragraph(selection.get("predicted_dosage", "No dosage recorded."), styles["body"]),
        paragraph("Prerequisites", styles["h2"]),
        paragraph("; ".join(item.get("id", "-") for item in lesson.get("prerequisites", []) if isinstance(item, dict)) or "None", styles["body"]),
    ])

    assets = [item for item in lesson.get("assets", []) if isinstance(item, dict)]
    assets_by_id = {item.get("id"): item for item in assets if isinstance(item.get("id"), str)}
    operations = {
        item.get("output_asset_id"): item
        for item in lesson.get("visual_plan", {}).get("operations", [])
        if isinstance(item, dict)
    }

    picture_book_story = []
    picture_book = lesson.get("picture_book")
    if isinstance(picture_book, dict):
        pages = [item for item in picture_book.get("pages", []) if isinstance(item, dict)]
        if pages:
            picture_book_story.extend([
                PageBreak(),
                paragraph("Picture book", styles["h1"]),
                paragraph(picture_book.get("instructional_kernel", "-"), styles["body"]),
            ])
            for page in pages:
                picture_book_story.extend([
                    PageBreak(),
                    paragraph(f"Picture book - {page.get('id', '-')}", styles["h1"]),
                ])
                asset_id = page.get("asset_id")
                asset = assets_by_id.get(asset_id)
                if asset is None:
                    picture_book_story.append(paragraph(f"BLOCKER: undeclared picture-book asset {asset_id}.", styles["warning"]))
                else:
                    path = resolve_asset(asset.get("path"), lesson_path)
                    if path is None:
                        picture_book_story.append(paragraph(f"BLOCKER: image bytes for {asset_id} are unavailable.", styles["warning"]))
                    else:
                        picture_book_story.append(image_flowable(path, 165 * mm, 132 * mm))
                        picture_book_story.append(Spacer(1, 4 * mm))
                dialogue = "\n".join(
                    f"{turn.get('speaker', '-')}: {turn.get('text', '-')}"
                    for turn in page.get("dialogue_turns", []) if isinstance(turn, dict)
                ) or "-"
                picture_book_story.append(Table([
                    [paragraph("Caption", styles["label"]), paragraph(page.get("caption", "-"), styles["quote"])],
                    [paragraph("Dialogue", styles["label"]), paragraph(dialogue, styles["quote"])],
                    [paragraph("Scene facts", styles["label"]), paragraph("; ".join(map(str, page.get("scene_facts", []))) or "-", styles["small"])],
                    [paragraph("Exact visual", styles["label"]), paragraph(asset_id or "-", styles["small"])],
                ], colWidths=[32 * mm, 133 * mm], style=TableStyle([
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF3F8")),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#C8D6E0")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2.5 * mm),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2.5 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
                ])))

    for phase, pool in phase_pools(lesson):
        if not pool:
            story.extend([
                PageBreak(),
                paragraph(PHASE_LABELS[phase], styles["h1"]),
                paragraph("No exercises in this optional phase.", styles["small"]),
            ])
            continue
        for exercise in pool:
            story.extend([
                PageBreak(),
                paragraph(f"{PHASE_LABELS[phase]} - {exercise.get('id', '-')}", styles["h1"]),
            ])
            story.extend(exercise_visual_block(exercise, assets_by_id, operations, lesson_path, styles))
            story.append(exercise_card(exercise, styles))

    story.extend(picture_book_story)
    closing_pools = []
    if isinstance(picture_book, dict):
        closing_pools.extend(picture_book_exercise_pools(picture_book))
    closing_phase = "closing_recap" if lesson.get("point", {}).get("novelty_kind") == "lexical_set" else "transfer"
    closing_pools.append((closing_phase, lesson.get("phases", {}).get("transfer", [])))
    for phase, raw_pool in closing_pools:
        pool = [item for item in raw_pool if isinstance(item, dict)] if isinstance(raw_pool, list) else []
        for exercise in pool:
            story.extend([
                PageBreak(),
                paragraph(f"{PHASE_LABELS[phase]} - {exercise.get('id', '-')}", styles["h1"]),
            ])
            story.extend(exercise_visual_block(exercise, assets_by_id, operations, lesson_path, styles))
            story.append(exercise_card(exercise, styles))

    if assets:
        story.append(PageBreak())
        story.append(paragraph("Visual proof", styles["h1"]))
    for index, asset in enumerate(assets):
        if index:
            story.append(PageBreak())
        asset_id = asset.get("id", "-")
        operation = operations.get(asset_id, {})
        story.append(paragraph(f"Asset {asset_id}", styles["h2"]))
        path = resolve_asset(asset.get("path"), lesson_path)
        if path is not None:
            story.append(image_flowable(path, 165 * mm, 125 * mm))
            story.append(Spacer(1, 3 * mm))
        else:
            story.append(Table([[paragraph("IMAGE NOT AVAILABLE IN THIS REVIEW ENVIRONMENT", styles["warning"]) ]], colWidths=[165 * mm], rowHeights=[45 * mm], style=TableStyle([
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#C46A55")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF3EF")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ])))
            story.append(Spacer(1, 3 * mm))
        details = [
            [paragraph("Purpose", styles["label"]), paragraph(asset.get("purpose", "-"), styles["body"])],
            [paragraph("Source / operation", styles["label"]), paragraph(f"{asset.get('source', '-')} / {operation.get('type', 'not recorded')}", styles["body"])],
            [paragraph("Teaching claims", styles["label"]), paragraph("; ".join(operation.get("teaching_claims", [])) or "Not recorded", styles["body"])],
            [paragraph("Crop", styles["label"]), paragraph(operation.get("crop_xywh") or asset.get("crop_xywh") or "Not a literal crop", styles["body"])],
            [paragraph("Parent", styles["label"]), paragraph(operation.get("parent_asset_id") or asset.get("parent_asset_id") or "None", styles["body"])],
            [paragraph("Pixel review", styles["label"]), paragraph(operation.get("verification", {}).get("decision", asset.get("status", "-")), styles["body"])],
        ]
        story.append(Table(details, colWidths=[42 * mm, 123 * mm], style=TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF3F8")),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#C8D6E0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2.5 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2.5 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ])))

    story.append(PageBreak())
    story.append(paragraph("Teaching controls and stop conditions", styles["h1"]))
    story.append(paragraph("Luna may choose only from this protocol-level tool set during rehearsal. A tool remains unusable unless the lesson and rehearsal specification license it for the current exercise.", styles["body"]))
    story.append(Spacer(1, 3 * mm))
    adaptive = lesson.get("adaptive", {})
    runtime_contract = adaptive.get("runtime_contract", {})
    base_accounting = runtime_contract.get("base_accounting", {})
    budgets = runtime_contract.get("budgets", {})
    enabled_tool_labels = list(TOOL_LABELS)
    if adaptive.get("marker_intervention", {}).get("enabled") is False:
        enabled_tool_labels.remove("USE_MARKERS")
    tool_rows = [[paragraph(name, styles["label"]), paragraph({
        "SHOW_ASSET": "Show a prepared lesson asset.",
        "SHOW_CROP": "Show a precomputed literal crop; never generate one live.",
        "SHOW_HIGHLIGHT": "Show a prepared context-preserving highlight.",
        "REPLAY_PRESENTATION": "Replay the frozen presentation within budget.",
        "USE_MARKERS": "Use the frozen bounded marker protocol, then retest unmarked.",
        "ASK_BOUNDED_CLARIFICATION": "Ask one licensed clarification question.",
        "CHECK_UNDERSTANDING": "Check whether teacher wording and focus were understood.",
        "PRESENT_AGAIN": "Replay only the licensed frozen presentation item, within its use budget, then cold-retest the gate.",
        "TRAIN_MORE": "Add one bounded Point-safe example using frozen reviewed assets and log the decision basis.",
        "TRAIN_LONGER": "Run a bounded varied ordering of frozen mixed-practice items and log the stop count.",
        "REPLAY_LESSON": "Replay the frozen lesson at most as licensed; never create new material live.",
        "FINISH": "Close the lesson and write the report; issue no further learner prompts.",
        "ALARM": "Freeze immediately when the lesson, visual, language, or protocol is unsafe or inadequate.",
    }[name], styles["small"])] for name in enabled_tool_labels]
    story.append(Table(tool_rows, colWidths=[52 * mm, 113 * mm], style=TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#C8D6E0")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF3F8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2.5 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2.5 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
    ])))
    mixed_execution = adaptive.get("mixed_execution", {})
    present_again = adaptive.get("present_again", {})
    train_more = adaptive.get("train_more", {})
    train_longer = adaptive.get("train_longer", {})
    replay = adaptive.get("replay_lesson", {})
    finish = adaptive.get("finish", {})
    gate_rules = train_more.get("gate_execution", {})
    sample_gate_rule = next((rule for rule in gate_rules.values() if isinstance(rule, dict)), {})
    present_dispatch = "; ".join(
        f"{gate} -> {mapping.get('presentation_id', '-')} -> {mapping.get('cold_retest_exercise_id', '-')}"
        for gate, mapping in present_again.get("dispatch_table", {}).items()
        if isinstance(mapping, dict)
    )
    story.extend([
        paragraph("Frozen stopping rules", styles["h2"]),
        paragraph(f"Base-path emissions: {base_accounting.get('total', '-')}; global teacher/student/tool cap: {budgets.get('teacher_cap', adaptive.get('maximum_teacher_turns', '-'))}; mixed-practice cap: {adaptive.get('mixed_practice_cap', '-')}; controlled threshold: {sample_gate_rule.get('base_pass_minimum_correct', '-')}/{sample_gate_rule.get('base_denominator', '-')}; mixed threshold: {mixed_execution.get('minimum_successes', '-')}/{mixed_execution.get('denominator', '-')}; terminal remediation outcome: {adaptive.get('marker_intervention', {}).get('terminal_outcome', '-')}", styles["body"]),
        paragraph(
            "Base accounting: "
            + "; ".join(f"{name.replace('_', ' ')} {count}" for name, count in base_accounting.items() if name != "total")
            + f"; total {base_accounting.get('total', '-')}. Counter rule: {budgets.get('convention', '-')}",
            styles["small"],
        ),
        paragraph("Executable adaptation ledger", styles["h2"]),
        Table([
            [paragraph("PRESENT_AGAIN", styles["label"]), paragraph(f"IDs: {', '.join(present_again.get('presentation_ids', [])) or '-'}; maximum uses: {present_again.get('maximum_total_uses', '-')}; dispatch: {present_dispatch or '-'}; return: {present_again.get('return_rule', '-')}", styles["small"])],
            [paragraph("MIXED", styles["label"]), paragraph(f"Order: {', '.join(mixed_execution.get('ordered_item_ids', [])) or '-'}; denominator: {mixed_execution.get('denominator', '-')}; minimum successes: {mixed_execution.get('minimum_successes', '-')}; maximum: {mixed_execution.get('maximum_items', '-')}", styles["small"])],
            [paragraph("TRAIN_MORE", styles["label"]), paragraph(f"Reserve IDs: {', '.join(train_more.get('reserve_ids', [])) or '-'}; release: {train_more.get('release_rule', '-')}", styles["small"])],
            [paragraph("TRAIN_LONGER", styles["label"]), paragraph(f"Source: {train_longer.get('source', '-')}; order: {', '.join(train_longer.get('ordered_item_ids', [])) or '-'}; maximum additional: {train_longer.get('max_additional_items', '-')}; stop: {train_longer.get('stop_rule', '-')}", styles["small"])],
            [paragraph("REPLAY_LESSON", styles["label"]), paragraph(f"Maximum replays: {replay.get('maximum_replays', '-')}; scope: {replay.get('replay_scope', '-')}; predicate: {replay.get('release_predicate', '-')}; release: {replay.get('release_rule', '-')}; stop: {replay.get('stop_rule', '-')}", styles["small"])],
            [paragraph("FINISH", styles["label"]), paragraph(f"Eligibility: {finish.get('eligibility', '-')}; behavior: {finish.get('behavior', '-')}", styles["small"])],
            [paragraph("OVERALL MASTERY", styles["label"]), paragraph(finish.get("eligibility", "-"), styles["small"])],
            [paragraph("BUDGET EXHAUSTION", styles["label"]), paragraph(f"PRESENT_AGAIN: {present_again.get('exhaustion', '-')}; TRAIN_MORE: {train_more.get('exhaustion', '-')}; TRAIN_LONGER: {train_longer.get('exhaustion', '-')}; REPLAY_LESSON: {replay.get('exhaustion', '-')}; ALARM: {adaptive.get('alarm', {}).get('behavior', '-')}", styles["small"])],
        ], colWidths=[38 * mm, 127 * mm], style=TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#C8D6E0")),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF3F8")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2.5 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2.5 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ])),
        paragraph("Phase terminal rules", styles["h2"]),
        Table(([
            [paragraph(transition, styles["label"]), paragraph(destination, styles["small"])]
            for transition, destination in adaptive.get("controller_transition_table", {}).items()
        ] or [[paragraph("Lesson-level rule", styles["label"]), paragraph(finish.get('eligibility', '-'), styles["small"])]]), colWidths=[62 * mm, 103 * mm], style=TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#C8D6E0")),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF3F8")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2.5 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2.5 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ])),
        KeepTogether([
            paragraph("Alarm rule", styles["h2"]),
            paragraph("If Luna cannot preserve the Point, understandability, scene truth, tool contract, or stopping budget, Luna presses ALARM. The rehearsal log freezes; repair happens in a new linked attempt.", styles["warning"]),
        ]),
    ])

    story.append(Spacer(1, 8 * mm))
    story.append(paragraph("Audit and review", styles["h1"]))
    assembly = lesson.get("assembly", {})
    authoring = lesson.get("authoring", {})
    review = lesson.get("independent_review", {})
    audit_rows = [
        ["Conducted entry", assembly.get("conducted_entry_id", "-")],
        ["Conducted position", assembly.get("conducted_sequence_number", "-")],
        ["Author", authoring.get("actor", "-")],
        ["Independent lesson review", review.get("decision", "-")],
        ["Instructor qualification", lesson.get("rehearsal", {}).get("decision", "-")],
        ["Asset count", len(assets)],
    ]
    story.append(Table([[paragraph(a, styles["label"]), paragraph(b, styles["body"])] for a, b in audit_rows], colWidths=[58 * mm, 107 * mm], style=TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#C8D6E0")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF3F8")),
        ("LEFTPADDING", (0, 0), (-1, -1), 2.5 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2.5 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
    ])))
    story.extend([
        Spacer(1, 7 * mm),
        paragraph("Operator review questions", styles["h2"]),
        paragraph("1. Is it always obvious what Ninereeds should look at?\n2. Is every teacher sentence understandable at the evidenced level?\n3. Do affirmative, negative, W-question, and OR-question forms stay separate before mixing?\n4. Are answer contracts and feedback unambiguous?\n5. Can Luna recover using only licensed tools?\n6. Is every stop or alarm condition explicit?", styles["body"]),
    ])
    doc.build(story)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lesson", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        render(args.lesson.resolve(), args.output.resolve(), force=args.force)
        print(f"rendered lesson PDF: {args.output.resolve()}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

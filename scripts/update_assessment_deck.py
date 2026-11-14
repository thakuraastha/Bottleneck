"""Apply four-member allocation and typography to the finalized assessment deck."""

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt


PATH = Path("/Users/aasthathakur/classwork/Bottleneck/docs/BOTTLENECK_Assessment_Presentation.pptx")


def replace(shape, value: str) -> None:
    shape.text_frame.clear()
    shape.text_frame.paragraphs[0].text = value


def set_font(shape, size: int, bold: bool | None = None) -> None:
    if not getattr(shape, "has_text_frame", False):
        return
    for paragraph in shape.text_frame.paragraphs:
        for run in paragraph.runs:
            run.font.name = "Poppins"
            run.font.size = Pt(size)
            if bold is not None:
                run.font.bold = bold


def set_color(shape, rgb: tuple[int, int, int]) -> None:
    for paragraph in shape.text_frame.paragraphs:
        for run in paragraph.runs:
            run.font.color.rgb = RGBColor(*rgb)


prs = Presentation(PATH)

for shape in prs.slides[0].shapes:
    if hasattr(shape, "text") and shape.text.startswith("Multi-Agent Supply-Chain Disruption"):
        replace(
            shape,
            "Multi-Agent Supply-Chain Disruption & Recovery\n"
            "Aastha Thakur · 230552  |  Shivani · Enrollment\n"
            "Mayank · Enrollment  |  Lokesh · Enrollment\n"
            "CSE3101 · November 2026",
        )
        shape.top = Inches(8.0)
        shape.height = Inches(1.25)
        set_color(shape, (255, 204, 0))

for shape in prs.slides[8].shapes:
    if hasattr(shape, "text") and (shape.text.startswith("MEMBER | RESPONSIBILITY") or shape.text.startswith("EQUAL CONTRIBUTION")):
        replace(
            shape,
            "EQUAL CONTRIBUTION — 25% EACH\n"
            "Aastha Thakur (230552) | Agent design, multi-agent architecture, orchestration, state management\n"
            "Shivani (Enrollment) | MCP design, A2A communication, guardrails and callbacks\n"
            "Mayank (Enrollment) | Observability, integration and testing, evaluation and documentation\n"
            "Lokesh (Enrollment) | Interface UI, deployment, live-demo validation and release quality",
        )
        shape.height = Inches(4.25)
        set_color(shape, (255, 204, 0))
    elif hasattr(shape, "text") and (shape.text.startswith("Single-member submission") or shape.text.startswith("Replace Member")):
        replace(shape, "All four members: equal 25% contribution. Insert the three pending enrollment numbers before submission.")
        shape.top = Inches(7.35)
        shape.height = Inches(0.8)
        set_color(shape, (255, 204, 0))

headings = {
    "Objectives & Deliverables", "Literature Review", "Multi-Agent Architecture",
    "Agent–Tool Communication · MCP", "Agent–Agent Communication · A2A",
    "Securing the Agentic System", "Deployment Architecture",
    "Team Responsibility / Self-Contribution", "Working System · Live Evidence",
    "Conclusions", "References",
}
navigation = {"ADK", "CrewAI", "MCP", "A2A", "Next Slide", "SLIDE 0", "SLIDE 1", "SLIDE 2", "BOTTLENECK"}
for slide_index, slide in enumerate(prs.slides):
    for shape in slide.shapes:
        if not hasattr(shape, "text") or not shape.text.strip():
            continue
        text = shape.text.strip()
        if text in headings or (slide_index == 0 and text == "BOTTLENECK" and shape.top > Inches(1)):
            set_font(shape, 64, True)
        elif text in navigation:
            set_font(shape, 18)
        else:
            set_font(shape, 22)

prs.save(PATH)
print(PATH)

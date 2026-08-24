"""CV tailoring system: modifies a DOCX template based on a job description.

Usage (CLI)::

    python -m job_bot.intelligence.generation.cv_tailor \
        --template "Patrick Hirwa Pm.docx" \
        --job-description "We are looking for a Senior PM..." \
        --output "tailored_cv.pdf"

Programmatic::

    from job_bot.intelligence.generation.cv_tailor import CVTailor
    tailor = CVTailor(provider)
    await tailor.tailor_to_job(template_path, job_description, output_pdf)
"""

import asyncio
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Optional

from docx import Document

from job_bot.intelligence.providers.base import LLMProvider


TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "templates"
DEFAULT_TEMPLATE = TEMPLATE_DIR / "Patrick Hirwa Pm.docx"

SYSTEM_PROMPT = (
    "You are a professional CV/resume writer. You tailor CVs to specific job "
    "descriptions to maximize ATS relevance and recruiter appeal. You output "
    "ONLY valid JSON — no markdown fences, no commentary."
)

USER_PROMPT_TEMPLATE = """You are tailoring a CV for Patrick Hirwa based on the job description below.

PATRICK'S BACKGROUND (current CV content):
{current_cv}

JOB DESCRIPTION:
{job_description}

Produce tailored CV content as JSON with these exact keys:

{{
  "summary": "3-4 sentences tailored to the role. Highlight relevant experience. No title line.",
  "skills_table": {{
    "Technical Expertise": "6-8 space-separated skills relevant to the job",
    "Project & Product Management": "5-6 space-separated skills relevant to the job",
    "Startup & Operations Skills": "5-6 space-separated skills relevant to the job",
    "Soft Skills": "5-6 space-separated skills relevant to the job"
  }},
  "achievements": [
    "Achievement 1 (1-2 sentences, quantify with % if possible)",
    "Achievement 2",
    "Achievement 3"
  ],
  "key_projects": [
    "Project Name1 - Brief description (1-2 sentences)",
    "Project Name2 - Brief description"
  ]
}}

Rules:
- Keep it honest — only reframe existing experience, do not invent new roles.
- Prioritize and reorder experience to match what the job description asks for.
- Mirror keywords from the job description naturally (ATS optimization).
- Use action verbs and quantify results where possible.
- Output ONLY the JSON, nothing else."""


def extract_current_cv(doc: Document) -> str:
    lines = []
    for p in doc.paragraphs:
        t = p.text.strip()
        if t:
            lines.append(f"[{p.style.name}] {t}")
    if doc.tables:
        for t in doc.tables:
            for row in t.rows:
                cells = [c.text.strip() for c in row.cells]
                lines.append(" | ".join(cells))
    return "\n".join(lines)


def _parse_llm_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        raw = m.group(0)
    return json.loads(raw)


def _replace_summary(doc: Document, new_summary: str):
    in_summary = False
    target_idx = None
    for i, p in enumerate(doc.paragraphs):
        if p.style.name == "Heading 2" and "SUMMARY" in p.text.upper():
            in_summary = True
            continue
        if in_summary:
            if p.style.name == "Normal" and p.text.strip():
                target_idx = i
                break
    if target_idx is None:
        for i, p in enumerate(doc.paragraphs):
            if p.text.strip().startswith("Tech-driven"):
                target_idx = i
                break
    if target_idx is not None:
        p = doc.paragraphs[target_idx]
        p.text = new_summary


def _replace_skills_table(doc: Document, skills: dict):
    if not doc.tables:
        return
    table = doc.tables[0]
    if len(table.rows) < 2 or len(table.columns) < 4:
        return
    headers = [table.cell(0, c).text.strip() for c in range(len(table.columns))]
    row = table.rows[1]
    for ci, header in enumerate(headers):
        if header in skills:
            row.cells[ci].text = skills[header]


def _replace_section_paragraphs(doc: Document, heading_text: str, new_items: list[str], style: str = "Body Text"):
    start_idx = None
    for i, p in enumerate(doc.paragraphs):
        if p.style.name in ("Heading 3", "Heading 2") and heading_text.upper() in p.text.upper():
            start_idx = i + 1
            break
    if start_idx is None:
        return
    target_indices = []
    for i in range(start_idx, len(doc.paragraphs)):
        p = doc.paragraphs[i]
        if p.style.name in ("Heading 3", "Heading 2", "Heading 4"):
            break
        if p.text.strip():
            target_indices.append(i)
    for i, idx in enumerate(target_indices):
        if i < len(new_items):
            doc.paragraphs[idx].text = new_items[i]
        else:
            doc.paragraphs[idx].text = ""


class CVTailor:
    def __init__(self, provider: LLMProvider, default_template: Optional[Path] = None):
        self.provider = provider
        self.default_template = default_template or DEFAULT_TEMPLATE

    async def tailor_to_job(
        self,
        job_description: str,
        template_path: Optional[Path] = None,
        output_pdf: Optional[Path] = None,
        output_docx: Optional[Path] = None,
    ) -> Path:
        template_path = Path(template_path or self.default_template)
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        doc = Document(str(template_path))
        current_cv = extract_current_cv(doc)
        prompt = USER_PROMPT_TEMPLATE.format(
            current_cv=current_cv,
            job_description=job_description,
        )
        raw_llm_response = await self.provider.generate(prompt, system=SYSTEM_PROMPT)
        try:
            tailored = _parse_llm_json(raw_llm_response)
        except json.JSONDecodeError:
            raise ValueError(f"LLM did not return valid JSON. Raw:\n{raw_llm_response[:500]}")

        _replace_summary(doc, tailored.get("summary", ""))
        _replace_skills_table(doc, tailored.get("skills_table", {}))
        _replace_section_paragraphs(
            doc, "ARCHIEVEMENTS", tailored.get("achievements", []), style="Body Text"
        )
        _replace_section_paragraphs(
            doc, "KEY", tailored.get("key_projects", []), style="Body Text"
        )

        output_docx = Path(output_docx) if output_docx else template_path.parent / "tailored_cv.docx"
        doc.save(str(output_docx))

        output_pdf = Path(output_pdf) if output_pdf else template_path.parent / "tailored_cv.pdf"
        self._convert_to_pdf(output_docx, output_pdf)
        return output_pdf

    @staticmethod
    def _convert_to_pdf(docx_path: Path, pdf_path: Path):
        from docx2pdf import convert
        convert(str(docx_path), str(pdf_path))


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Tailor a CV DOCX to a job description and output PDF.")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="Path to DOCX template")
    parser.add_argument("--job-description", required=True, help="Job description text (or path to .txt file)")
    parser.add_argument("--output", default="tailored_cv.pdf", help="Output PDF path")
    parser.add_argument("--output-docx", default=None, help="Optional intermediate DOCX path")
    parser.add_argument("--provider", default="opencode", help="LLM provider name")
    parser.add_argument("--model", default="deepseek-v4-flash-free", help="LLM model name")
    parser.add_argument("--api-key", default=None, help="LLM API key (defaults to env)")
    parser.add_argument("--base-url", default=None, help="LLM base URL")
    args = parser.parse_args()

    jd = args.job_description
    if Path(jd).exists():
        jd = Path(jd).read_text(encoding="utf-8")

    from job_bot.intelligence.providers.factory import create_provider

    provider_kwargs = {"model": args.model}
    if args.api_key:
        provider_kwargs["api_key"] = args.api_key
    if args.base_url:
        provider_kwargs["base_url"] = args.base_url
    provider = create_provider(args.provider, **provider_kwargs)

    tailor = CVTailor(provider)
    pdf_path = asyncio.run(
        tailor.tailor_to_job(
            job_description=jd,
            template_path=Path(args.template),
            output_pdf=Path(args.output),
            output_docx=Path(args.output_docx) if args.output_docx else None,
        )
    )
    print(f"Generated: {pdf_path}")


if __name__ == "__main__":
    main()

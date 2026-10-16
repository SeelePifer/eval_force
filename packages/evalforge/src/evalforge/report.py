from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from evalforge.models import EvalRun

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def render_report(run: EvalRun) -> str:
    environment = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(enabled_extensions=("html", "j2")),
    )
    environment.filters["quality"] = lambda value: f"{float(value):.3f}"
    environment.filters["usd"] = lambda value: f"{float(value):.6f}"
    environment.filters["ms"] = lambda value: f"{float(value):.1f}"
    environment.filters["optional"] = lambda value: "—" if value is None else f"{float(value):.3f}"
    template = environment.get_template("report.html.j2")
    return template.render(run=run.model_dump())

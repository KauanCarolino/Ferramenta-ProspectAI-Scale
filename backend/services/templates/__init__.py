"""Pacote do serviço de templates."""

from services.templates.service import (
    ALLOWED_VARS,
    count_spintax_groups,
    create_template,
    delete_template,
    extract_variables,
    get_template,
    list_templates,
    preview_template,
    render_template,
    update_template,
    validate_template_body,
)

__all__ = [
    "ALLOWED_VARS",
    "count_spintax_groups",
    "create_template",
    "delete_template",
    "extract_variables",
    "get_template",
    "list_templates",
    "preview_template",
    "render_template",
    "update_template",
    "validate_template_body",
]

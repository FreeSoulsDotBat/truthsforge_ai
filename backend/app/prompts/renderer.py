from __future__ import annotations

import re

VARIABLE_RE = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")


def render_prompt(template: str, variables: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        return variables.get(match.group(1), match.group(0))

    return VARIABLE_RE.sub(replace, template)

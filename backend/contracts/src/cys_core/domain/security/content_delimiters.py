from __future__ import annotations


def wrap_delimited_block(content: str, *, header: str, begin: str, end: str) -> str:
    return f"{header}\n{begin}\n{content}\n{end}"


def wrap_retrieved_tool_data(content: str) -> str:
    return wrap_delimited_block(
        content,
        header="RETRIEVED_TOOL_DATA:",
        begin="BEGIN_RETRIEVED_CONTENT",
        end="END_RETRIEVED_CONTENT",
    )


def wrap_skill_content(content: str) -> str:
    return wrap_delimited_block(
        content,
        header="SKILL_CONTENT:",
        begin="BEGIN_SKILL_CONTENT",
        end="END_SKILL_CONTENT",
    )


def wrap_retrieved_chunks_body(body: str) -> str:
    return wrap_delimited_block(
        body,
        header="",
        begin="BEGIN_RETRIEVED_CONTENT",
        end="END_RETRIEVED_CONTENT",
    ).lstrip("\n")

"""
Request field limits
====================
Constrained string and list types for request bodies.

Every text field a client can send has an upper bound, so one request cannot
push megabytes into DynamoDB, a Bedrock prompt or a LaTeX compile. FastAPI
rejects anything outside these bounds with a 422 before a handler runs.
"""

from typing import Annotated, List, TypeVar

from pydantic import Field, StringConstraints

T = TypeVar("T")

#: A required single-line name or title.
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
#: An optional single-line value such as a city, degree or company.
ShortText = Annotated[str, StringConstraints(max_length=300)]
#: A paragraph such as a summary, project description or note.
Paragraph = Annotated[str, StringConstraints(max_length=5_000)]
#: A pasted job description or a chat message to the resume assistant.
LongText = Annotated[str, StringConstraints(max_length=50_000)]
#: A full LaTeX resume. Real resumes are 5 to 30 KB.
LatexSource = Annotated[str, StringConstraints(max_length=200_000)]
#: A URL.
Url = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2_048)]
#: An opaque id from a path or body, such as a job or role id.
Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
#: A new password. bcrypt only reads the first 72 bytes.
NewPassword = Annotated[str, StringConstraints(min_length=8, max_length=72)]
#: A password at sign-in, checked only for size so existing accounts still work.
Password = Annotated[str, StringConstraints(min_length=1, max_length=72)]

#: A list of short tags such as technologies or skills.
TagList = Annotated[List[ShortText], Field(max_length=100)]


def bounded_list(item: type[T], max_items: int = 100) -> type[List[T]]:
    """A list of `item` that holds at most `max_items` entries."""
    return Annotated[List[item], Field(max_length=max_items)]  # type: ignore[return-value]

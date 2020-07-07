# Copyright 2017-present Kensho Technologies, LLC.
import re

import six


def remove_custom_formatting(query: str) -> str:
    """Prepare the query string for pretty-printing by removing all unusual formatting."""
    query = re.sub("[\n ]+", " ", query)
    return query.replace("( ", "(").replace(" )", ")")


def pretty_print_gremlin(gremlin: str) -> str:
    """Return a human-readable representation of a gremlin command string."""
    gremlin = remove_custom_formatting(gremlin)
    too_many_parts = re.split(r"([)}]|scatter)[ ]?\.", gremlin)

    # Put the ) and } back on.
    parts = [
        too_many_parts[i] + too_many_parts[i + 1]
        for i in six.moves.xrange(0, len(too_many_parts) - 1, 2)
    ]
    parts.append(too_many_parts[-1])

    # Put the . back on.
    for i in six.moves.xrange(1, len(parts)):
        parts[i] = "." + parts[i]

    indentation = 0
    indentation_increment = 4
    output = []
    for current_part in parts:
        if any(
            [
                current_part.startswith(".out"),
                current_part.startswith(".in"),
                current_part.startswith(".ifThenElse"),
            ]
        ):
            indentation += indentation_increment
        elif current_part.startswith(".back") or current_part.startswith(".optional"):
            indentation -= indentation_increment
            if indentation < 0:
                raise AssertionError("Indentation became negative: {}".format(indentation))

        output.append((" " * indentation) + current_part)

    return "\n".join(output).strip()


def pretty_print_match(match: str, parameterized: bool = True) -> str:
    """Return a human-readable representation of a parameterized MATCH query string."""
    left_curly = "{{" if parameterized else "{"
    right_curly = "}}" if parameterized else "}"
    match = remove_custom_formatting(match)
    parts = re.split("({}|{})".format(left_curly, right_curly), match)

    inside_braces = False
    indent_size = 4
    indent = " " * indent_size

    output = [parts[0]]
    for current_index, current_part in enumerate(parts[1:]):
        if current_part == left_curly:
            if inside_braces:
                raise AssertionError(
                    "Found open-braces pair while already inside braces: "
                    "{} {} {}".format(current_index, parts, match)
                )
            inside_braces = True
            output.append(current_part + "\n")
        elif current_part == right_curly:
            if not inside_braces:
                raise AssertionError(
                    "Found close-braces pair while not inside braces: "
                    "{} {} {}".format(current_index, parts, match)
                )
            inside_braces = False
            output.append(current_part)
        else:
            if not inside_braces:
                stripped_part = current_part.lstrip()
                if stripped_part.startswith("."):
                    # Strip whitespace before traversal steps.
                    output.append(stripped_part)
                else:
                    # Do not strip whitespace before e.g. the RETURN keyword.
                    output.append(current_part)
            else:
                # Split out the keywords, initially getting rid of commas.
                separate_keywords = re.split(", ([a-z]+:)", current_part)

                # The first item in the separated list is the full first "keyword: value" pair.
                # For every subsequent item, the keyword and value are separated; join them
                # back together, outputting the comma, newline and indentation before them.
                output.append(indent + separate_keywords[0].lstrip())
                for i in six.moves.xrange(1, len(separate_keywords) - 1, 2):
                    output.append(
                        ",\n{indent}{keyword} {value}".format(
                            keyword=separate_keywords[i].strip(),
                            value=separate_keywords[i + 1].strip(),
                            indent=indent,
                        )
                    )
                output.append("\n")

    return "".join(output).strip()

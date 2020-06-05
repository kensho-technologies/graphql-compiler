from typing import Iterable

from .typedefs import DataContext


def print_tap(info: str, data_contexts: Iterable[DataContext]) -> Iterable[DataContext]:
    # TODO(predrag): Debug-only code. Remove before merging.
    return data_contexts


#     print('\n')
#     unique_id = hash(info)
#     print(unique_id, info)
#     from funcy.py3 import chunks
#     for context_chunk in chunks(100, data_contexts):
#         for context in context_chunk:
#             pprint((unique_id, context))
#             yield context

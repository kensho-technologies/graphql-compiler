# Copyright 2020-present Kensho Technologies, LLC.
"""Tools for constructing high-performance query interpreters over arbitrary schemas.

While GraphQL compiler's database querying capabilities are sufficient for many use cases, there are
many types of data querying for which the compilation-based approach is unsuitable. A few examples:
- data accessible via a simple API instead of a rich query language,
- data represented as a set of files and directories on a local disk,
- data produced on-demand by running a machine learning model over some inputs.

The data in each of these cases can be described by a valid schema, and users could write
well-defined and legal queries against that schema. However, the execution of such queries cannot
proceed by compiling them to another query language -- no such target query language exists.
Instead, the queries need to be executed using an *interpreter*: a piece of code
that executes queries incrementally in a series of steps, such as "fetch the value of this field"
or "filter out this data point if its value is less than 5."

Some parts of the interpreter (e.g. "fetch the value of this field") obviously need to be aware of
the schema and the underlying data source. Other parts (e.g. "filter out this data point") are
schema-agnostic -- they work in the same way regardless of the schema and data source. This library
provides efficient implementations of all schema-agnostic interpreter components. All schema-aware
logic is abstracted into the straightforward API of the InterpreterAdapter class, which should be
subclassed to create a new interpreter over a new dataset.
logic is abstracted into the straightforward, four-method API of the InterpreterAdapter class,
which should be subclassed to create a new interpreter over a new dataset.

As a result, the development of a new interpreter looks like this:
- Construct the schema of the data your new interpreter will be querying.
- Construct a subclass InterpreterAdapter class -- let's call it MyCustomAdapter.
- Add long-lived interpreter state such as API keys, connection pools, etc. as instance attributes
  of the MyCustomAdapter class.
- Implement the four simple functions that form the InterpreterAdapter API.
- Construct an instance of MyCustomAdapter and pass it to the schema-agnostic portion of
  the interpreter implemented in this library, such as the interpret_ir() function.
- You now have a way to execute queries over your schema! Then, profit!

For more information, consult the documentation of the items exported below.
"""

from ..compiler.metadata import FilterInfo  # re-export due to use in interpreter API  # noqa
from .api import interpret_ir, interpret_query  # noqa
from .typedefs import DataContext, DataToken, EdgeInfo, InterpreterAdapter, NeighborHint  # noqa

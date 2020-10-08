# Copyright 2020-present Kensho Technologies, LLC.
from abc import ABCMeta, abstractmethod
from typing import (
    AbstractSet,
    Any,
    Collection,
    Generic,
    Iterable,
    Mapping,
    Optional,
    Tuple,
    TypeVar,
)

from ..compiler.metadata import FilterInfo
from ..typedefs import Literal


DataToken = TypeVar("DataToken")


class DataContext(Generic[DataToken]):
    pass  # TODO(predrag): Will be implemented and documented in a later PR.


EdgeDirection = Literal["in", "out"]
EdgeInfo = Tuple[EdgeDirection, str]  # direction + edge name

# TODO(predrag): Figure out a better type here. We need to balance between finding something
#                easy and lightweight, and letting the user know about things like:
#                optional edges, recursive edges, used fields/filters at the neighbor, etc.
#                Will probably punt on this until the API is stabilized, since defining something
#                here is not a breaking change.
NeighborHint = Any


class InterpreterAdapter(Generic[DataToken], metaclass=ABCMeta):
    """Base class defining the API for schema-aware interpreter functionality over some schema.

    This ABC is the abstraction through which the rest of the interpreter is schema-agnostic:
    the rest of the interpreter code simply takes an instance of InterpreterAdapter and performs
    all schema-aware operations through its simple, four-method API.

    ## The DataToken type parameter

    This class is generic on an implementer-chosen DataToken type, which to the rest of the library
    represents an opaque reference to the data contained by a particular vertex in the data set
    described by your chosen schema. For example, if building a subclass of InterpreterAdapter
    called MyAdapter with dict as the DataToken type, MyAdapter should be defined as follows:

        class MyAdapter(InterpreterAdapter[dict]):
            ...

    Here are a few common examples of DataToken types in practice:
    - a dict containing the type name of the vertex and the values of all its properties;
    - a dataclass containing the type name of the vertex, and a collection name and primary key
      that can be used to retrieve its property values from a database, or
    - an instance of a custom class which has *some* of the values of the vertex properties, and
      has sufficient information to look up the rest of them if they are ever requested.

    The best choice of DataToken type is dependent on the specific use case, e.g. whether the data
    is already available in Python memory, or is on a local disk, or is a network hop away.

    Implementers are free to choose any DataToken type and the interpreter code will happily use it.
    However, certain debugging and testing tools provided by this library will work best
    when DataToken is a deep-copyable type that implements
    equality beyond a simple referential equality check.

    ## The InterpreterAdapter API

    The methods in the InterpreterAdapter API are all designed to support generator-style operation,
    where data is produced and consumed only when required. Here is a high-level description of
    the methods in the InterpreterAdapter API:
    - get_tokens_of_type() produces an iterable of DataTokens of the type specified by its argument.
      The calling function will wrap the DataTokens into a bookkeeping object called a DataContext,
      where a particular token is currently active and specified in the "current_token" attribute.
    - For an iterable of such DataContexts, project_property() can be used to get the value
      of one of the properties on the vertex type represented by the currently active DataToken
      in each DataContext; project_property() therefore returns an iterable of
      tuples (data_context, value).
    - project_neighbors() is similar: for an iterable of DataContexts and a specific edge name,
      it returns an iterable (data_context, iterable_of_neighbor_tokens) where
      iterable_of_neighbor_tokens yields a DataToken for each vertex that can be reached by
      following the specified edge from data_context's vertex.
    - can_coerce_to_type() is used to check whether a DataToken corresponding to one vertex type
      can be safely converted into one representing a different vertex type. Given an iterable of
      DataContexts and the name of the type to which the conversion is attempted, it produces
      an iterable of tuples (data_context, can_coerce), where can_coerce is a boolean.

    ## Performance and optimization opportunities

    The design of the API and its generator-style operation enable a variety of optimizations.
    Many optimizations are applied automatically, and additional ones can be implemented with
    minimal additional work. A few simple examples:
    - Interpreters perform lazy evaluation by default: if exactly 3 query results are requested,
      then only the minimal data necessary for *exactly 3* results' worth of outputs is loaded.
    - When computing a particular result, data loading for output fields is deferred
      until *after* all filtering operations have been completed, to minimize data loads.
    - Data caching is easy to implement within this API -- simply have
      your API function's implementation consult a cache before performing the requested operation.
    - Batch-loading of data can be performed by simply advancing the input generator multiple times,
      then operating on an entire batch of input data before producing corresponding outputs:

        def project_property(
            self,
            data_contexts: Iterable[DataContext[DataToken]],
            current_type_name: str,
            field_name: str,
            **hints: Any
        ) -> Iterable[Tuple[DataContext[DataToken], Any]]:
            for data_context_batch in funcy.chunks(30, data_contexts):
                # Data for 30 entries is now in data_context_batch, operate on it in bulk.
                results_batch = compute_results_for_batch(
                    data_context_batch, current_type_name, field_name
                )
                yield from results_batch

    Additionally, each of the four methods in the API takes several kwargs whose names
    end with the suffix "_hints", in addition to the catch-all "**hints: Any" argument. These
    provide each function with information about how the data it is currently processing will
    be used in subsequent operations, and can therefore enable additional interesting optimizations.
    Use of these hints is optional (the interpreter always assumes that the hints weren't used),
    so subclasses of InterpreterAdapter may even safely ignore these kwargs entirely -- for example,
    if the "runtime_arg_hints" kwarg is omitted in the method definition, at call time its value
    will go into the catch-all "**hints" argument instead.

    The set of hints (and the information each hint provides) could grow in the future. Currently,
    the following hints are offered:
    - runtime_arg_hints: the names and values of any runtime arguments provided to the query
      for use in filtering operations (e.g. "$arg_name"); an empty mapping in queries
      with no runtime arguments.
    - used_property_hints: the property names in the current scope that are used by the query,
      e.g. in a filter or as an output. Within project_neighbors(), the current scope is the
      neighboring vertex; in the remaining 3 methods the current scope is the current vertex.
    - filter_hints: information about the filters applied within the current scope,
      such as "which filtering operation is being performed?" and "with which arguments?"
      Within project_neighbors(), the current scope is the neighboring vertex; in
      the remaining 3 methods the current scope is the current vertex.
    - neighbor_hints: information about the edges originating from the current scope that
      the query will eventually need to expand. Within project_neighbors(), the current scope is
      the neighboring vertex; in the remaining 3 methods the current scope is the current vertex.

    More details on these hints, and suggestions for their use, can be found in the methods'
    docstrings, available below.
    """

    @abstractmethod
    def get_tokens_of_type(
        self,
        type_name: str,
        *,
        runtime_arg_hints: Optional[Mapping[str, Any]] = None,
        used_property_hints: Optional[AbstractSet[str]] = None,
        filter_hints: Optional[Collection[FilterInfo]] = None,
        neighbor_hints: Optional[Collection[Tuple[EdgeInfo, NeighborHint]]] = None,
        **hints: Any,
    ) -> Iterable[DataToken]:
        """Produce an iterable of tokens for the specified type name.

        This function is used by the interpreter library to get the initial data with which
        the process of query execution begins.

        Consider the following example schema:
        ***
        schema {
            query: RootSchemaQuery
        }

        < ... some default GraphQL compiler directives and scalar type definitions here ... >

        type Foo {
            < ... some fields here ... >
        }

        < ... perhaps other type definitions here ... >

        type RootSchemaQuery {
            # This is the root query type for the schema, as defined at the top of the schema.
            Foo: [Foo]
        }
        ***

        Per the GraphQL specification, since the definition of RootSchemaQuery only contains the
        type named Foo, queries must start by querying for Foo in order to be valid for the schema:
        {
            Foo {
                < stuff here >
            }
        }

        To compute the results for such a query, the interpreter would call get_tokens_of_type()
        with "Foo" as the type_name value. As get_tokens_of_type() yields tokens,
        the interpreter uses those tokens to perform the rest of the query via
        the remaining interpreter API methods.

        get_tokens_of_type() is guaranteed to be called *exactly once* during the evaluation of
        any interpreted query. However, due to the generator-style operation of the interpreter,
        the call to get_tokens_of_type() is *not* guaranteed to be the first call across the four
        methods that comprise this API -- one or more calls to the other methods may precede it.

        Args:
            type_name: name of the vertex type for which to yield tokens. Guaranteed to be:
                       - the name of a type defined in the schema being queried, and specifically
                       - one of the types defined in the schema's root query type:
                         http://spec.graphql.org/June2018/#sec-Root-Operation-Types
            runtime_arg_hints: names and values of any runtime arguments provided to the query
                               for use in filtering operations (e.g. "$arg_name").
            used_property_hints: the property names of the requested vertices that
                                 are going to be used in a subsequent filtering or output step.
            filter_hints: information about any filters applied to the requested vertices,
                          such as "which filtering operations are being performed?"
                          and "with which arguments?"
            neighbor_hints: information about the edges originating from the requested vertices
                            that the query will eventually need to expand.
            **hints: catch-all kwarg field making the function's signature forward-compatible with
                     future revisions of this library that add more hints.

        Yields:
            DataTokens corresponding to vertices of the specified type. The information supplied
            via hints may, but is not required to, be applied to the returned DataToken objects.
            For example, this function is allowed to yield a DataToken that will be filtered out
            in a subsequent query step, even though the filter_hints argument (or other hints)
            notified this function of that impending outcome.
        """

    @abstractmethod
    def project_property(
        self,
        data_contexts: Iterable[DataContext[DataToken]],
        current_type_name: str,
        field_name: str,
        *,
        runtime_arg_hints: Optional[Mapping[str, Any]] = None,
        used_property_hints: Optional[AbstractSet[str]] = None,
        filter_hints: Optional[Collection[FilterInfo]] = None,
        neighbor_hints: Optional[Collection[Tuple[EdgeInfo, NeighborHint]]] = None,
        **hints: Any,
    ) -> Iterable[Tuple[DataContext[DataToken], Any]]:
        """Produce the values for a given property for each of an iterable of input DataTokens."""
        # TODO(predrag): Add more docs in an upcoming PR.

    @abstractmethod
    def project_neighbors(
        self,
        data_contexts: Iterable[DataContext[DataToken]],
        current_type_name: str,
        edge_info: EdgeInfo,
        *,
        runtime_arg_hints: Optional[Mapping[str, Any]] = None,
        used_property_hints: Optional[AbstractSet[str]] = None,
        filter_hints: Optional[Collection[FilterInfo]] = None,
        neighbor_hints: Optional[Collection[Tuple[EdgeInfo, NeighborHint]]] = None,
        **hints: Any,
    ) -> Iterable[Tuple[DataContext[DataToken], Iterable[DataToken]]]:
        """Produce the neighbors along a given edge for each of an iterable of input DataTokens."""
        # TODO(predrag): Add more docs in an upcoming PR.
        #
        # If using a generator or a mutable data type for the Iterable[DataToken] part,
        # be careful! Make sure any state it depends upon
        # does not change, or that bug will be hard to find.

    @abstractmethod
    def can_coerce_to_type(
        self,
        data_contexts: Iterable[DataContext[DataToken]],
        current_type_name: str,
        coerce_to_type_name: str,
        *,
        runtime_arg_hints: Optional[Mapping[str, Any]] = None,
        used_property_hints: Optional[AbstractSet[str]] = None,
        filter_hints: Optional[Collection[FilterInfo]] = None,
        neighbor_hints: Optional[Collection[Tuple[EdgeInfo, NeighborHint]]] = None,
        **hints: Any,
    ) -> Iterable[Tuple[DataContext[DataToken], bool]]:
        """Determine if each of an iterable of input DataTokens can be coerced to another type."""
        # TODO(predrag): Add more docs in an upcoming PR.

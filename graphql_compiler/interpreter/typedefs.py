# Copyright 2020-present Kensho Technologies, LLC.
from abc import ABCMeta, abstractmethod
from typing import AbstractSet, Any, Collection, Generic, Iterable, Mapping, Optional, Tuple

from ..compiler.metadata import FilterInfo
from ..typedefs import Literal, TypedDict
from .data_context import DataContext, DataToken


EdgeDirection = Literal["in", "out"]
EdgeInfo = Tuple[EdgeDirection, str]  # direction + edge name

# TODO(predrag): Figure out a better type here. We need to balance between finding something
#                easy and lightweight, and letting the user know about things like:
#                optional edges, recursive edges, used fields/filters at the neighbor, etc.
#                Will probably punt on this until the API is stabilized, since defining something
#                here is not a breaking change.
NeighborHint = Any


class InterpreterHints(TypedDict):
    """Describe all known hint types.

    Values of this type are intended to be used as "**hints" syntax in adapter calls.
    """

    runtime_arg_hints: Mapping[str, Any]  # the runtime arguments passed for this query
    used_property_hints: AbstractSet[str]  # the names of all property fields used within this scope
    filter_hints: Collection[FilterInfo]  # info on all filters used within this scope
    neighbor_hints: Collection[Tuple[EdgeInfo, NeighborHint]]  # info on all neighbors of this scope


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
    when DataToken is a deep-copyable type that implements equality beyond
    a simple referential equality check.

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

        Per the GraphQL specification, since the definition of RootSchemaQuery only contains the
        type named Foo, queries must start by querying for Foo in order to be valid for the schema:
            {
                Foo {
                    < ... stuff here ... >
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
        """Produce the values for a given property for each of an iterable of input DataTokens.

        In situations such as outputting property values or applying filters to properties,
        the interpreter needs to get the value of some property field for a series of DataTokens.

        For example, consider the following query:
            {
                Foo {
                    bar @output(out_name: "bar_value")
                }
            }

        Once the interpreter has used the get_tokens_of_type() function to obtain
        an iterable of DataTokens for the Foo type, it will automatically wrap each of them in
        a "bookkeeping" object called DataContext. These DataContext objects allow
        the interpreter to keep track of "which data came from where"; only the DataToken value
        bound to each current_token attribute is relevant to the InterpreterAdapter API.

        Having obtained an iterable of DataTokens and converted it to an iterable of DataContexts,
        the interpreter needs to get the value of the "bar" property for the tokens bound to
        the contexts. To do so, the interpreter calls project_property() with the iterable
        of DataContexts, setting current_type_name = "Foo" and field_name = "bar", requesting
        the "bar" property's value for each DataContext with its corresponding current_token.
        If the DataContext's current_token attribute is set to None (which may happen
        when @optional edges are used), the property's value is considered to be None.

        A simple example implementation is as follows:
            def project_property(
                self,
                data_contexts: Iterable[DataContext[DataToken]],
                current_type_name: str,
                field_name: str,
                **hints: Any,
            ) -> Iterable[Tuple[DataContext[DataToken], Any]]:
                for data_context in data_contexts:
                    current_token = data_context.current_token
                    property_value: Any
                    if current_token is None:
                        # Evaluating an @optional scope where the optional edge didn't exist.
                        # There is no value for the named property here.
                        property_value = None
                    else:
                        if field_name == "__typename":
                            # The query is requesting the runtime type of the current vertex.
                            # If current_type_name is an interface type, the runtime type of
                            # the current vertex may either be that interface type or
                            # a type that implements that interface. More info on "__typename"
                            # can be found at https://graphql.org/learn/queries/#meta-fields
                            property_value = < load the runtime type of the current_token vertex >
                        else:
                            property_value = (
                                < load the value of the field_name property for current_token >
                            )

                    # Remember to always yield the DataContext alongside the produced value.
                    yield data_context, property_value

        Args:
            data_contexts: iterable of DataContext objects which specify the DataTokens whose
                           property data needs to be loaded
            current_type_name: name of the vertex type whose property needs to be loaded. Guaranteed
                               to be the name of a type defined in the schema being queried.
                               (current_type_name names the concrete type of DataToken contained in
                               the DataContext containers yielded by the data_context iterator.)
            field_name: name of the property whose data needs to be loaded. Guaranteed to refer
                        either to a property that is defined in the supplied current_type_name
                        in the schema, or to the "__typename" meta field that is valid for all
                        GraphQL types and holds the type name of the current vertex. This type name
                        may be different from the value of current_type_name e.g. when
                        current_type_name refers to an interface type and "__typename" refers to
                        a type that implements that interface. More information on "__typename" may
                        be found in the GraphQL docs: https://graphql.org/learn/queries/#meta-fields
            runtime_arg_hints: names and values of any runtime arguments provided to the query
                               for use in filtering operations (e.g. "$arg_name").
            used_property_hints: the property names of the vertices being processed that
                                 are going to be used in a subsequent filtering or output step.
            filter_hints: information about any filters applied to the vertices being processed,
                          such as "which filtering operations are being performed?"
                          and "with which arguments?"
            neighbor_hints: information about the edges of the vertices being processed
                            that the query will eventually need to expand.
            **hints: catch-all kwarg field making the function's signature forward-compatible with
                     future revisions of this library that add more hints.

        Yields:
            tuples (data_context, property_value), providing the value of the requested property
            together with the DataContext corresponding to that value. The yielded DataContext
            values must be yielded in the same order as they were received via the function's
            data_contexts argument.
        """

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
        """Produce the neighbors along a given edge for each of an iterable of input DataTokens.

        To support traversing edges, as well as directives such as @optional and @recurse,
        the interpreter needs to get the neighboring vertices along a particular edge for
        a series of DataTokens.

        For example, consider the following query:
            {
                Foo {
                    out_Foo_Bar {
                        < ... some fields here ... >
                    }
                }
            }

        Once the interpreter has used the get_tokens_of_type() function to obtain
        an iterable of DataTokens for the Foo type, it will automatically wrap each of them in
        a "bookkeeping" object called DataContext. These DataContext objects allow
        the interpreter to keep track of "which data came from where"; only the DataToken value
        bound to each current_token attribute is relevant to the InterpreterAdapter API.

        Having obtained an iterable of DataTokens and converted it to an iterable of DataContexts,
        the interpreter needs to find the neighbors along the outbound Foo_Bar edge for each of
        those DataTokens. To do so, the interpreter calls project_neighbors() with the iterable of
        DataContexts, setting current_type_name = "Foo" and edge_info = ("out", "Foo_Bar").  This
        function call requests an iterable of DataTokens representing the neighboring vertices for
        each current_token contained in a DataContext.  If the DataContext's current_token
        attribute is set to None (which may happen when @optional edges are used), an empty
        iterable of neighboring DataTokens should be returned.

        A simple example implementation is as follows:
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
                for data_context in data_contexts:
                    current_token = data_context.current_token
                    neighbors: Iterable[DataToken]
                    if current_token is None:
                        # Evaluating an @optional scope where the optional edge didn't exist.
                        # There are no neighbors here.
                        neighbors = []
                    else:
                        neighbors = _your_function_that_gets_neighbors_for_a_given_token(
                            current_type_name, edge_info, current_token
                        )

                    # Remember to always yield the DataContext alongside the produced value
                    yield data_context, neighbors

        ## Common bug to avoid in your implementation

        In the previous code example, note that we called a module-scoped function,
        `_your_function_that_gets_neighbors_for_a_given_token`, instead of one defined in the scope
        of `project_neighbors`.  Because Python evaluates references to variables in outer scopes
        at the time a function or generator is invoked--not at the time it's defined--, it's very
        easy to introduce subtle race conditions when defining generator factories in a nested
        scope.

        Because generators may be evaluated in arbitrary order, these bugs can appear only
        intermittently and can be very difficult to troubleshoot.  Always defining generator
        factories in the module scope is one reliable way to avoid this problem.

        In this example code, we use a for-loop to yield several generators from a generator
        factory.  Notice that we don't pass any arguments to the generator factory--the value its
        generators yield come from its enclosing scope.

        >>> def yield_generators():
        ...     for target in range(1, 4):
        ...         def _generator_factory():
        ...             while True:
        ...                 # refers to `target` in the enclosing scope
        ...                 yield target
        ...         yield _generator_factory()
        ...
        >>> gens = yield_generators()
        >>> one = next(gens)
        >>> next(one)
        1
        >>> two = next(gens)
        >>> next(two)
        2
        >>> next(one)  # We expect 1, but get 2
        2
        >>> three = next(gens)
        >>> next(three)
        3
        >>> next(two)  # We expect 2, but get 3
        3
        >>> next(one)  # We expect 1, got 2, and now get 3
        3

        Although we have three distinct generators, they're all yielding the same `target` from
        `yield_generator`'s scope, which is also the same `target` that the for-loop advances with
        each iteration.

        If we define `_generator_factory` in the scope of the module, then we can't refer
        inadvertently to shared state in an enclosing scope, which saves us from this bug.

        >>> def _generator_factory(target):
        ...     while True:
        ...         # refers to the argument `target`, which exists
        ...         # only in the local scope
        ...         yield target
        ...
        >>> def yield_generators():
        ...     for target in range(1, 4):
        ...         yield _generator_factory(target)
        ...
        >>> gens = yield_generators()
        >>> one = next(gens)
        >>> next(one)
        1
        >>> two = next(gens)
        >>> next(two)
        2
        >>> next(one)
        1
        >>> three = next(gens)
        >>> next(three)
        3
        >>> next(two)
        2
        >>> next(one)
        1

        ## Hints supplied to this function refer to neighboring vertices

        Hint kwargs in this function, such as used_property_hints, filter_hints, and
        neighbor_hints, describe the desired structure of the *neighboring* vertices that this
        function produces (as opposed to the vertices supplied via the data_contexts argument).
        For example, consider the following query:
            {
                Foo {
                    out_Foo_Bar {
                        name @output(out_name: "name")
                    }
                }
            }
        To traverse the out_Foo_Bar edge, project_neighbors() is called with
        used_property_hints=frozenset({"name"}) and data_contexts=<Iterable of DataContexts
        pointing to Foo vertices>. This is because used_property_hints correspond to
        neighboring vertices, and the neighboring Bar vertices (along the outbound Foo_Bar edge)
        are being queried for their "name" property.

        Args:
            data_contexts: iterable of DataContext objects which specify the DataTokens whose
                           neighboring DataTokens need to be loaded.
            current_type_name: name of the vertex type whose neighbors need to be loaded. Guaranteed
                               to be the name of a type defined in the schema being queried.
            edge_info: direction and name of the edge along which neighboring vertices need to be
                       loaded. For example, in the query example above, this argument would be set
                       to ("out", "Foo_Bar").
            runtime_arg_hints: names and values of any runtime arguments provided to the query
                               for use in filtering operations (e.g. "$arg_name").
            used_property_hints: property names of the neighboring vertices being loaded that
                                 are going to be used in a subsequent filtering or output step.
            filter_hints: information about any filters applied to the neighboring vertices being
                          loaded, such as "which filtering operations are being performed?"
                          and "with which arguments?"
            neighbor_hints: information about the edges of the neighboring vertices being loaded
                            that the query will eventually need to expand.
            **hints: catch-all kwarg field making the function's signature forward-compatible with
                     future revisions of this library that add more hints.

        Yields:
            tuples (data_context, iterable_of_neighbor_tokens), providing the tokens of
            the neighboring vertices together with the DataContext corresponding to those neighbors.
            The yielded DataContext values must be yielded in the same order as they were received
            via the function's data_contexts argument.
        """

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
        """Determine if each of an iterable of input DataTokens can be coerced to another type.

        Consider a query like the following:
            {
                Foo {
                    out_Foo_Bar {
                        ... on BarImpl {
                            < ... some fields here ... >
                        }
                    }
                }
            }

        Assume that this query is written against a schema that contains the following definitions:
            type Foo {
                < ... some fields here ... >
                out_Foo_Bar: [Bar]
            }

            interface Bar {
                < ... some fields here ... >
            }

            type BarImpl implements Bar {
                < ... some fields here ... >
            }

        When resolving the out_Foo_Bar edge in the query using project_neighbors(), the interpreter
        receives DataTokens that (per the schema) are instances of the Bar interface type. However,
        the query's subsequent "... on BarImpl" type coercion clause requires that the interpreter
        discard any neighboring vertices that are not instances of BarImpl, a subtype of
        the Bar interface type.

        The interpreter uses can_coerce_to_type() for this purpose: it calls this function with
        an iterable of DataContexts, with current_type_name set to "Bar" (the schema-implied type
        of the query's scope) and with coerce_to_type_name set to "BarImpl" (the type to which
        coercion is being attempted). For each DataContext in the input iterable, this function
        yields a tuple containing the context itself and a bool set to True if the coercion
        to the new type could be completed.

        A simple example implementation is as follows:
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
                for data_context in data_contexts:
                    current_token = data_context.current_token
                    can_coerce: bool
                    if current_token is None:
                        # Evaluating an @optional scope where the optional edge didn't exist.
                        # We cannot coerce something that doesn't exist.
                        can_coerce = False
                    else:
                        can_coerce = (
                            < check whether current_token represents a vertex
                                of type coerce_to_type_name >
                        )

                    # Remember to always yield the DataContext alongside the bool result.
                    yield data_context, can_coerce

        Args:
            data_contexts: iterable of DataContext objects which specify the DataTokens that are
                           being coerced to a new type
            current_type_name: name of the vertex type from which the vertices are being coerced.
                               Guaranteed to be the name of an interface or union type defined
                               in the schema being queried.
            coerce_to_type_name: name of the vertex type to which the vertices are being coerced.
                                 Guaranteed to be the name of a type defined in the schema being
                                 queried. If current_type_name refers to an interface type, then
                                 coerce_to_type_name is guaranteed to refer to a type that
                                 implements that interface. If current_type_name refers to a union
                                 type, then coerce_to_type_name is guaranteed to refer to a type
                                 that is a member of that union type.
            runtime_arg_hints: names and values of any runtime arguments provided to the query
                               for use in filtering operations (e.g. "$arg_name").
            used_property_hints: the property names of the vertices being processed that
                                 are going to be used in a subsequent filtering or output step.
            filter_hints: information about any filters applied to the vertices being processed,
                          such as "which filtering operations are being performed?"
                          and "with which arguments?"
            neighbor_hints: information about the edges of the vertices being processed
                            that the query will eventually need to expand.
            **hints: catch-all kwarg field making the function's signature forward-compatible with
                     future revisions of this library that add more hints.

        Yields:
            tuples (data_context, can_coerce), containing a DataContext and a corresponding boolean
            indicating whether the DataContext's current_token can be coerced to the specified type.
            The yielded DataContext values must be yielded in the same order as they were received
            via the function's data_contexts argument.
        """

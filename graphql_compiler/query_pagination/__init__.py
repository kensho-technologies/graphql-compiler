# Copyright 2019-present Kensho Technologies, LLC.
"""Query Pagination.

Purpose
=======

Compiled GraphQL queries are sometimes too expensive to execute, in two ways:
- They return too many results: high *cardinality*.
- They require too many operations: high *execution cost*.

If these impractically-expensive queries are executed, they can overload our systems and cause the
querying system along with all dependent systems to crash.

A possible solution to this is modifying the query so that smaller, easier-to-compute chunks (i.e.
page) of results are generated, where the user defines what an acceptable page size is. For example,
with a page size of 1000 results, a query that would return 5000 results is said to return 5 pages
of results.

For better ease-of-use, the query pagination does this query modification automatically for the
user. It receives a query, and depending on how many pages of results it will generate, it may
return the query as-is or split the given query into two smaller queries. If the query was split,
two queries are generated: the next page query and the remainder query. The former returns
approximately a page of results of the original query, while the latter contains the rest of the
result data of the original query.

If the remainder query that the paginator has generated is too large as well, the user can continue
paginating their query by providing the remainder query to the paginator, and so on.

Limiting Query Result Size
==========================

Using uniformly distributed property fields, we can arbitrarily restrict the result size of a given
query. An example of such a property field for many databases is UUID, which is a property uniformly
sampled from the range of integers between 0 and 2^128-1 (inclusively).

Example:
    Consider the query:
    {
        Animal {
            name @output(out_name: "animal_name")
        }
    }
    Assume this query returns 1000 results.
    Assuming UUIDs are evenly distributed, the following query will return half of the result set
    of the previous query:
    {
        Animal {
            uuid @filter(op_name: "<", value: ["$median_uuid"])
            name @output(out_name: "animal_name")
        }
    }
    with parameter median_uuid set to '80000000-0000-0000-0000-000000000000', which is a median
    UUID value i.e. there's approximately an equal number of UUIDs below and above it.
    This is since in the old query, the range of Animal UUIDs for the query is [0, 2^128-1], while
    for the second query, the range is half that: [0, 2^127].

This can further be generalized: By controlling what we set the UUID filter's value, we can
arbitrarily restrict the size of the range of UUIDs passing through the filter, reducing the
results generated.

Note that even though this example uses UUID, this can be generalized to any uniformly distributed
vertex property.

Approach Details
================

Using the cost estimator, we can generate a rough estimate of how many result pages this query will
generate. Based on this, the paginator adds filters and generates parameters for these filters so
that the next page query and remainder query can be generated. If the query is estimated to return
more than a page of results, the paginator modifies the query and parameters so that the next page
query and remainder query can be generated.

The current approach to splitting a given query into two pairs of query and parameters will be
documented, which may be subject to change.

Consider paging the query:
{
    Animal {
        uuid @filter(op_name: ">=", value: ["$uuid_lower_bound"])
        name @output(out_name: "animal_name")
    }
}
with parameter uuid_lower_bound set to '80000000-0000-0000-0000-000000000000' (this corresponds to
the integer 2^127).
Assume the cost estimator has predicted this query will return 2 pages of results.

To limit the result size of this query, we'll need to create the next page query and remainder query
by adding filters over uniformly distributed property fields.

In this case, we'll create the next page query by adding a '<' filter over Animal uuid. So the
resulting next page query will be:
{
    Animal {
        uuid @filter(op_name: ">=", value: ["$uuid_lower_bound"])
             @filter(op_name: "<", value: ["$__paged_lower_bound_0"])
    }
}

Similarly, the remainder query will be created by adding a '>=' filter over Animal uuid. But since a
'>=' filter exists, we don't have to modify the user's query; we can paginate by just modifying the
parameter value of uuid_lower_bound.

Now that the next page query and remainder query have been generated, parameters for the '>=' and
'<' filters need to be generated such that the next page query returns only a page of results, while
the remainder query returns everything else. Note that even though uuid_lower_bound has a defined
value, we can edit the user's parameters as long as the two generated queries' union is equivalent
to the original query.

In the original query, the range of Animal UUIDs passing through the filter was [2^127, 2^128-1].
Since this query was estimated to return two pages of results, we need to divide this range into two
equal-size chunks: [2^127, 2^127+2^126) and [2^127+2^126, 2^128-1].

We can create a pair of query and parameters for the first chunk by using the next page query, and
setting the '__paged_lower_bound_0' parameter to 2^127+2^126.

The second chunk can be created using the remainder query, by restricting the 'uuid_filter'
parameter to 2^127+2^126.

So the resulting pair of query and parameters for the next page query is:
{
    Animal {
        uuid @filter(op_name: ">=", value: ["$uuid_lower_bound"])
             @filter(op_name: "<", value: ["$__paged_lower_bound_0"])
    }
}
with parameters:
    uuid_filter with value '80000000-0000-0000-0000-000000000000'
        (corresponding to integer 2^127),
    and
    __paged_lower_bound_0 with value 'c0000000-0000-0000-0000-000000000000'
        (corresponding to integer 2^127+2^126)

Meanwhile the resulting pair of query and parameters for the remainder query is:
{
    Animal {
        uuid @filter(op_name: ">=", value: ["$uuid_lower_bound"])
    }
}
with uuid_filter set to '80000000-0000-0000-0000-000000000000'
    (corresponding to integer 2^127+2^126).

TODOs
=====
    - Support for more than one pagination filter over a given query.
        - The more pagination filters available for pagination, the more accurate the page splits.
          Specifically, queries whose result set is a cartesian product of two independent sets
          (e.g. queries that return all pairs of Animals and Events) would benefit much from
          paginating over multiple filters simultaneously.
    - Support for parameter generation of non-uuid filters.
    - Better error handling.
    - Using histograms, pagination can be improved e.g. finding vertices for pagination, parameter
      generation.
    - Combine filter_selectivity_utils handling of uuid filters and parameter_generation uuid
      handling, to avoid having two chunks of code doing the exact same thing.
"""
from collections import namedtuple

from graphql.language.printer import print_ast

from graphql_compiler.ast_manipulation import safe_parse_graphql
from graphql_compiler.cost_estimation.cardinality_estimator import estimate_number_of_pages
from graphql_compiler.query_pagination.query_splitter import (
    ASTWithParameters, split_into_page_query_and_remainder_query
)


QueryStringWithParameters = namedtuple(
    'QueryStringWithParameters',
    (
        'query_string',     # str, describing a GraphQL query.
        'parameters',       # dict, parameters for executing the given query.
    ),
)


def paginate_query_ast(schema_graph, statistics, query_ast, parameters, page_size):
    """Generate a query fetching a page of results and the remainder query for a query AST.

    Since the cost estimator may underestimate or overestimate the actual number of pages, you
    should expect the actual number of results of the page query to be within two orders of
    magnitude of the estimate.

    Args:
        schema_graph: SchemaGraph instance.
        statistics: Statistics object.
        query_ast: Document, AST of the GraphQL query that is being paginated.
        parameters: dict, parameters with which query will be estimated.
        page_size: int, describes the desired number of result rows per page.

    Returns:
        tuple containing two elements:
            - ASTWithParameters namedtuple, describing a query expected to return roughly a page
              of result data of the original query.
            - ASTWithParameters namedtuple or None, describing a query that returns the rest of the
              result data of the original query. If the original query is expected to return only a
              page or less of results, then this element will have value None.

    Raises:
        ValueError if page_size is below 1.
    """
    if page_size < 1:
        raise ValueError(
            u'Could not page query {} with page size lower than 1: {}'.format(query_ast, page_size)
        )

    # Initially, assume the query does not need to be paged i.e. will return one page of results.
    next_page_ast_with_parameters = ASTWithParameters(
        query_ast,
        parameters,
    )
    remainder_ast_with_parameters = None

    # HACK(vlad): Since the current cost estimator expects GraphQL queries given as a string, we
    #             print the given AST and provide that to the cost estimator.
    graphql_query_string = print_ast(query_ast)
    num_pages = estimate_number_of_pages(
        schema_graph, statistics, graphql_query_string, parameters, page_size
    )

    if num_pages > 1:
        next_page_ast_with_parameters, remainder_ast_with_parameters = (
            split_into_page_query_and_remainder_query(
                schema_graph, statistics, query_ast, parameters, num_pages
            )
        )

    return next_page_ast_with_parameters, remainder_ast_with_parameters


def paginate_query(schema_graph, statistics, query_string, parameters, page_size):
    """Generate a query fetching a page of results and the remainder query for a query string.

    Since the cost estimator may underestimate or overestimate the actual number of pages, you
    should expect the actual number of results of the page query to be within two orders of
    magnitude of the estimate.

    Args:
        schema_graph: SchemaGraph instance.
        statistics: Statistics object.
        query_string: str, valid GraphQL query to be paginated.
        parameters: dict, parameters with which query will be estimated.
        page_size: int, describes the desired number of result rows per page.

    Returns:
        tuple containing queries for going over the original query in a paginated fashion:
            - QueryStringWithParameters namedtuple, query expected to return roughly a page of
              result data of the original query.
            - QueryStringWithParameters namedtuple or None. If the given query was estimated to
              return more than a page of results, this element is a QueryStringWithParameters
              namedtuple describing a query for the rest of the result data. Otherwise, this element
              is None.
    """
    query_ast = safe_parse_graphql(query_string)

    next_page_ast_with_parameters, remainder_ast_with_parameters = paginate_query_ast(
        schema_graph, statistics, query_ast, parameters, page_size
    )

    next_page_query_with_parameters = QueryStringWithParameters(
        print_ast(next_page_ast_with_parameters.query_ast),
        next_page_ast_with_parameters.parameters,
    )

    remainder_query_with_parameters = None
    if remainder_ast_with_parameters is not None:
        remainder_query_with_parameters = QueryStringWithParameters(
            print_ast(remainder_ast_with_parameters.query_ast),
            remainder_ast_with_parameters.parameters,
        )

    return next_page_query_with_parameters, remainder_query_with_parameters

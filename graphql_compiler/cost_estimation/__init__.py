# Copyright 2019-present Kensho Technologies, LLC.
"""Query cost estimator.

Purpose
=======

Compiled GraphQL queries are sometimes too expensive to execute, in two ways:
- They return too many results: high *cardinality*.
- They require too many operations: high *execution cost*.

If these impractically-expensive queries are executed, they can overload our systems and cause the
querying system along with all dependent systems to crash.

In order to prevent this, we use schema information and graph statistics to estimate these two costs
at the GraphQL level given a query and parameters.

A separate module could then use these estimates to inform users about potentially expensive
queries, do automatic paging of the query, or suggest additions of indexes that may improve
performance.

Estimating Cardinality
======================

The *cardinality* of a query is a rough measure of the query result size and is defined as the
unfolded number of rows returned by the query.

We estimate cardinality by estimating the number of *result sets* (sets of graph vertices that match
with scopes in the query) found as the results are *expanded* (as we step through the query and
create or discard result sets).

Example:
    Given the query
    {
        Region {
            name @output(out_name: "region")
            in_TropicalCyclone_LandfallRegion {
                name @output(out_name: "cyclone")
            }
            in_Earthquake_AffectedRegion {
                name @output(out_name: "earthquake")
            }
        }
    }
    and a graph with 6 Regions, 12 TropicalCyclones each linked to some Region, and 2 Earthquakes
    each linked to some Region, we estimate cardinality as follows:

    First, find all 6 Regions. For each Region, assuming the 12 relevant TropicalCyclones are evenly
    distributed among the 6 Regions, we expect 12/6=2 TropicalCyclones connected to each Region. So,
    after *expanding* each Region (going through each one and finding connected TropicalCyclones),
    we expect 6*2=12 *result sets* (subgraphs of a Region vertex connected to a TropicalCyclone
    vertex). Next, we expect only 2/6=.33 result sets in the *subexpansion* associated with
    Earthquakes (expanding each Region looking just for Earthquakes). So of the 12 TropicalCyclone
    result sets, we expect 12*.33=4 complete result sets for the full query (i.e. the query has
    estimated cardinality of 4).

Approach Details:
    Following this expansion model, we can think of queries as trees and find the number of expected
    result sets as we recursively traverse the tree (i.e. step through the expansion).

    Our calculation depends on two types of values:
        (1) The root result set count (e.g. the 6 Regions in the graph)
        (2) The expected result set count per parent (e.g. .33 Earthquake result sets per Region)

    Both can be calculated with graph counts for every type in the schema which must be externally
    provided. (1) can be looked up directly and (2) can be approximated as the number of
    parent-child edges divided up over parent vertices present in the graph.

    Type casting and directives can affect these calculations in many different ways. We naively
    handle type casting, as well as optional, fold, recurse, and some filter directives. Additional
    statistics can be recorded to improve the coverage and accuracy of these adjustments.

TODOs
=====
    - Estimate execution cost by augmenting the cardinality calculation.
    - Add recurse handling.
    - Add additional statistics to improve directive coverage (e.g. histograms
      to better model more filter operations).
"""

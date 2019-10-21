from sqlalchemy import select, join, MetaData, Table, Column, Integer, String
from sqlalchemy.sql import Alias
from sqlalchemy.sql.compiler import _CompileLabel
from sqlalchemy.sql.expression import BinaryExpression, BooleanClauseList
from sqlalchemy.dialects import mssql
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import func

meta = MetaData()

FoldedVertex = Table(
    'Neighborhoods', meta,
    Column('name', String, primary_key=True),
    Column('city', String)
)

NestedFoldedVertex = Table(
    'Streets', meta,
    Column('name', String, primary_key=True),
    Column('neighborhood', String)
)

FoldedVertex2 = Table(
    'Teams', meta,
    Column('name', String, primary_key=True),
    Column('city', String)
)

OuterVertex = Table(
    'Cities', meta,
    Column('name', String, primary_key=True),
    Column('state', String),
    Column('population', Integer)
)


class XMLPathBinaryExpression(BinaryExpression):
    pass


@compiles(_CompileLabel, "mssql")
def compile_xmlpath(element, compiler, **kw):
    if type(element.element) == XMLPathBinaryExpression:
        kw.update(
            within_columns_clause=False
        )
    return compiler.visit_label(element, **kw)


def agg_table(output_column, where):
    col = ('~|*' + func.REPLACE(output_column, '|', '||'))
    col = XMLPathBinaryExpression(col.left, col.right, col.operator)
    return select([col]).where(where).suffix_with("FOR XML PATH ('')")


def fold(columns, aggs):
    suffixes = [
        '_'.join(map(lambda x: x.fullname if isinstance(x, Table) else x.element._froms[0].fullname, agg_table.froms))
        + '_' + agg_table._columns_plus_names[0][1]._orig[1].clauses.clauses[0].description for agg_table in aggs]

    labels = list(map(lambda x: 'agg_table_' + x, suffixes))
    return select(columns + [func.COALESCE(func.STUFF(agg_table.as_scalar(), 1, 3, ''), '!|#null!|#').label(label) for
                             agg_table, label in zip(aggs, labels)]).alias()


def count(fold_table, aliased, join_on):
    j = fold_table
    for alias, constr in zip(aliased, join_on):
        j = join(j, alias, onclause=constr, isouter=True)
    subquery_columns = set([col for arr in list(map(lambda x: list(x.c), aliased)) for col in arr])
    l = list(filter(lambda col: col not in subquery_columns or str.startswith(col.description, 'x_count'), list(j.c)))
    l = list(map(
        lambda col: func.COALESCE(col, 0).label(col.description) if str.startswith(col.description, 'x_count') else col,
        l))
    return select(l).select_from(j).alias()


def filter_table(table, where):
    return table.select(whereclause=where).alias()


def count_table(group_by_cols):
    tablename = (group_by_cols[0].table.fullname
                 if isinstance(group_by_cols[0].table, Table)
                 else group_by_cols[0].table.original.froms[0].fullname)
    label = "x_count_" + tablename
    return select(group_by_cols + [func.COUNT().label(label)]) \
        .group_by(*group_by_cols).alias()


def get_xcount_join_preds(x, count_tbl, join_predicates, outer_tbl):
    # If OuterVertex, InnerVertex were joined on
    # OuterVertex.a = InnerVertex.b then the count tables will be joined on
    # x.a = count_tbl.b
    inner_tbl = count_tbl.original._froms[0].original._froms[0] \
        if isinstance(count_tbl.original._froms[0], Alias) \
        else count_tbl.original._froms[0]
    key = (outer_tbl, inner_tbl)

    pred = join_predicates[key]

    def xcount_substitute(column, outer, inner):
        name = column.description
        table = column.table
        if table == inner:
            return count_tbl.c[name]
        elif table == outer:
            return x.c[name]

    # We need to replace all occurrences of InnerVertex.col with count_tbl.col
    # Likewise OuterVertex.col -> x.col
    repl = BinaryExpression(xcount_substitute(pred.left, outer_tbl, inner_tbl),
                            xcount_substitute(pred.right, outer_tbl, inner_tbl),
                            pred.operator)
    return repl


def get_join_predicate(join_predicates, output_column, outer_table, filtered_outside_table=None,
                       filtered_inner_tables=None):
    key = (outer_table,
           output_column.table if not isinstance(output_column.table, Alias) else output_column.table.original.froms[0])
    pred = join_predicates[key]

    def sub_filtered_tables(column, outer, inner):
        name = column.description
        table = column.table
        if table == inner:
            return filtered_inner_tables[key[1]].c[name] if filtered_inner_tables is not None and filtered_inner_tables[key[1]] is not None else column
        elif table == outer:
            return filtered_outside_table.c[name] if filtered_outside_table is not None else column

    return BinaryExpression(sub_filtered_tables(pred.left, outer_table, key[1]),
                            sub_filtered_tables(pred.right, outer_table, key[1]),
                            pred.operator)


def find_substitute(alternative_columns, column):
    for col in alternative_columns:
        if col.description == column.description:
            return col
    return column


def get_folds(outer_table, inner_tables, outer_output_columns, inner_output_columns, join_predicates,
              group_by_cols=None, inner_filters=None, outer_filter=None, x_count_filters=None):
    filtered_inner_tables = None
    filtered_outside_table = None
    if outer_filter is not None:
        # this creates a filtered version of the outside table
        filtered_outside_table = filter_table(outer_table, outer_filter)
        # this updates the output columns requested to be those from the filtered version
        outer_output_columns = list(
            map(lambda col: find_substitute(list(filtered_outside_table.c), col), outer_output_columns))
    if inner_filters is not None:
        # filter each inner table
        filtered_inner_tables = {tbl: filter_table(tbl, inner_filters[tbl])
                                 for tbl in inner_filters}
        # updates the columns uses in the xml path subquery to be the ones from the filtered table
        inner_output_columns = list(map(lambda col: col if col.table not in filtered_inner_tables else find_substitute(
            list(filtered_inner_tables[col.table].c), col), inner_output_columns))
        # updates the columns from the count query to be the ones from the filtered table
        group_by_cols = [list(map(lambda col: col if col.table not in filtered_inner_tables else find_substitute(
            list(filtered_inner_tables[col.table].c), col), sublist)) for sublist in group_by_cols]

    # create the subqueries corresponding to the xml path bit
    # make sure to use the proper join predicates, updating them as necessary if the tables have been filtered
    aggs = [agg_table(output_column=output_col,
                      where=get_join_predicate(join_predicates, output_col, outer_table, filtered_outside_table,
                                               filtered_inner_tables)) for
            output_col in inner_output_columns]

    # this combines the output of the outer  vertex fields with the output of the
    # aggregated columns - does proper updating to ensure that filtered versions of
    # columns are used if necessary
    x = fold(outer_output_columns, aggs)

    if group_by_cols is not None:
        # create the count table and name the x_count field
        # uses the filtered columns if necessary
        count_tbls = [count_table(cols) for cols in group_by_cols]

        # left join all of the count tables onto the main table resolving the
        # correct join predicates (i.e. use the update columns if the original columns requested
        # no longer exist due to filtering)
        #
        # this query also makes sure we get only the columns from the main table and the x count columns
        x = count(x, count_tbls,
                  [get_xcount_join_preds(x, count_tbl, join_predicates, outer_table) for count_tbl in count_tbls])

    if x_count_filters is not None:
        # originally, filters for the x_count had a placeholder column
        # this is because the column being filtered on doesn't actually exist until the count() method is called
        # we need to substitute in the updated column, then join all the filters together with AND
        clauses = [item for sublist in list(
            map(lambda k: [BinaryExpression(x.c[k], pred.right, pred.operator) for pred in x_count_filters[k]],
                x_count_filters.keys())) for item in sublist]
        b = BooleanClauseList.and_(*clauses)
        # reselect from results table but with x count filter applied - widest scope possible
        x = x.select(whereclause=b)
    return x.compile(dialect=mssql.dialect(), compile_kwargs={"literal_binds": True})


if __name__ == '__main__':
    print(get_folds(outer_table=OuterVertex,
                    inner_tables=[FoldedVertex],
                    outer_output_columns=[OuterVertex.c.name],
                    inner_output_columns=[FoldedVertex.c.name],
                    join_predicates={(OuterVertex, FoldedVertex): FoldedVertex.c.city == OuterVertex.c.name},
                    # outer_filter=OuterVertex.c.population >= 60000,
                    group_by_cols=[[FoldedVertex.c.city]],
                    # x_count_filters={'x_count_Neighborhoods': [Column() > 1, Column() < 3]},
                    # Column() is a placeholder, the lefthand column always gets replaced by the column name given
                    # inner_filters={FoldedVertex: FoldedVertex.c.name.like("B%")}
                    ))

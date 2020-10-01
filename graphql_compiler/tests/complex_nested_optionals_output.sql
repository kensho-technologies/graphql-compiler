SELECT
    EXPAND($result)
LET
    $optional__0 = (
        SELECT
            Animal___1.name AS `animal_name`
        FROM (
            MATCH {{
                class: Animal,
                where: ((((in_Animal_ParentOf IS null) OR (in_Animal_ParentOf.size() = 0)) AND ((out_Animal_ParentOf IS null) OR (out_Animal_ParentOf.size() = 0)))),
                as: Animal___1
            }}
            RETURN $matches
        )
    ),
    $optional__1 = (
        SELECT
            Animal___1.name AS `animal_name`, Animal__out_Animal_ParentOf___1.name AS `parent_name`
        FROM (
            MATCH {{
                class: Animal,
                where: (((in_Animal_ParentOf IS null) OR (in_Animal_ParentOf.size() = 0))),
                as: Animal___1
            }} , {{
                class: Animal,
                as: Animal___1
            }}.out('Animal_ParentOf') {{
                class: Animal,
                where: (((out_Animal_ParentOf IS null) OR (out_Animal_ParentOf.size() = 0))),
                as: Animal__out_Animal_ParentOf___1
            }}
            RETURN $matches
        )
    ),
    $optional__2 = (
        SELECT
            Animal___1.name AS `animal_name`, Animal__in_Animal_ParentOf___1.name AS `child_name`, Animal__in_Animal_ParentOf__in_Entity_Related___1.name AS `grandchild_relation_name`, Animal__in_Animal_ParentOf__in_Entity_Related__out_Animal_OfSpecies___1.name AS `grandchild_relation_species`, Animal__out_Animal_ParentOf___1.name AS `parent_name`
        FROM (
            MATCH {{
                where: ((@this INSTANCEOF 'Animal')),
                as: Animal___1
            }}.in('Animal_ParentOf') {{
                class: Animal,
                where: (((in_Animal_ParentOf IS null) OR (in_Animal_ParentOf.size() = 0))),
                as: Animal__in_Animal_ParentOf___1
            }} , {{
                class: Animal,
                as: Animal__in_Animal_ParentOf___1
            }}.in('Entity_Related') {{
                where: ((@this INSTANCEOF 'Animal')),
                as: Animal__in_Animal_ParentOf__in_Entity_Related___1
            }}.out('Animal_OfSpecies') {{
                as: Animal__in_Animal_ParentOf__in_Entity_Related__out_Animal_OfSpecies___1
            }} , {{
                as: Animal___1
            }}.out('Animal_ParentOf') {{
                class: Animal,
                where: (((out_Animal_ParentOf IS null) OR (out_Animal_ParentOf.size() = 0))),
                as: Animal__out_Animal_ParentOf___1
            }}
            RETURN $matches
        )
    ),
    $optional__3 = (
        SELECT
            Animal___1.name AS `animal_name`, Animal__out_Animal_ParentOf__out_Animal_ParentOf___1.name AS `grandparent_name`, Animal__out_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1.name AS `grandparent_species`, Animal__out_Animal_ParentOf___1.name AS `parent_name`
        FROM (
            MATCH {{
                class: Animal,
                where: (((in_Animal_ParentOf IS null) OR (in_Animal_ParentOf.size() = 0))),
                as: Animal___1
            }} , {{
                class: Animal,
                as: Animal___1
            }}.out('Animal_ParentOf') {{
                as: Animal__out_Animal_ParentOf___1
            }}.out('Animal_ParentOf') {{
                as: Animal__out_Animal_ParentOf__out_Animal_ParentOf___1
            }}.out('Animal_OfSpecies') {{
                as: Animal__out_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1
            }}
            RETURN $matches
        )
    ),
    $optional__4 = (
        SELECT
            Animal___1.name AS `animal_name`, Animal__in_Animal_ParentOf___1.name AS `child_name`
        FROM (
            MATCH {{
                class: Animal,
                where: (((out_Animal_ParentOf IS null) OR (out_Animal_ParentOf.size() = 0))),
                as: Animal___1
            }}.in('Animal_ParentOf') {{
                class: Animal,
                where: ((((in_Animal_ParentOf IS null) OR (in_Animal_ParentOf.size() = 0)) AND ((in_Entity_Related IS null) OR (in_Entity_Related.size() = 0)))),
                as: Animal__in_Animal_ParentOf___1
            }}
            RETURN $matches
        )
    ),
    $optional__5 = (
        SELECT
            Animal___1.name AS `animal_name`, Animal__in_Animal_ParentOf___1.name AS `child_name`, Animal__out_Animal_ParentOf___1.name AS `parent_name`
        FROM (
            MATCH {{
                where: ((@this INSTANCEOF 'Animal')),
                as: Animal___1
            }}.in('Animal_ParentOf') {{
                class: Animal,
                where: ((((in_Animal_ParentOf IS null) OR (in_Animal_ParentOf.size() = 0)) AND ((in_Entity_Related IS null) OR (in_Entity_Related.size() = 0)))),
                as: Animal__in_Animal_ParentOf___1
            }} , {{
                as: Animal___1
            }}.out('Animal_ParentOf') {{
                class: Animal,
                where: (((out_Animal_ParentOf IS null) OR (out_Animal_ParentOf.size() = 0))),
                as: Animal__out_Animal_ParentOf___1
            }}
            RETURN $matches
        )
    ),
    $optional__6 = (
        SELECT
            Animal___1.name AS `animal_name`, Animal__in_Animal_ParentOf___1.name AS `child_name`, Animal__in_Animal_ParentOf__in_Animal_ParentOf___1.name AS `grandchild_name`, Animal__in_Animal_ParentOf__in_Entity_Related___1.name AS `grandchild_relation_name`, Animal__in_Animal_ParentOf__in_Entity_Related__out_Animal_OfSpecies___1.name AS `grandchild_relation_species`, Animal__in_Animal_ParentOf__in_Animal_ParentOf__out_Animal_OfSpecies___1.name AS `grandchild_species`, Animal__out_Animal_ParentOf___1.name AS `parent_name`
        FROM (
            MATCH {{
                where: ((@this INSTANCEOF 'Animal')),
                as: Animal___1
            }}.in('Animal_ParentOf') {{
                as: Animal__in_Animal_ParentOf___1
            }}.in('Animal_ParentOf') {{
                as: Animal__in_Animal_ParentOf__in_Animal_ParentOf___1
            }}.out('Animal_OfSpecies') {{
                as: Animal__in_Animal_ParentOf__in_Animal_ParentOf__out_Animal_OfSpecies___1
            }} , {{
                where: ((@this INSTANCEOF 'Animal')),
                as: Animal__in_Animal_ParentOf___1
            }}.in('Entity_Related') {{
                where: ((@this INSTANCEOF 'Animal')),
                as: Animal__in_Animal_ParentOf__in_Entity_Related___1
            }}.out('Animal_OfSpecies') {{
                as: Animal__in_Animal_ParentOf__in_Entity_Related__out_Animal_OfSpecies___1
            }} , {{
                as: Animal___1
            }}.out('Animal_ParentOf') {{
                class: Animal,
                where: (((out_Animal_ParentOf IS null) OR (out_Animal_ParentOf.size() = 0))),
                as: Animal__out_Animal_ParentOf___1
            }}
            RETURN $matches
        )
    ),
    $optional__7 = (
        SELECT
            Animal___1.name AS `animal_name`, Animal__in_Animal_ParentOf___1.name AS `child_name`, Animal__in_Animal_ParentOf__in_Entity_Related___1.name AS `grandchild_relation_name`, Animal__in_Animal_ParentOf__in_Entity_Related__out_Animal_OfSpecies___1.name AS `grandchild_relation_species`, Animal__out_Animal_ParentOf__out_Animal_ParentOf___1.name AS `grandparent_name`, Animal__out_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1.name AS `grandparent_species`, Animal__out_Animal_ParentOf___1.name AS `parent_name`
        FROM (
            MATCH {{
                where: ((@this INSTANCEOF 'Animal')),
                as: Animal___1
            }}.in('Animal_ParentOf') {{
                class: Animal,
                where: (((in_Animal_ParentOf IS null) OR (in_Animal_ParentOf.size() = 0))),
                as: Animal__in_Animal_ParentOf___1
            }} , {{
                class: Animal,
                as: Animal__in_Animal_ParentOf___1
            }}.in('Entity_Related') {{
                where: ((@this INSTANCEOF 'Animal')),
                as: Animal__in_Animal_ParentOf__in_Entity_Related___1
            }}.out('Animal_OfSpecies') {{
                as: Animal__in_Animal_ParentOf__in_Entity_Related__out_Animal_OfSpecies___1
            }} , {{
                as: Animal___1
            }}.out('Animal_ParentOf') {{
                as: Animal__out_Animal_ParentOf___1
            }}.out('Animal_ParentOf') {{
                as: Animal__out_Animal_ParentOf__out_Animal_ParentOf___1
            }}.out('Animal_OfSpecies') {{
                as: Animal__out_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1
            }}
            RETURN $matches
        )
    ),
    $optional__8 = (
        SELECT
            Animal___1.name AS `animal_name`, Animal__in_Animal_ParentOf___1.name AS `child_name`, Animal__in_Animal_ParentOf__in_Animal_ParentOf___1.name AS `grandchild_name`, Animal__in_Animal_ParentOf__in_Animal_ParentOf__out_Animal_OfSpecies___1.name AS `grandchild_species`, Animal__out_Animal_ParentOf___1.name AS `parent_name`
        FROM (
            MATCH {{
                where: ((@this INSTANCEOF 'Animal')),
                as: Animal___1
            }}.in('Animal_ParentOf') {{
                class: Animal,
                where: (((in_Entity_Related IS null) OR (in_Entity_Related.size() = 0))),
                as: Animal__in_Animal_ParentOf___1
            }}.in('Animal_ParentOf') {{
                as: Animal__in_Animal_ParentOf__in_Animal_ParentOf___1
            }}.out('Animal_OfSpecies') {{
                as: Animal__in_Animal_ParentOf__in_Animal_ParentOf__out_Animal_OfSpecies___1
            }} , {{
                as: Animal___1
            }}.out('Animal_ParentOf') {{
                class: Animal,
                where: (((out_Animal_ParentOf IS null) OR (out_Animal_ParentOf.size() = 0))),
                as: Animal__out_Animal_ParentOf___1
            }}
            RETURN $matches
        )
    ),
    $optional__9 = (
        SELECT
            Animal___1.name AS `animal_name`, Animal__in_Animal_ParentOf___1.name AS `child_name`, Animal__out_Animal_ParentOf__out_Animal_ParentOf___1.name AS `grandparent_name`, Animal__out_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1.name AS `grandparent_species`, Animal__out_Animal_ParentOf___1.name AS `parent_name`
        FROM (
            MATCH {{
                where: ((@this INSTANCEOF 'Animal')),
                as: Animal___1
            }}.in('Animal_ParentOf') {{
                class: Animal,
                where: ((((in_Animal_ParentOf IS null) OR (in_Animal_ParentOf.size() = 0)) AND ((in_Entity_Related IS null) OR (in_Entity_Related.size() = 0)))),
                as: Animal__in_Animal_ParentOf___1
            }} , {{
                as: Animal___1
            }}.out('Animal_ParentOf') {{
                as: Animal__out_Animal_ParentOf___1
            }}.out('Animal_ParentOf') {{
                as: Animal__out_Animal_ParentOf__out_Animal_ParentOf___1
            }}.out('Animal_OfSpecies') {{
                as: Animal__out_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1
            }}
            RETURN $matches
        )
    ),
    $optional__10 = (
        SELECT
            Animal___1.name AS `animal_name`, Animal__in_Animal_ParentOf___1.name AS `child_name`, Animal__in_Animal_ParentOf__in_Animal_ParentOf___1.name AS `grandchild_name`, Animal__in_Animal_ParentOf__in_Animal_ParentOf__out_Animal_OfSpecies___1.name AS `grandchild_species`, Animal__out_Animal_ParentOf__out_Animal_ParentOf___1.name AS `grandparent_name`, Animal__out_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1.name AS `grandparent_species`, Animal__out_Animal_ParentOf___1.name AS `parent_name`
        FROM (
            MATCH {{
                where: ((@this INSTANCEOF 'Animal')),
                as: Animal___1
            }}.in('Animal_ParentOf') {{
                class: Animal,
                where: (((in_Entity_Related IS null) OR (in_Entity_Related.size() = 0))),
                as: Animal__in_Animal_ParentOf___1
            }}.in('Animal_ParentOf') {{
                as: Animal__in_Animal_ParentOf__in_Animal_ParentOf___1
            }}.out('Animal_OfSpecies') {{
                as: Animal__in_Animal_ParentOf__in_Animal_ParentOf__out_Animal_OfSpecies___1
            }} , {{
                as: Animal___1
            }}.out('Animal_ParentOf') {{
                as: Animal__out_Animal_ParentOf___1
            }}.out('Animal_ParentOf') {{
                as: Animal__out_Animal_ParentOf__out_Animal_ParentOf___1
            }}.out('Animal_OfSpecies') {{
                as: Animal__out_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1
            }}
            RETURN $matches
        )
    ),
    $optional__11 = (
        SELECT
            Animal___1.name AS `animal_name`, Animal__in_Animal_ParentOf___1.name AS `child_name`, Animal__in_Animal_ParentOf__in_Entity_Related___1.name AS `grandchild_relation_name`, Animal__in_Animal_ParentOf__in_Entity_Related__out_Animal_OfSpecies___1.name AS `grandchild_relation_species`
        FROM (
            MATCH {{
                class: Animal,
                where: (((out_Animal_ParentOf IS null) OR (out_Animal_ParentOf.size() = 0))),
                as: Animal___1
            }}.in('Animal_ParentOf') {{
                class: Animal,
                where: (((in_Animal_ParentOf IS null) OR (in_Animal_ParentOf.size() = 0))),
                as: Animal__in_Animal_ParentOf___1
            }} , {{
                class: Animal,
                as: Animal__in_Animal_ParentOf___1
            }}.in('Entity_Related') {{
                where: ((@this INSTANCEOF 'Animal')),
                as: Animal__in_Animal_ParentOf__in_Entity_Related___1
            }}.out('Animal_OfSpecies') {{
                as: Animal__in_Animal_ParentOf__in_Entity_Related__out_Animal_OfSpecies___1
            }}
            RETURN $matches
        )
    ),
    $optional__12 = (
        SELECT
            Animal___1.name AS `animal_name`, Animal__in_Animal_ParentOf___1.name AS `child_name`, Animal__in_Animal_ParentOf__in_Animal_ParentOf___1.name AS `grandchild_name`, Animal__in_Animal_ParentOf__in_Animal_ParentOf__out_Animal_OfSpecies___1.name AS `grandchild_species`
        FROM (
            MATCH {{
                class: Animal,
                where: (((out_Animal_ParentOf IS null) OR (out_Animal_ParentOf.size() = 0))),
                as: Animal___1
            }}.in('Animal_ParentOf') {{
                class: Animal,
                where: (((in_Entity_Related IS null) OR (in_Entity_Related.size() = 0))),
                as: Animal__in_Animal_ParentOf___1
            }}.in('Animal_ParentOf') {{
                as: Animal__in_Animal_ParentOf__in_Animal_ParentOf___1
            }}.out('Animal_OfSpecies') {{
                as: Animal__in_Animal_ParentOf__in_Animal_ParentOf__out_Animal_OfSpecies___1
            }}
            RETURN $matches
        )
    ),
    $optional__13 = (
        SELECT
            Animal___1.name AS `animal_name`, Animal__in_Animal_ParentOf___1.name AS `child_name`, Animal__in_Animal_ParentOf__in_Animal_ParentOf___1.name AS `grandchild_name`, Animal__in_Animal_ParentOf__in_Entity_Related___1.name AS `grandchild_relation_name`, Animal__in_Animal_ParentOf__in_Entity_Related__out_Animal_OfSpecies___1.name AS `grandchild_relation_species`, Animal__in_Animal_ParentOf__in_Animal_ParentOf__out_Animal_OfSpecies___1.name AS `grandchild_species`
        FROM (
            MATCH {{
                class: Animal,
                where: (((out_Animal_ParentOf IS null) OR (out_Animal_ParentOf.size() = 0))),
                as: Animal___1
            }}.in('Animal_ParentOf') {{
                as: Animal__in_Animal_ParentOf___1
            }}.in('Animal_ParentOf') {{
                as: Animal__in_Animal_ParentOf__in_Animal_ParentOf___1
            }}.out('Animal_OfSpecies') {{
                as: Animal__in_Animal_ParentOf__in_Animal_ParentOf__out_Animal_OfSpecies___1
            }} , {{
                where: ((@this INSTANCEOF 'Animal')),
                as: Animal__in_Animal_ParentOf___1
            }}.in('Entity_Related') {{
                where: ((@this INSTANCEOF 'Animal')),
                as: Animal__in_Animal_ParentOf__in_Entity_Related___1
            }}.out('Animal_OfSpecies') {{
                as: Animal__in_Animal_ParentOf__in_Entity_Related__out_Animal_OfSpecies___1
            }}
            RETURN $matches
        )
    ),
    $optional__14 = (
        SELECT
            Animal___1.name AS `animal_name`, Animal__in_Animal_ParentOf___1.name AS `child_name`, Animal__in_Animal_ParentOf__in_Animal_ParentOf___1.name AS `grandchild_name`, Animal__in_Animal_ParentOf__in_Entity_Related___1.name AS `grandchild_relation_name`, Animal__in_Animal_ParentOf__in_Entity_Related__out_Animal_OfSpecies___1.name AS `grandchild_relation_species`, Animal__in_Animal_ParentOf__in_Animal_ParentOf__out_Animal_OfSpecies___1.name AS `grandchild_species`, Animal__out_Animal_ParentOf__out_Animal_ParentOf___1.name AS `grandparent_name`, Animal__out_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1.name AS `grandparent_species`, Animal__out_Animal_ParentOf___1.name AS `parent_name`
        FROM (
            MATCH {{
                class: Animal,
                as: Animal___1
            }}.in('Animal_ParentOf') {{
                class: Animal,
                as: Animal__in_Animal_ParentOf___1
            }}.in('Animal_ParentOf') {{
                class: Animal,
                as: Animal__in_Animal_ParentOf__in_Animal_ParentOf___1
            }}.out('Animal_OfSpecies') {{
                class: Species,
                as: Animal__in_Animal_ParentOf__in_Animal_ParentOf__out_Animal_OfSpecies___1
            }} , {{
                class: Animal,
                as: Animal__in_Animal_ParentOf___1
            }}.in('Entity_Related') {{
                class: Animal,
                as: Animal__in_Animal_ParentOf__in_Entity_Related___1
            }}.out('Animal_OfSpecies') {{
                class: Species,
                as: Animal__in_Animal_ParentOf__in_Entity_Related__out_Animal_OfSpecies___1
            }} , {{
                class: Animal,
                as: Animal___1
            }}.out('Animal_ParentOf') {{
                class: Animal,
                as: Animal__out_Animal_ParentOf___1
            }}.out('Animal_ParentOf') {{
                class: Animal,
                as: Animal__out_Animal_ParentOf__out_Animal_ParentOf___1
            }}.out('Animal_OfSpecies') {{
                class: Species,
                as: Animal__out_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1
            }}
            RETURN $matches
        )
    ),
    $result = UNIONALL($optional__0,
                       $optional__1,
                       $optional__2,
                       $optional__3,
                       $optional__4,
                       $optional__5,
                       $optional__6,
                       $optional__7,
                       $optional__8,
                       $optional__9,
                       $optional__10,
                       $optional__11,
                       $optional__12,
                       $optional__13,
                       $optional__14)

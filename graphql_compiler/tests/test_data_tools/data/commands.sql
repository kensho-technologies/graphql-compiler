# Auto-generated output from `graphql_compiler/scripts/generate_test_sql/__init__.py`.
# Do not edit directly!
# Generated on 2018-06-21T18:17:34.213827 from git revision 2c2c5197776703d619661ed6e848e6af5a11fd8e.

create vertex Species set name = 'Nazgul', uuid = '302934307671667531413257853548643485645'
create vertex Species set name = 'Pteranodon', uuid = '173977771337128709904731325155688394548'
create vertex Species set name = 'Dragon', uuid = '282384309546404946677649712557383598968'
create vertex Species set name = 'Hippogriff', uuid = '47392387440050222334387056025351624211'
create vertex Animal set name = 'Nazgul__0', uuid = '306991165517665256324778893243503225633'
create vertex Animal set name = 'Nazgul__1', uuid = '177407450100309800300969634957035917318'
create vertex Animal set name = 'Nazgul__2', uuid = '285868227991728515823364176561995005096'
create vertex Animal set name = 'Nazgul__3', uuid = '329236887588495498680613646289592227374'
create vertex Animal set name = 'Nazgul__4', uuid = '31039180739522226500264777420862466941'
create vertex Animal set name = 'Nazgul__(023)', uuid = '240430390928747079917280759511220198891'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(023)') to (select from Animal where name = 'Nazgul__0')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(023)') to (select from Animal where name = 'Nazgul__2')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(023)') to (select from Animal where name = 'Nazgul__3')
create vertex Animal set name = 'Nazgul__(124)', uuid = '82384795729952134079151163904035971493'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(124)') to (select from Animal where name = 'Nazgul__1')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(124)') to (select from Animal where name = 'Nazgul__2')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(124)') to (select from Animal where name = 'Nazgul__4')
create vertex Animal set name = 'Nazgul__((023)(124)1)', uuid = '223449612386921660899567306932374004060'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((023)(124)1)') to (select from Animal where name = 'Nazgul__(023)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((023)(124)1)') to (select from Animal where name = 'Nazgul__(124)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((023)(124)1)') to (select from Animal where name = 'Nazgul__1')
create vertex Animal set name = 'Nazgul__(((023)(124)1)(124)0)', uuid = '298349497532394848273075385118073346682'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((023)(124)1)(124)0)') to (select from Animal where name = 'Nazgul__((023)(124)1)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((023)(124)1)(124)0)') to (select from Animal where name = 'Nazgul__(124)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((023)(124)1)(124)0)') to (select from Animal where name = 'Nazgul__0')
create vertex Animal set name = 'Nazgul__((023)01)', uuid = '232582448321334961524380570887193043323'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((023)01)') to (select from Animal where name = 'Nazgul__(023)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((023)01)') to (select from Animal where name = 'Nazgul__0')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((023)01)') to (select from Animal where name = 'Nazgul__1')
create vertex Animal set name = 'Nazgul__((((023)(124)1)(124)0)34)', uuid = '197259991110368393269222042990062892176'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((023)(124)1)(124)0)34)') to (select from Animal where name = 'Nazgul__(((023)(124)1)(124)0)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((023)(124)1)(124)0)34)') to (select from Animal where name = 'Nazgul__3')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((023)(124)1)(124)0)34)') to (select from Animal where name = 'Nazgul__4')
create vertex Animal set name = 'Nazgul__(((((023)(124)1)(124)0)34)((023)(124)1)(023))', uuid = '39251484984065603481696118144125789552'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((023)(124)1)(124)0)34)((023)(124)1)(023))') to (select from Animal where name = 'Nazgul__((((023)(124)1)(124)0)34)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((023)(124)1)(124)0)34)((023)(124)1)(023))') to (select from Animal where name = 'Nazgul__((023)(124)1)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((023)(124)1)(124)0)34)((023)(124)1)(023))') to (select from Animal where name = 'Nazgul__(023)')
create vertex Animal set name = 'Nazgul__(((((023)(124)1)(124)0)34)((023)01)(023))', uuid = '75018833995206381512027585611313626751'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((023)(124)1)(124)0)34)((023)01)(023))') to (select from Animal where name = 'Nazgul__((((023)(124)1)(124)0)34)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((023)(124)1)(124)0)34)((023)01)(023))') to (select from Animal where name = 'Nazgul__((023)01)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((023)(124)1)(124)0)34)((023)01)(023))') to (select from Animal where name = 'Nazgul__(023)')
create vertex Animal set name = 'Nazgul__((((((023)(124)1)(124)0)34)((023)01)(023))(023)2)', uuid = '74444784996223432665018199630880948218'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((((023)(124)1)(124)0)34)((023)01)(023))(023)2)') to (select from Animal where name = 'Nazgul__(((((023)(124)1)(124)0)34)((023)01)(023))')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((((023)(124)1)(124)0)34)((023)01)(023))(023)2)') to (select from Animal where name = 'Nazgul__(023)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((((((023)(124)1)(124)0)34)((023)01)(023))(023)2)') to (select from Animal where name = 'Nazgul__2')
create vertex Animal set name = 'Nazgul__(((((((023)(124)1)(124)0)34)((023)01)(023))(023)2)((((023)(124)1)(124)0)34)((023)01))', uuid = '216079273138807230312886268899032659455'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((((023)(124)1)(124)0)34)((023)01)(023))(023)2)((((023)(124)1)(124)0)34)((023)01))') to (select from Animal where name = 'Nazgul__((((((023)(124)1)(124)0)34)((023)01)(023))(023)2)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((((023)(124)1)(124)0)34)((023)01)(023))(023)2)((((023)(124)1)(124)0)34)((023)01))') to (select from Animal where name = 'Nazgul__((((023)(124)1)(124)0)34)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((((((023)(124)1)(124)0)34)((023)01)(023))(023)2)((((023)(124)1)(124)0)34)((023)01))') to (select from Animal where name = 'Nazgul__((023)01)')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__0') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__1') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__2') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__3') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__4') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(023)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(124)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((023)(124)1)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((023)(124)1)(124)0)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((023)01)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((((023)(124)1)(124)0)34)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((((023)(124)1)(124)0)34)((023)(124)1)(023))') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((((023)(124)1)(124)0)34)((023)01)(023))') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((((((023)(124)1)(124)0)34)((023)01)(023))(023)2)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((((((023)(124)1)(124)0)34)((023)01)(023))(023)2)((((023)(124)1)(124)0)34)((023)01))') to (select from Species where name = 'Nazgul')
create vertex Animal set name = 'Pteranodon__0', uuid = '40730259540489196208158731565201424000'
create vertex Animal set name = 'Pteranodon__1', uuid = '333652526538723743061329250892865511857'
create vertex Animal set name = 'Pteranodon__2', uuid = '42159340702229845245076644291529360381'
create vertex Animal set name = 'Pteranodon__3', uuid = '23821229388316841745989034761007131421'
create vertex Animal set name = 'Pteranodon__4', uuid = '119198861163581164906005274270020451471'
create vertex Animal set name = 'Pteranodon__(012)', uuid = '88518758963465233786882873227239815809'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(012)') to (select from Animal where name = 'Pteranodon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(012)') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(012)') to (select from Animal where name = 'Pteranodon__2')
create vertex Animal set name = 'Pteranodon__((012)13)', uuid = '85304482102252033124956228215790490233'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((012)13)') to (select from Animal where name = 'Pteranodon__(012)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((012)13)') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((012)13)') to (select from Animal where name = 'Pteranodon__3')
create vertex Animal set name = 'Pteranodon__(134)', uuid = '312212858156261122236980165259006402397'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(134)') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(134)') to (select from Animal where name = 'Pteranodon__3')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(134)') to (select from Animal where name = 'Pteranodon__4')
create vertex Animal set name = 'Pteranodon__((012)(134)3)', uuid = '235074803977113312339635252068718813059'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((012)(134)3)') to (select from Animal where name = 'Pteranodon__(012)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((012)(134)3)') to (select from Animal where name = 'Pteranodon__(134)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((012)(134)3)') to (select from Animal where name = 'Pteranodon__3')
create vertex Animal set name = 'Pteranodon__((134)12)', uuid = '95579589155068790053592867250746960154'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((134)12)') to (select from Animal where name = 'Pteranodon__(134)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((134)12)') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((134)12)') to (select from Animal where name = 'Pteranodon__2')
create vertex Animal set name = 'Pteranodon__(((134)12)(012)4)', uuid = '105588794939571557635637350535683564644'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((134)12)(012)4)') to (select from Animal where name = 'Pteranodon__((134)12)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((134)12)(012)4)') to (select from Animal where name = 'Pteranodon__(012)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((134)12)(012)4)') to (select from Animal where name = 'Pteranodon__4')
create vertex Animal set name = 'Pteranodon__(((012)13)01)', uuid = '113791000114287909541484337047650316681'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((012)13)01)') to (select from Animal where name = 'Pteranodon__((012)13)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((012)13)01)') to (select from Animal where name = 'Pteranodon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((012)13)01)') to (select from Animal where name = 'Pteranodon__1')
create vertex Animal set name = 'Pteranodon__((((012)13)01)(134)3)', uuid = '151545497319785852152226649664896723828'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((012)13)01)(134)3)') to (select from Animal where name = 'Pteranodon__(((012)13)01)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((012)13)01)(134)3)') to (select from Animal where name = 'Pteranodon__(134)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((012)13)01)(134)3)') to (select from Animal where name = 'Pteranodon__3')
create vertex Animal set name = 'Pteranodon__((((012)13)01)24)', uuid = '332990711735135573412736981133019448118'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((012)13)01)24)') to (select from Animal where name = 'Pteranodon__(((012)13)01)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((012)13)01)24)') to (select from Animal where name = 'Pteranodon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((((012)13)01)24)') to (select from Animal where name = 'Pteranodon__4')
create vertex Animal set name = 'Pteranodon__(((((012)13)01)24)(((012)13)01)2)', uuid = '72658678951967615894076332463206976850'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((012)13)01)24)(((012)13)01)2)') to (select from Animal where name = 'Pteranodon__((((012)13)01)24)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((012)13)01)24)(((012)13)01)2)') to (select from Animal where name = 'Pteranodon__(((012)13)01)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((((012)13)01)24)(((012)13)01)2)') to (select from Animal where name = 'Pteranodon__2')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__0') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__1') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__2') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__3') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__4') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(012)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((012)13)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(134)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((012)(134)3)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((134)12)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((134)12)(012)4)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((012)13)01)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((((012)13)01)(134)3)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((((012)13)01)24)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((((012)13)01)24)(((012)13)01)2)') to (select from Species where name = 'Pteranodon')
create vertex Animal set name = 'Dragon__0', uuid = '33274288505145101722666309307345058635'
create vertex Animal set name = 'Dragon__1', uuid = '332971465871975396122702430521229255503'
create vertex Animal set name = 'Dragon__2', uuid = '314002267908019758727962054012602511643'
create vertex Animal set name = 'Dragon__3', uuid = '6320516259841239882886964618275152777'
create vertex Animal set name = 'Dragon__4', uuid = '223008085850302546354048361968188875982'
create vertex Animal set name = 'Dragon__(134)', uuid = '70725684597098659197903330403631285778'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(134)') to (select from Animal where name = 'Dragon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(134)') to (select from Animal where name = 'Dragon__3')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(134)') to (select from Animal where name = 'Dragon__4')
create vertex Animal set name = 'Dragon__(024)', uuid = '113452994992046650228400831372121467436'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(024)') to (select from Animal where name = 'Dragon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(024)') to (select from Animal where name = 'Dragon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(024)') to (select from Animal where name = 'Dragon__4')
create vertex Animal set name = 'Dragon__((024)02)', uuid = '12136330895497172120812557269818929532'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)02)') to (select from Animal where name = 'Dragon__(024)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)02)') to (select from Animal where name = 'Dragon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)02)') to (select from Animal where name = 'Dragon__2')
create vertex Animal set name = 'Dragon__((024)14)', uuid = '122810156710647467147390610136102778982'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)14)') to (select from Animal where name = 'Dragon__(024)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)14)') to (select from Animal where name = 'Dragon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)14)') to (select from Animal where name = 'Dragon__4')
create vertex Animal set name = 'Dragon__(((024)02)((024)14)2)', uuid = '36972161166674645164542070870192549628'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((024)02)((024)14)2)') to (select from Animal where name = 'Dragon__((024)02)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((024)02)((024)14)2)') to (select from Animal where name = 'Dragon__((024)14)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((024)02)((024)14)2)') to (select from Animal where name = 'Dragon__2')
create vertex Animal set name = 'Dragon__((((024)02)((024)14)2)((024)02)((024)14))', uuid = '102732308339781359664852280308222625683'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((024)02)((024)14)2)((024)02)((024)14))') to (select from Animal where name = 'Dragon__(((024)02)((024)14)2)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((024)02)((024)14)2)((024)02)((024)14))') to (select from Animal where name = 'Dragon__((024)02)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((024)02)((024)14)2)((024)02)((024)14))') to (select from Animal where name = 'Dragon__((024)14)')
create vertex Animal set name = 'Dragon__(((((024)02)((024)14)2)((024)02)((024)14))(((024)02)((024)14)2)2)', uuid = '75222385805444133457056383783440017313'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((024)02)((024)14)2)((024)02)((024)14))(((024)02)((024)14)2)2)') to (select from Animal where name = 'Dragon__((((024)02)((024)14)2)((024)02)((024)14))')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((024)02)((024)14)2)((024)02)((024)14))(((024)02)((024)14)2)2)') to (select from Animal where name = 'Dragon__(((024)02)((024)14)2)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((024)02)((024)14)2)((024)02)((024)14))(((024)02)((024)14)2)2)') to (select from Animal where name = 'Dragon__2')
create vertex Animal set name = 'Dragon__((024)01)', uuid = '98620909852468031314649474004126046483'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)01)') to (select from Animal where name = 'Dragon__(024)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)01)') to (select from Animal where name = 'Dragon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((024)01)') to (select from Animal where name = 'Dragon__1')
create vertex Animal set name = 'Dragon__(((((024)02)((024)14)2)((024)02)((024)14))(((024)02)((024)14)2)((024)02))', uuid = '125336699379883786541305714451008056737'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((024)02)((024)14)2)((024)02)((024)14))(((024)02)((024)14)2)((024)02))') to (select from Animal where name = 'Dragon__((((024)02)((024)14)2)((024)02)((024)14))')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((024)02)((024)14)2)((024)02)((024)14))(((024)02)((024)14)2)((024)02))') to (select from Animal where name = 'Dragon__(((024)02)((024)14)2)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(((((024)02)((024)14)2)((024)02)((024)14))(((024)02)((024)14)2)((024)02))') to (select from Animal where name = 'Dragon__((024)02)')
create vertex Animal set name = 'Dragon__((((024)02)((024)14)2)24)', uuid = '39136692071535542773957910077223764035'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((024)02)((024)14)2)24)') to (select from Animal where name = 'Dragon__(((024)02)((024)14)2)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((024)02)((024)14)2)24)') to (select from Animal where name = 'Dragon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((((024)02)((024)14)2)24)') to (select from Animal where name = 'Dragon__4')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__0') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__1') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__2') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__3') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__4') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(134)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(024)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((024)02)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((024)14)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((024)02)((024)14)2)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((((024)02)((024)14)2)((024)02)((024)14))') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((((024)02)((024)14)2)((024)02)((024)14))(((024)02)((024)14)2)2)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((024)01)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(((((024)02)((024)14)2)((024)02)((024)14))(((024)02)((024)14)2)((024)02))') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((((024)02)((024)14)2)24)') to (select from Species where name = 'Dragon')
create vertex Animal set name = 'Hippogriff__0', uuid = '238879635489108752839894880992323523478'
create vertex Animal set name = 'Hippogriff__1', uuid = '135416594372412587913892515382644822466'
create vertex Animal set name = 'Hippogriff__2', uuid = '49801853253149419652818548584802981208'
create vertex Animal set name = 'Hippogriff__3', uuid = '191886628802280315796589948786413219417'
create vertex Animal set name = 'Hippogriff__4', uuid = '302096521205533083353824497588673637423'
create vertex Animal set name = 'Hippogriff__(234)', uuid = '272207460175107021593835217172712599152'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(234)') to (select from Animal where name = 'Hippogriff__2')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(234)') to (select from Animal where name = 'Hippogriff__3')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(234)') to (select from Animal where name = 'Hippogriff__4')
create vertex Animal set name = 'Hippogriff__((234)04)', uuid = '102237256870961124648069176881592633999'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((234)04)') to (select from Animal where name = 'Hippogriff__(234)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((234)04)') to (select from Animal where name = 'Hippogriff__0')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((234)04)') to (select from Animal where name = 'Hippogriff__4')
create vertex Animal set name = 'Hippogriff__(((234)04)23)', uuid = '170967593054731394486053405058091580985'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((234)04)23)') to (select from Animal where name = 'Hippogriff__((234)04)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((234)04)23)') to (select from Animal where name = 'Hippogriff__2')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((234)04)23)') to (select from Animal where name = 'Hippogriff__3')
create vertex Animal set name = 'Hippogriff__((234)14)', uuid = '70133840206802028380130434920676220376'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((234)14)') to (select from Animal where name = 'Hippogriff__(234)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((234)14)') to (select from Animal where name = 'Hippogriff__1')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((234)14)') to (select from Animal where name = 'Hippogriff__4')
create vertex Animal set name = 'Hippogriff__((((234)04)23)((234)04)((234)14))', uuid = '22329615990233100392781078963506970248'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((234)04)23)((234)04)((234)14))') to (select from Animal where name = 'Hippogriff__(((234)04)23)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((234)04)23)((234)04)((234)14))') to (select from Animal where name = 'Hippogriff__((234)04)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((234)04)23)((234)04)((234)14))') to (select from Animal where name = 'Hippogriff__((234)14)')
create vertex Animal set name = 'Hippogriff__(((((234)04)23)((234)04)((234)14))((234)04)4)', uuid = '21185559346863190656263171390140074675'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((234)04)23)((234)04)((234)14))((234)04)4)') to (select from Animal where name = 'Hippogriff__((((234)04)23)((234)04)((234)14))')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((234)04)23)((234)04)((234)14))((234)04)4)') to (select from Animal where name = 'Hippogriff__((234)04)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((234)04)23)((234)04)((234)14))((234)04)4)') to (select from Animal where name = 'Hippogriff__4')
create vertex Animal set name = 'Hippogriff__((((((234)04)23)((234)04)((234)14))((234)04)4)23)', uuid = '113662699305970163063171460682846478106'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((234)04)23)((234)04)((234)14))((234)04)4)23)') to (select from Animal where name = 'Hippogriff__(((((234)04)23)((234)04)((234)14))((234)04)4)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((234)04)23)((234)04)((234)14))((234)04)4)23)') to (select from Animal where name = 'Hippogriff__2')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((((234)04)23)((234)04)((234)14))((234)04)4)23)') to (select from Animal where name = 'Hippogriff__3')
create vertex Animal set name = 'Hippogriff__((((234)04)23)((234)04)0)', uuid = '237754066481530140710275939781752499854'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((234)04)23)((234)04)0)') to (select from Animal where name = 'Hippogriff__(((234)04)23)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((234)04)23)((234)04)0)') to (select from Animal where name = 'Hippogriff__((234)04)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((234)04)23)((234)04)0)') to (select from Animal where name = 'Hippogriff__0')
create vertex Animal set name = 'Hippogriff__(((((234)04)23)((234)04)0)((234)04)(234))', uuid = '131581408829052556530741761927364578030'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((234)04)23)((234)04)0)((234)04)(234))') to (select from Animal where name = 'Hippogriff__((((234)04)23)((234)04)0)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((234)04)23)((234)04)0)((234)04)(234))') to (select from Animal where name = 'Hippogriff__((234)04)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((((234)04)23)((234)04)0)((234)04)(234))') to (select from Animal where name = 'Hippogriff__(234)')
create vertex Animal set name = 'Hippogriff__((((234)04)23)01)', uuid = '110221322639271469416611444097263989851'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((234)04)23)01)') to (select from Animal where name = 'Hippogriff__(((234)04)23)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((234)04)23)01)') to (select from Animal where name = 'Hippogriff__0')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((((234)04)23)01)') to (select from Animal where name = 'Hippogriff__1')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__0') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__1') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__2') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__3') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__4') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(234)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((234)04)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((234)04)23)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((234)14)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((((234)04)23)((234)04)((234)14))') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((((234)04)23)((234)04)((234)14))((234)04)4)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((((((234)04)23)((234)04)((234)14))((234)04)4)23)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((((234)04)23)((234)04)0)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((((234)04)23)((234)04)0)((234)04)(234))') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((((234)04)23)01)') to (select from Species where name = 'Hippogriff')

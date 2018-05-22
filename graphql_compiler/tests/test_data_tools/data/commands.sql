create vertex Species set name = 'Nazgul', uuid = '87425473-4595-2762-9989-378641469948'
create vertex Species set name = 'Pteranodon', uuid = '28507386-0482-3815-2984-035915758596'
create vertex Species set name = 'Dragon', uuid = '54535211-6640-7898-8953-728885954699'
create vertex Species set name = 'Hippogriff', uuid = '70646827-1273-8116-0595-606653390091'
create vertex Animal set name = 'Nazgul__0', uuid = '12890412-2631-5019-1378-916906832541'
create vertex Animal set name = 'Nazgul__1', uuid = '44553382-5073-0229-3239-667346013263'
create vertex Animal set name = 'Nazgul__2', uuid = '85447460-4215-4578-4348-881960794632'
create vertex Animal set name = 'Nazgul__3', uuid = '70850168-2918-3024-7815-638200659990'
create vertex Animal set name = 'Nazgul__4', uuid = '77679635-2501-3773-6019-235242015043'
create vertex Animal set name = 'Nazgul__(204)', uuid = '48934643-7896-3960-0700-354456439274'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(204)') to (select from Animal where name = 'Nazgul__2')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(204)') to (select from Animal where name = 'Nazgul__0')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(204)') to (select from Animal where name = 'Nazgul__4')
create vertex Animal set name = 'Nazgul__(203)', uuid = '79461320-9211-3519-9146-849344626239'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(203)') to (select from Animal where name = 'Nazgul__2')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(203)') to (select from Animal where name = 'Nazgul__0')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(203)') to (select from Animal where name = 'Nazgul__3')
create vertex Animal set name = 'Nazgul__((203)40)', uuid = '12785780-0802-0083-1169-595568797925'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((203)40)') to (select from Animal where name = 'Nazgul__(203)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((203)40)') to (select from Animal where name = 'Nazgul__4')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__((203)40)') to (select from Animal where name = 'Nazgul__0')
create vertex Animal set name = 'Nazgul__(4(204)2)', uuid = '73587601-5208-9348-0612-800448761946'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(4(204)2)') to (select from Animal where name = 'Nazgul__4')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(4(204)2)') to (select from Animal where name = 'Nazgul__(204)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(4(204)2)') to (select from Animal where name = 'Nazgul__2')
create vertex Animal set name = 'Nazgul__(30(4(204)2))', uuid = '10661533-7486-4631-6671-979868571747'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(30(4(204)2))') to (select from Animal where name = 'Nazgul__3')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(30(4(204)2))') to (select from Animal where name = 'Nazgul__0')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(30(4(204)2))') to (select from Animal where name = 'Nazgul__(4(204)2)')
create vertex Animal set name = 'Nazgul__(4((203)40)0)', uuid = '09499652-0887-6431-4599-407704609970'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(4((203)40)0)') to (select from Animal where name = 'Nazgul__4')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(4((203)40)0)') to (select from Animal where name = 'Nazgul__((203)40)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(4((203)40)0)') to (select from Animal where name = 'Nazgul__0')
create vertex Animal set name = 'Nazgul__(03(4((203)40)0))', uuid = '30980822-6910-3068-1139-193429961915'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(03(4((203)40)0))') to (select from Animal where name = 'Nazgul__0')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(03(4((203)40)0))') to (select from Animal where name = 'Nazgul__3')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(03(4((203)40)0))') to (select from Animal where name = 'Nazgul__(4((203)40)0)')
create vertex Animal set name = 'Nazgul__(1(30(4(204)2))(4((203)40)0))', uuid = '83272401-0004-5714-6043-904473224972'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(1(30(4(204)2))(4((203)40)0))') to (select from Animal where name = 'Nazgul__1')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(1(30(4(204)2))(4((203)40)0))') to (select from Animal where name = 'Nazgul__(30(4(204)2))')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(1(30(4(204)2))(4((203)40)0))') to (select from Animal where name = 'Nazgul__(4((203)40)0)')
create vertex Animal set name = 'Nazgul__(((203)40)(4(204)2)(03(4((203)40)0)))', uuid = '43742491-4642-0660-2765-174672729180'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((203)40)(4(204)2)(03(4((203)40)0)))') to (select from Animal where name = 'Nazgul__((203)40)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((203)40)(4(204)2)(03(4((203)40)0)))') to (select from Animal where name = 'Nazgul__(4(204)2)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(((203)40)(4(204)2)(03(4((203)40)0)))') to (select from Animal where name = 'Nazgul__(03(4((203)40)0))')
create vertex Animal set name = 'Nazgul__(3(203)(1(30(4(204)2))(4((203)40)0)))', uuid = '31227950-7335-2914-2556-546477236163'
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(3(203)(1(30(4(204)2))(4((203)40)0)))') to (select from Animal where name = 'Nazgul__3')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(3(203)(1(30(4(204)2))(4((203)40)0)))') to (select from Animal where name = 'Nazgul__(203)')
create edge Animal_ParentOf from (select from Animal where name = 'Nazgul__(3(203)(1(30(4(204)2))(4((203)40)0)))') to (select from Animal where name = 'Nazgul__(1(30(4(204)2))(4((203)40)0))')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__0') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__1') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__2') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__3') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__4') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(204)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(203)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__((203)40)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(4(204)2)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(30(4(204)2))') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(4((203)40)0)') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(03(4((203)40)0))') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(1(30(4(204)2))(4((203)40)0))') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(((203)40)(4(204)2)(03(4((203)40)0)))') to (select from Species where name = 'Nazgul')
create edge Animal_OfSpecies from (select from Animal where name = 'Nazgul__(3(203)(1(30(4(204)2))(4((203)40)0)))') to (select from Species where name = 'Nazgul')
create vertex Animal set name = 'Pteranodon__0', uuid = '51634446-3603-7060-4805-086760069867'
create vertex Animal set name = 'Pteranodon__1', uuid = '27214314-8447-5194-7383-219503201061'
create vertex Animal set name = 'Pteranodon__2', uuid = '66752834-6599-9954-7220-106176939431'
create vertex Animal set name = 'Pteranodon__3', uuid = '87343003-2512-6738-2370-904708941007'
create vertex Animal set name = 'Pteranodon__4', uuid = '49404780-1418-9345-2522-465221707227'
create vertex Animal set name = 'Pteranodon__(321)', uuid = '81617367-6282-5626-2185-350139507775'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(321)') to (select from Animal where name = 'Pteranodon__3')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(321)') to (select from Animal where name = 'Pteranodon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(321)') to (select from Animal where name = 'Pteranodon__1')
create vertex Animal set name = 'Pteranodon__(412)', uuid = '87356918-5340-2664-9438-267873007934'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(412)') to (select from Animal where name = 'Pteranodon__4')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(412)') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(412)') to (select from Animal where name = 'Pteranodon__2')
create vertex Animal set name = 'Pteranodon__((321)31)', uuid = '63357106-0026-0094-8243-139734257640'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((321)31)') to (select from Animal where name = 'Pteranodon__(321)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((321)31)') to (select from Animal where name = 'Pteranodon__3')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((321)31)') to (select from Animal where name = 'Pteranodon__1')
create vertex Animal set name = 'Pteranodon__(((321)31)2(412))', uuid = '01857138-8208-1761-0956-416287090021'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((321)31)2(412))') to (select from Animal where name = 'Pteranodon__((321)31)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((321)31)2(412))') to (select from Animal where name = 'Pteranodon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((321)31)2(412))') to (select from Animal where name = 'Pteranodon__(412)')
create vertex Animal set name = 'Pteranodon__(2(((321)31)2(412))(321))', uuid = '42433959-7526-4744-0706-572625399253'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(2(((321)31)2(412))(321))') to (select from Animal where name = 'Pteranodon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(2(((321)31)2(412))(321))') to (select from Animal where name = 'Pteranodon__(((321)31)2(412))')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(2(((321)31)2(412))(321))') to (select from Animal where name = 'Pteranodon__(321)')
create vertex Animal set name = 'Pteranodon__((2(((321)31)2(412))(321))(((321)31)2(412))4)', uuid = '76398370-8593-6376-9010-199498771549'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((2(((321)31)2(412))(321))(((321)31)2(412))4)') to (select from Animal where name = 'Pteranodon__(2(((321)31)2(412))(321))')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((2(((321)31)2(412))(321))(((321)31)2(412))4)') to (select from Animal where name = 'Pteranodon__(((321)31)2(412))')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((2(((321)31)2(412))(321))(((321)31)2(412))4)') to (select from Animal where name = 'Pteranodon__4')
create vertex Animal set name = 'Pteranodon__(1((2(((321)31)2(412))(321))(((321)31)2(412))4)(321))', uuid = '11576722-4979-5591-7787-169539546820'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(1((2(((321)31)2(412))(321))(((321)31)2(412))4)(321))') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(1((2(((321)31)2(412))(321))(((321)31)2(412))4)(321))') to (select from Animal where name = 'Pteranodon__((2(((321)31)2(412))(321))(((321)31)2(412))4)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(1((2(((321)31)2(412))(321))(((321)31)2(412))4)(321))') to (select from Animal where name = 'Pteranodon__(321)')
create vertex Animal set name = 'Pteranodon__((412)((2(((321)31)2(412))(321))(((321)31)2(412))4)(1((2(((321)31)2(412))(321))(((321)31)2(412))4)(321)))', uuid = '66472829-9047-4587-9199-692876000273'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((412)((2(((321)31)2(412))(321))(((321)31)2(412))4)(1((2(((321)31)2(412))(321))(((321)31)2(412))4)(321)))') to (select from Animal where name = 'Pteranodon__(412)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((412)((2(((321)31)2(412))(321))(((321)31)2(412))4)(1((2(((321)31)2(412))(321))(((321)31)2(412))4)(321)))') to (select from Animal where name = 'Pteranodon__((2(((321)31)2(412))(321))(((321)31)2(412))4)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__((412)((2(((321)31)2(412))(321))(((321)31)2(412))4)(1((2(((321)31)2(412))(321))(((321)31)2(412))4)(321)))') to (select from Animal where name = 'Pteranodon__(1((2(((321)31)2(412))(321))(((321)31)2(412))4)(321))')
create vertex Animal set name = 'Pteranodon__(((2(((321)31)2(412))(321))(((321)31)2(412))4)((321)31)4)', uuid = '80481730-4505-3011-5098-939972654301'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((2(((321)31)2(412))(321))(((321)31)2(412))4)((321)31)4)') to (select from Animal where name = 'Pteranodon__((2(((321)31)2(412))(321))(((321)31)2(412))4)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((2(((321)31)2(412))(321))(((321)31)2(412))4)((321)31)4)') to (select from Animal where name = 'Pteranodon__((321)31)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(((2(((321)31)2(412))(321))(((321)31)2(412))4)((321)31)4)') to (select from Animal where name = 'Pteranodon__4')
create vertex Animal set name = 'Pteranodon__(1(412)((321)31))', uuid = '70805769-3505-8227-2299-195056078064'
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(1(412)((321)31))') to (select from Animal where name = 'Pteranodon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(1(412)((321)31))') to (select from Animal where name = 'Pteranodon__(412)')
create edge Animal_ParentOf from (select from Animal where name = 'Pteranodon__(1(412)((321)31))') to (select from Animal where name = 'Pteranodon__((321)31)')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__0') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__1') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__2') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__3') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__4') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(321)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(412)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((321)31)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((321)31)2(412))') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(2(((321)31)2(412))(321))') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((2(((321)31)2(412))(321))(((321)31)2(412))4)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(1((2(((321)31)2(412))(321))(((321)31)2(412))4)(321))') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__((412)((2(((321)31)2(412))(321))(((321)31)2(412))4)(1((2(((321)31)2(412))(321))(((321)31)2(412))4)(321)))') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(((2(((321)31)2(412))(321))(((321)31)2(412))4)((321)31)4)') to (select from Species where name = 'Pteranodon')
create edge Animal_OfSpecies from (select from Animal where name = 'Pteranodon__(1(412)((321)31))') to (select from Species where name = 'Pteranodon')
create vertex Animal set name = 'Dragon__0', uuid = '24136455-8380-4348-5981-307081403307'
create vertex Animal set name = 'Dragon__1', uuid = '73800397-6584-0813-3131-660458400878'
create vertex Animal set name = 'Dragon__2', uuid = '26083940-9620-3151-1962-869486022122'
create vertex Animal set name = 'Dragon__3', uuid = '84815090-3890-8507-1676-304932155046'
create vertex Animal set name = 'Dragon__4', uuid = '94442363-5898-3064-2037-918070483976'
create vertex Animal set name = 'Dragon__(013)', uuid = '59259367-6719-1526-2462-731614307675'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(013)') to (select from Animal where name = 'Dragon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(013)') to (select from Animal where name = 'Dragon__1')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(013)') to (select from Animal where name = 'Dragon__3')
create vertex Animal set name = 'Dragon__(304)', uuid = '25838773-1984-8835-3699-738939599861'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(304)') to (select from Animal where name = 'Dragon__3')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(304)') to (select from Animal where name = 'Dragon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(304)') to (select from Animal where name = 'Dragon__4')
create vertex Animal set name = 'Dragon__(03(013))', uuid = '95662691-6637-0884-1452-479580891888'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(03(013))') to (select from Animal where name = 'Dragon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(03(013))') to (select from Animal where name = 'Dragon__3')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(03(013))') to (select from Animal where name = 'Dragon__(013)')
create vertex Animal set name = 'Dragon__(4(03(013))1)', uuid = '74013859-9053-5441-8464-151881003952'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(4(03(013))1)') to (select from Animal where name = 'Dragon__4')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(4(03(013))1)') to (select from Animal where name = 'Dragon__(03(013))')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(4(03(013))1)') to (select from Animal where name = 'Dragon__1')
create vertex Animal set name = 'Dragon__(20(03(013)))', uuid = '81881508-5746-9583-0028-324953052337'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(20(03(013)))') to (select from Animal where name = 'Dragon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(20(03(013)))') to (select from Animal where name = 'Dragon__0')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(20(03(013)))') to (select from Animal where name = 'Dragon__(03(013))')
create vertex Animal set name = 'Dragon__(2(4(03(013))1)(013))', uuid = '48331745-4639-4347-9842-432194133599'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(2(4(03(013))1)(013))') to (select from Animal where name = 'Dragon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(2(4(03(013))1)(013))') to (select from Animal where name = 'Dragon__(4(03(013))1)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(2(4(03(013))1)(013))') to (select from Animal where name = 'Dragon__(013)')
create vertex Animal set name = 'Dragon__((304)(2(4(03(013))1)(013))(20(03(013))))', uuid = '54360382-9950-0231-7320-301691710880'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((304)(2(4(03(013))1)(013))(20(03(013))))') to (select from Animal where name = 'Dragon__(304)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((304)(2(4(03(013))1)(013))(20(03(013))))') to (select from Animal where name = 'Dragon__(2(4(03(013))1)(013))')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((304)(2(4(03(013))1)(013))(20(03(013))))') to (select from Animal where name = 'Dragon__(20(03(013)))')
create vertex Animal set name = 'Dragon__(2((304)(2(4(03(013))1)(013))(20(03(013))))(20(03(013))))', uuid = '38437625-7866-5097-2666-356251191844'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(2((304)(2(4(03(013))1)(013))(20(03(013))))(20(03(013))))') to (select from Animal where name = 'Dragon__2')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(2((304)(2(4(03(013))1)(013))(20(03(013))))(20(03(013))))') to (select from Animal where name = 'Dragon__((304)(2(4(03(013))1)(013))(20(03(013))))')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(2((304)(2(4(03(013))1)(013))(20(03(013))))(20(03(013))))') to (select from Animal where name = 'Dragon__(20(03(013)))')
create vertex Animal set name = 'Dragon__(4(2((304)(2(4(03(013))1)(013))(20(03(013))))(20(03(013))))((304)(2(4(03(013))1)(013))(20(03(013)))))', uuid = '53822490-7047-4424-2265-995025691088'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(4(2((304)(2(4(03(013))1)(013))(20(03(013))))(20(03(013))))((304)(2(4(03(013))1)(013))(20(03(013)))))') to (select from Animal where name = 'Dragon__4')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(4(2((304)(2(4(03(013))1)(013))(20(03(013))))(20(03(013))))((304)(2(4(03(013))1)(013))(20(03(013)))))') to (select from Animal where name = 'Dragon__(2((304)(2(4(03(013))1)(013))(20(03(013))))(20(03(013))))')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__(4(2((304)(2(4(03(013))1)(013))(20(03(013))))(20(03(013))))((304)(2(4(03(013))1)(013))(20(03(013)))))') to (select from Animal where name = 'Dragon__((304)(2(4(03(013))1)(013))(20(03(013))))')
create vertex Animal set name = 'Dragon__((2(4(03(013))1)(013))(304)(4(03(013))1))', uuid = '41378986-5719-7546-6852-429851014626'
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((2(4(03(013))1)(013))(304)(4(03(013))1))') to (select from Animal where name = 'Dragon__(2(4(03(013))1)(013))')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((2(4(03(013))1)(013))(304)(4(03(013))1))') to (select from Animal where name = 'Dragon__(304)')
create edge Animal_ParentOf from (select from Animal where name = 'Dragon__((2(4(03(013))1)(013))(304)(4(03(013))1))') to (select from Animal where name = 'Dragon__(4(03(013))1)')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__0') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__1') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__2') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__3') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__4') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(013)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(304)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(03(013))') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(4(03(013))1)') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(20(03(013)))') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(2(4(03(013))1)(013))') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((304)(2(4(03(013))1)(013))(20(03(013))))') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(2((304)(2(4(03(013))1)(013))(20(03(013))))(20(03(013))))') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__(4(2((304)(2(4(03(013))1)(013))(20(03(013))))(20(03(013))))((304)(2(4(03(013))1)(013))(20(03(013)))))') to (select from Species where name = 'Dragon')
create edge Animal_OfSpecies from (select from Animal where name = 'Dragon__((2(4(03(013))1)(013))(304)(4(03(013))1))') to (select from Species where name = 'Dragon')
create vertex Animal set name = 'Hippogriff__0', uuid = '87469836-1534-4684-1779-345870285842'
create vertex Animal set name = 'Hippogriff__1', uuid = '09164350-9404-7377-2908-512528235382'
create vertex Animal set name = 'Hippogriff__2', uuid = '01650943-7046-9781-4023-338185351408'
create vertex Animal set name = 'Hippogriff__3', uuid = '33964705-5854-5735-7969-367329398289'
create vertex Animal set name = 'Hippogriff__4', uuid = '26708379-0621-7953-4454-099124608628'
create vertex Animal set name = 'Hippogriff__(314)', uuid = '90786157-4523-8441-3528-323899075122'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(314)') to (select from Animal where name = 'Hippogriff__3')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(314)') to (select from Animal where name = 'Hippogriff__1')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(314)') to (select from Animal where name = 'Hippogriff__4')
create vertex Animal set name = 'Hippogriff__(2(314)3)', uuid = '07832231-5202-8489-2585-129287777801'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(2(314)3)') to (select from Animal where name = 'Hippogriff__2')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(2(314)3)') to (select from Animal where name = 'Hippogriff__(314)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(2(314)3)') to (select from Animal where name = 'Hippogriff__3')
create vertex Animal set name = 'Hippogriff__(312)', uuid = '41008099-7424-3378-1220-850447716501'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(312)') to (select from Animal where name = 'Hippogriff__3')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(312)') to (select from Animal where name = 'Hippogriff__1')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(312)') to (select from Animal where name = 'Hippogriff__2')
create vertex Animal set name = 'Hippogriff__((314)2(312))', uuid = '56147813-4442-8936-3565-678125585975'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((314)2(312))') to (select from Animal where name = 'Hippogriff__(314)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((314)2(312))') to (select from Animal where name = 'Hippogriff__2')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((314)2(312))') to (select from Animal where name = 'Hippogriff__(312)')
create vertex Animal set name = 'Hippogriff__((312)32)', uuid = '44607940-2127-0891-1938-090698383433'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((312)32)') to (select from Animal where name = 'Hippogriff__(312)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((312)32)') to (select from Animal where name = 'Hippogriff__3')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((312)32)') to (select from Animal where name = 'Hippogriff__2')
create vertex Animal set name = 'Hippogriff__((314)(312)((312)32))', uuid = '70532911-1665-5989-0806-954399673196'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((314)(312)((312)32))') to (select from Animal where name = 'Hippogriff__(314)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((314)(312)((312)32))') to (select from Animal where name = 'Hippogriff__(312)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((314)(312)((312)32))') to (select from Animal where name = 'Hippogriff__((312)32)')
create vertex Animal set name = 'Hippogriff__(3((312)32)(314))', uuid = '38081127-6419-7687-1787-461727655000'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(3((312)32)(314))') to (select from Animal where name = 'Hippogriff__3')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(3((312)32)(314))') to (select from Animal where name = 'Hippogriff__((312)32)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(3((312)32)(314))') to (select from Animal where name = 'Hippogriff__(314)')
create vertex Animal set name = 'Hippogriff__(((312)32)1((314)(312)((312)32)))', uuid = '39838035-9049-0535-7489-908819129852'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((312)32)1((314)(312)((312)32)))') to (select from Animal where name = 'Hippogriff__((312)32)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((312)32)1((314)(312)((312)32)))') to (select from Animal where name = 'Hippogriff__1')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(((312)32)1((314)(312)((312)32)))') to (select from Animal where name = 'Hippogriff__((314)(312)((312)32))')
create vertex Animal set name = 'Hippogriff__(340)', uuid = '60700278-5913-7315-0323-450334440268'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(340)') to (select from Animal where name = 'Hippogriff__3')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(340)') to (select from Animal where name = 'Hippogriff__4')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__(340)') to (select from Animal where name = 'Hippogriff__0')
create vertex Animal set name = 'Hippogriff__((312)10)', uuid = '13565536-7487-9437-0393-520146551039'
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((312)10)') to (select from Animal where name = 'Hippogriff__(312)')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((312)10)') to (select from Animal where name = 'Hippogriff__1')
create edge Animal_ParentOf from (select from Animal where name = 'Hippogriff__((312)10)') to (select from Animal where name = 'Hippogriff__0')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__0') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__1') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__2') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__3') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__4') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(314)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(2(314)3)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(312)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((314)2(312))') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((312)32)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((314)(312)((312)32))') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(3((312)32)(314))') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(((312)32)1((314)(312)((312)32)))') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__(340)') to (select from Species where name = 'Hippogriff')
create edge Animal_OfSpecies from (select from Animal where name = 'Hippogriff__((312)10)') to (select from Species where name = 'Hippogriff')

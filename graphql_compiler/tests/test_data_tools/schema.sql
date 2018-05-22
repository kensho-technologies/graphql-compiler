### UUIDs ###
CREATE CLASS UniquelyIdentifiable
CREATE PROPERTY UniquelyIdentifiable.uuid String
# make uuid default to '' and insert such a record on purpose
# this will ensure that no UniquelyIdentifiable is added without a valid uuid field
ALTER PROPERTY UniquelyIdentifiable.uuid DEFAULT ''
INSERT INTO UniquelyIdentifiable SET uuid = ''
CREATE INDEX UniquelyIdentifiable.uuid UNIQUE_HASH_INDEX
###############

### Entity ###
CREATE CLASS Entity EXTENDS V, UniquelyIdentifiable ABSTRACT
CREATE PROPERTY Entity.name String
CREATE INDEX Entity.name NOTUNIQUE

CREATE PROPERTY Entity.alias EmbeddedSet String
ALTER PROPERTY Entity.alias DEFAULT {}
CREATE INDEX Entity.alias NOTUNIQUE

CREATE PROPERTY Entity.description String
###############

### Event ###
CREATE CLASS Event EXTENDS Entity

CREATE PROPERTY Event.event_date Date
CREATE INDEX Event.event_date NOTUNIQUE
###############

### BirthEvent ###
CREATE CLASS BirthEvent EXTENDS Event
###############

### Animal ###
CREATE CLASS Animal EXTENDS Entity

CREATE PROPERTY Animal.birthday Date
CREATE INDEX Animal.birthday NOTUNIQUE

CREATE PROPERTY Animal.color String
CREATE INDEX Animal.color NOTUNIQUE

CREATE CLASS Animal_ParentOf EXTENDS E
CREATE PROPERTY Animal_ParentOf.out LINK Animal
CREATE PROPERTY Animal_ParentOf.in LINK Animal
CREATE INDEX Animal_ParentOf ON Animal_ParentOf (in, out) UNIQUE_HASH_INDEX

CREATE CLASS Animal_FedAt EXTENDS E
CREATE PROPERTY Animal_FedAt.in LINK Event
CREATE PROPERTY Animal_FedAt.out LINK Animal
CREATE INDEX Animal_FedAt ON Animal_FedAt (in, out) UNIQUE_HASH_INDEX

CREATE CLASS Animal_ImportantEvent EXTENDS E
CREATE PROPERTY Animal_ImportantEvent.in LINK Event
CREATE PROPERTY Animal_ImportantEvent.out LINK Animal
CREATE INDEX Animal_ImportantEvent ON Animal_ImportantEvent (in, out) UNIQUE_HASH_INDEX

CREATE CLASS Animal_BornAt EXTENDS E
CREATE PROPERTY Animal_BornAt.in LINK Event
CREATE PROPERTY Animal_BornAt.out LINK Animal
CREATE INDEX Animal_BornAt ON Animal_BornAt (in, out) UNIQUE_HASH_INDEX
###############

### Species ###
CREATE CLASS Species EXTENDS Entity

CREATE PROPERTY Species.limbs Date
CREATE INDEX Species.limbs NOTUNIQUE

CREATE CLASS Species_Eats EXTENDS E
CREATE PROPERTY Species_Eats.out LINK Species
CREATE PROPERTY Species_Eats.in LINK Species
CREATE INDEX Species_Eats ON Species_Eats (in, out) UNIQUE_HASH_INDEX

CREATE CLASS Animal_OfSpecies EXTENDS E
CREATE PROPERTY Animal_OfSpecies.in LINK Species
CREATE PROPERTY Animal_OfSpecies.out LINK Animal
CREATE INDEX Animal_OfSpecies ON Animal_OfSpecies (in, out) UNIQUE_HASH_INDEX
###############


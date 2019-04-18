### UUIDs ###
CREATE CLASS UniquelyIdentifiable ABSTRACT
CREATE PROPERTY UniquelyIdentifiable.uuid String
ALTER PROPERTY UniquelyIdentifiable.uuid MANDATORY TRUE
CREATE INDEX UniquelyIdentifiable.uuid UNIQUE_HASH_INDEX
###############


### Entity ###
CREATE CLASS Entity EXTENDS V, UniquelyIdentifiable ABSTRACT
CREATE PROPERTY Entity.name String
CREATE INDEX Entity.name UNIQUE

CREATE PROPERTY Entity.alias EmbeddedSet String
ALTER PROPERTY Entity.alias DEFAULT {}
CREATE INDEX Entity.alias NOTUNIQUE

CREATE PROPERTY Entity.description String

CREATE CLASS Entity_Related EXTENDS E
CREATE PROPERTY Entity_Related.in LINK Entity
CREATE PROPERTY Entity_Related.out LINK Entity
CREATE INDEX Entity_Related ON Entity_Related (in, out) UNIQUE_HASH_INDEX
###############


### Event ###
CREATE CLASS Event EXTENDS Entity

CREATE PROPERTY Event.event_date DateTime
CREATE INDEX Event.event_date NOTUNIQUE

CREATE CLASS Event_RelatedEvent EXTENDS E
CREATE PROPERTY Event_RelatedEvent.in LINK Event
CREATE PROPERTY Event_RelatedEvent.out LINK Event
CREATE INDEX Event_RelatedEvent ON Event_RelatedEvent (in, out) UNIQUE_HASH_INDEX
###############


### BirthEvent ###
CREATE CLASS BirthEvent EXTENDS Event
###############

### FeedingEvent ###
CREATE CLASS FeedingEvent EXTENDS Event
###############

### Location ###
CREATE CLASS Location EXTENDS Entity
###############

### Animal ###
CREATE CLASS Animal EXTENDS Entity

CREATE PROPERTY Animal.color String
CREATE INDEX Animal.color NOTUNIQUE

CREATE PROPERTY Animal.birthday Date
CREATE INDEX Animal.birthday NOTUNIQUE

CREATE PROPERTY Animal.net_worth Decimal
CREATE INDEX Animal.net_worth NOTUNIQUE

CREATE CLASS Animal_ParentOf EXTENDS E
CREATE PROPERTY Animal_ParentOf.in LINK Animal
CREATE PROPERTY Animal_ParentOf.out LINK Animal
ALTER CLASS Animal_ParentOf CUSTOM human_name_in="Parent"
ALTER CLASS Animal_ParentOf CUSTOM human_name_out="Child"
CREATE INDEX Animal_ParentOf ON Animal_ParentOf (in, out) UNIQUE_HASH_INDEX

CREATE CLASS Animal_FedAt EXTENDS E
CREATE PROPERTY Animal_FedAt.in LINK FeedingEvent
CREATE PROPERTY Animal_FedAt.out LINK Animal
CREATE INDEX Animal_FedAt ON Animal_FedAt (in, out) UNIQUE_HASH_INDEX

CREATE CLASS Animal_ImportantEvent EXTENDS E
CREATE PROPERTY Animal_ImportantEvent.in LINK Event
CREATE PROPERTY Animal_ImportantEvent.out LINK Animal
CREATE INDEX Animal_ImportantEvent ON Animal_ImportantEvent (in, out) UNIQUE_HASH_INDEX

CREATE CLASS Animal_BornAt EXTENDS E
CREATE PROPERTY Animal_BornAt.in LINK BirthEvent
CREATE PROPERTY Animal_BornAt.out LINK Animal
CREATE INDEX Animal_BornAt ON Animal_BornAt (in, out) UNIQUE_HASH_INDEX

CREATE CLASS Animal_LivesIn EXTENDS E
CREATE PROPERTY Animal_LivesIn.in LINK Location
CREATE PROPERTY Animal_LivesIn.out LINK Animal
CREATE INDEX Animal_LivesIn ON Animal_LivesIn (in, out) UNIQUE_HASH_INDEX
###############


### FoodOrSpecies ###
CREATE CLASS FoodOrSpecies EXTENDS Entity
###############


### Species ###
CREATE CLASS Species EXTENDS FoodOrSpecies

CREATE PROPERTY Species.limbs Integer
CREATE INDEX Species.limbs NOTUNIQUE

CREATE CLASS Animal_OfSpecies EXTENDS E
CREATE PROPERTY Animal_OfSpecies.in LINK Species
CREATE PROPERTY Animal_OfSpecies.out LINK Animal
CREATE INDEX Animal_OfSpecies ON Animal_OfSpecies (in, out) UNIQUE_HASH_INDEX

CREATE CLASS Species_Eats EXTENDS E
CREATE PROPERTY Species_Eats.in LINK FoodOrSpecies
CREATE PROPERTY Species_Eats.out LINK Species
CREATE INDEX Species_Eats ON Species_Eats (in, out) UNIQUE_HASH_INDEX
###############


### Food ###
CREATE CLASS Food EXTENDS FoodOrSpecies
###############

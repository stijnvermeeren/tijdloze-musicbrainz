CREATE TABLE "musicbrainz_export"."mb_artist"
(
    "id"         int PRIMARY KEY,
    "mb_id"      uuid,
    "name"       varchar,
    "country_id" varchar,
    "score"      int
);

CREATE TABLE "musicbrainz_export"."mb_artist_alias"
(
    "artist_id" int,
    "alias"     varchar,
    UNIQUE ("artist_id", "alias")
);

CREATE INDEX "idx_mb_artist_alias_artist_id" ON "musicbrainz_export"."mb_artist_alias" (artist_id);
CREATE INDEX "idx_mb_artist_alias_alias" ON "musicbrainz_export"."mb_artist_alias" (alias);

CREATE TABLE "musicbrainz_export"."mb_album"
(
    "id"            int PRIMARY KEY,
    "mb_id"         uuid,
    "title"         varchar,
    "release_year"  int,
    "is_soundtrack" boolean,
    "is_single"     boolean,
    "is_main_album" boolean
);

CREATE TABLE "musicbrainz_export"."mb_song"
(
    "id"        int PRIMARY KEY,
    "mb_id"     uuid,
    "title"     varchar,
    "artist_id" int,
    "album_id"  int,
    "is_single" boolean,
    "score"     int
);

CREATE INDEX "idx_mb_song_artist_id" ON "musicbrainz_export"."mb_song" (artist_id);

CREATE TABLE "musicbrainz_export"."mb_song_alias"
(
    "song_id" int,
    "alias"   varchar,
    UNIQUE ("song_id", "alias")
);

CREATE INDEX "idx_mb_song_alias_song_id" ON "musicbrainz_export"."mb_song_alias" (song_id);
CREATE INDEX "idx_mb_song_alias_alias" ON "musicbrainz_export"."mb_song_alias" (alias);
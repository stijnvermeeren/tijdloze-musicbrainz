SET search_path TO musicbrainz_export, musicbrainz, public;

WITH data AS (
    SELECT id, "name"
    FROM "musicbrainz_export"."mb_artist"

    UNION

    SELECT mb_artist.id, artist_alias."name"
    FROM "musicbrainz_export"."mb_artist"
         JOIN "musicbrainz"."artist_alias" ON artist_alias.artist = mb_artist.id

    UNION

    SELECT mb_artist.id, artist_credit_name."name"
    FROM "musicbrainz_export"."mb_artist"
         JOIN "musicbrainz"."artist_credit_name" ON artist_credit_name.artist = mb_artist.id

    UNION

    SELECT mb_artist.id, artist2.name
    FROM "musicbrainz_export"."mb_artist"
         JOIN "musicbrainz"."l_artist_artist" ON entity1 = mb_artist.id
         JOIN "musicbrainz"."link" ON l_artist_artist.link = "link".id AND "link_type" = 103
         JOIN "musicbrainz"."artist" AS artist2 ON artist2.id = l_artist_artist.entity0
         JOIN "musicbrainz"."link_attribute" ON link_attribute."link" = "link".id AND link_attribute.attribute_type = 1094
)
INSERT INTO "musicbrainz_export"."mb_artist_alias" (artist_id, alias)
SELECT
    id,
    LOWER(REGEXP_REPLACE(UNACCENT(name), '\W', '', 'g'))
FROM data
ON CONFLICT ("artist_id", "alias") DO NOTHING;

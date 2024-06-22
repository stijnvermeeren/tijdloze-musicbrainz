WITH data AS (
    SELECT
        id, gid, name, country_id, (SELECT COUNT(*) FROM "l_artist_url" WHERE "entity0" = "artist"."id") as score
    FROM "musicbrainz"."artist"
    LEFT JOIN "musicbrainz_export"."tmp_area_country_id" ON "tmp_area_country_id"."area_id" = "artist"."area"
)
INSERT INTO "musicbrainz_export"."mb_artist" (id, mb_id, name, country_id, score)
SELECT id, gid, name, country_id, score
FROM data
WHERE country_id = 'be' OR score > 8;

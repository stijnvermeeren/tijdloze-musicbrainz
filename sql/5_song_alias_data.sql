
WITH data AS (
    SELECT mb_song.id, recording.name
    FROM "musicbrainz_export"."mb_song"
    JOIN "musicbrainz"."recording" ON recording.gid = mb_song.mb_id

    UNION

    SELECT mb_song.id, recording_alias.name
    FROM "musicbrainz_export"."mb_song"
    JOIN "musicbrainz"."recording" ON recording.gid = mb_song.mb_id
    JOIN "musicbrainz"."recording_alias" ON "recording_alias"."recording" = "recording"."id"

    UNION

    SELECT mb_song.id, work.name
    FROM "musicbrainz_export"."mb_song"
    JOIN "musicbrainz"."recording" ON recording.gid = mb_song.mb_id
    JOIN "musicbrainz"."l_recording_work" ON "l_recording_work"."entity0" = "recording"."id"
    JOIN "musicbrainz"."work" ON "work"."id" = "l_recording_work"."entity1"

    UNION

    SELECT mb_song.id, work_alias.name
    FROM "musicbrainz_export"."mb_song"
    JOIN "musicbrainz"."recording" ON recording.gid = mb_song.mb_id
    JOIN "musicbrainz"."l_recording_work" ON "l_recording_work"."entity0" = "recording"."id"
    JOIN "musicbrainz"."work" ON "work"."id" = "l_recording_work"."entity1"
    JOIN "musicbrainz"."work_alias" ON "work_alias"."work" = "work"."id"
)
INSERT INTO "musicbrainz_export"."mb_song_alias"
SELECT id, LOWER(REGEXP_REPLACE(UNACCENT('musicbrainz.unaccent', name), '\W', '', 'g'))
FROM data
ON CONFLICT ("song_id", "alias") DO NOTHING;


WITH data AS (
    SELECT mb_song.id, recording.name
    FROM mb_song
    JOIN recording ON recording.gid = mb_song.mb_id

    UNION

    SELECT mb_song.id, recording_alias.name
    FROM mb_song
    JOIN recording ON recording.gid = mb_song.mb_id
    JOIN "recording_alias" ON "recording_alias"."recording" = "recording"."id"

    UNION

    SELECT mb_song.id, work.name
    FROM mb_song
    JOIN recording ON recording.gid = mb_song.mb_id
    JOIN "l_recording_work" ON "l_recording_work"."entity0" = "recording"."id"
    JOIN "work" ON "work"."id" = "l_recording_work"."entity1"

    UNION

    SELECT mb_song.id, work_alias.name
    FROM mb_song
    JOIN recording ON recording.gid = mb_song.mb_id
    JOIN "l_recording_work" ON "l_recording_work"."entity0" = "recording"."id"
    JOIN "work" ON "work"."id" = "l_recording_work"."entity1"
    JOIN "work_alias" ON "work_alias"."work" = "work"."id"
)
INSERT INTO mb_song_alias
SELECT id, LOWER(REGEXP_REPLACE(name, '\W', '', 'g'))
FROM data
ON CONFLICT ("song_id", "alias") DO NOTHING;

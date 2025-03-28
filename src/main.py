from util import query, search_key
from dotenv import load_dotenv

from tqdm import tqdm
import psycopg2
import dataclasses
import os
import argparse

load_dotenv()

@dataclasses.dataclass
class Entry:
    title: str
    recording_id: int
    recording_mb_id: str
    work_mb_id: str
    second_artist_id: int
    release_group_id: int
    release_group_mb_id: str
    release_group_name: str
    release_type: int
    release_secondary_types: list[int]
    release_year: int
    release_group_year: int
    is_single_from: int
    language: str
    recording_score: int

    def is_main_album(self):
        return self.release_type == 1 and not self.release_secondary_types

    def is_compilation_album(self):
        return self.release_type == 1 and self.release_secondary_types and 1 in self.release_secondary_types

    def is_soundtrack_album(self):
        return self.release_type == 1 and self.release_secondary_types and 2 in self.release_secondary_types

    def is_exact_match(self, query):
        return search_key(self.title) == search_key(query)

    def relevance_for_query(self, query):
        if self.is_exact_match(query):
            # exact match
            return self.recording_score
        else:
            # e.g. "Hotellounge (Be the Death of Me)" instead of "Hotellounge"
            return self.recording_score / 10

    def sort_key(self):
        if self.release_year is None:
            year_value = 9999
        elif self.is_single_from or self.is_main_album():
            year_value = self.release_year
        else:
            year_value = self.release_year + 1

        reference_priority = 1
        if self.is_single_from:
            reference_priority = 0

        if self.is_main_album():
            type_priority = 1
        elif self.is_soundtrack_album():
            type_priority = 2
        elif self.is_compilation_album():
            # Note that we have already ensured in the SQL query that we only take compilation albums from the artist,
            # no "various artists" compilation albums.
            type_priority = 3
        else:
            type_priority = 4

        return (year_value, reference_priority, type_priority)


def process_artist(cursor, artist_id: int, args):
    singlesQuery = """
        SELECT
            release_group.name AS title,
            release_group_album."gid" AS album_id
        FROM "artist_credit_name"
        JOIN "artist_credit" ON "artist_credit"."id" = "artist_credit_name"."artist_credit"
        JOIN "release_group" ON "release_group"."artist_credit" = "artist_credit"."id"
        JOIN "l_release_group_release_group" ON "l_release_group_release_group"."entity0" = "release_group".id
        JOIN "link" ON "link"."id" = "l_release_group_release_group"."link"
        JOIN "release_group" AS release_group_album ON release_group_album.id = "l_release_group_release_group"."entity1"
        WHERE "artist_credit_name"."artist" = {} AND "link"."link_type" = 11  -- "single_from"
    """.format(artist_id)

    single_from_relations = {}
    for entry in query(cursor, singlesQuery):
        single_title = search_key(entry["title"])
        if single_title not in single_from_relations:
            single_from_relations[single_title] = set()
        single_from_relations[single_title].add(entry['album_id'])

    recordings_query = """
        SELECT
            release_group.id as release_group_id, 
            release_group.gid as release_group_mb_id, 
            release_group.name as release_group_name,
            release_group.type as release_type,
            MIN(release_country.date_year) as release_year,
            (
                SELECT MIN(date_year) 
                FROM "release_country" 
                JOIN "release" release2 ON release_country.release = release2.id 
                WHERE release2."release_group" = "release_group".id
            ) as release_group_year,
            (SELECT array_agg(secondary_type) FROM release_group_secondary_type_join WHERE release_group_secondary_type_join.release_group = release_group.id) as secondary_types,
            "recording"."id" as recording_id,
            "recording"."gid" as recording_mb_id,
            "recording"."name" as recording_name,
            (SELECT COUNT(*) FROM "release" r2 JOIN "medium" m2 ON m2."release" = r2."id" JOIN "track" t2 ON t2."medium" = m2."id" WHERE t2."recording" = "recording"."id") as recording_score,
            (
              select artist 
              from "artist_credit_name" 
              where "recording"."artist_credit" = "artist_credit_name"."artist_credit"
              and "artist_credit_name"."position" = 1
            ) as second_artist_id,
            (
              select COALESCE("language"."iso_code_1", "language"."iso_code_3") 
              from "musicbrainz"."language" 
              left join "musicbrainz"."work_language" on "language"."id" = "work_language"."language" 
              where "work"."id" = "work_language"."work" 
              and ("language"."iso_code_1" is not NULL OR "language"."iso_code_3" = 'zxx')
              limit 1
            ) as language,
            "work"."gid" as "work_mb_id"
        FROM "musicbrainz"."recording"
        JOIN "musicbrainz"."track" ON "recording"."id" = "track"."recording"
        JOIN "musicbrainz"."medium" ON "track"."medium" = "medium"."id" 
        JOIN "musicbrainz"."release" ON "medium"."release" = "release"."id"
        JOIN "musicbrainz"."release_country" ON "release"."id" = "release_country"."release"
        JOIN "musicbrainz"."release_group" ON "release"."release_group" = "release_group"."id"
        JOIN "musicbrainz"."artist_credit" AS artist_credit_rg ON artist_credit_rg.id = "release_group"."artist_credit"
        JOIN "musicbrainz"."artist_credit_name" AS artist_credit_name_rg ON artist_credit_name_rg."artist_credit" = artist_credit_rg."id"
        JOIN "musicbrainz"."artist_credit" ON "artist_credit".id = "recording"."artist_credit"
        JOIN "musicbrainz"."artist_credit_name" ON "artist_credit_name"."artist_credit" = "artist_credit"."id" AND "artist_credit_name"."position" = 0
        left join "musicbrainz"."l_recording_work" ON "l_recording_work"."entity0" = "recording"."id" and "l_recording_work"."link_order" <= 1
        left join "musicbrainz"."work" ON "work"."id" = "l_recording_work"."entity1"
        WHERE "artist_credit_name"."artist" = {} AND "release"."status" = 1 AND artist_credit_name_rg.artist = artist_credit_name.artist -- official
        GROUP BY recording.id, release_group.id, work.id
    """.format(artist_id)

    recordings_query_soundtrack = """
        SELECT
            release_group.id as release_group_id, 
            release_group.gid as release_group_mb_id, 
            release_group.name as release_group_name,
            release_group.type as release_type,
            MIN(release_country.date_year) as release_year,
            (
                SELECT MIN(date_year) 
                FROM "release_country" 
                JOIN "release" release2 ON release_country.release = release2.id 
                WHERE release2."release_group" = "release_group".id
            ) as release_group_year,
            (SELECT array_agg(secondary_type) FROM release_group_secondary_type_join WHERE release_group_secondary_type_join.release_group = release_group.id) as secondary_types,
            "recording"."id" as recording_id,
            "recording"."gid" as recording_mb_id,
            "recording"."name" as recording_name,
            (SELECT COUNT(*) FROM "release" r2 JOIN "medium" m2 ON m2."release" = r2."id" JOIN "track" t2 ON t2."medium" = m2."id" WHERE t2."recording" = "recording"."id") as recording_score,
            (
              select artist 
              from "artist_credit_name" 
              where "recording"."artist_credit" = "artist_credit_name"."artist_credit"
              and "artist_credit_name"."position" = 1
            ) as second_artist_id,
            (
              select COALESCE("language"."iso_code_1", "language"."iso_code_3") 
              from "musicbrainz"."language" 
              left join "musicbrainz"."work_language" on "language"."id" = "work_language"."language" 
              where "work"."id" = "work_language"."work" 
              and ("language"."iso_code_1" is not NULL OR "language"."iso_code_3" = 'zxx')
              limit 1
            ) as language,
            "work"."gid" as "work_mb_id"
        FROM "musicbrainz"."recording"
        JOIN "musicbrainz"."track" ON "recording"."id" = "track"."recording"
        JOIN "musicbrainz"."medium" ON "track"."medium" = "medium"."id" 
        JOIN "musicbrainz"."release" ON "medium"."release" = "release"."id"
        JOIN "musicbrainz"."release_country" ON "release"."id" = "release_country"."release"
        JOIN "musicbrainz"."release_group" ON "release"."release_group" = "release_group"."id"
        JOIN "musicbrainz"."artist_credit" ON "artist_credit".id = "recording"."artist_credit"
        JOIN "musicbrainz"."artist_credit_name" ON "artist_credit_name"."artist_credit" = "artist_credit"."id" AND "artist_credit_name"."position" = 0
        JOIN "musicbrainz"."release_group_secondary_type_join" ON "release_group_secondary_type_join"."release_group" = "release_group"."id"
        left join "musicbrainz"."l_recording_work" ON "l_recording_work"."entity0" = "recording"."id" and "l_recording_work"."link_order" <= 1
        left join "musicbrainz"."work" ON "work"."id" = "l_recording_work"."entity1"
        WHERE "artist_credit_name"."artist" = {} AND "release"."status" = 1 AND "release_group_secondary_type_join"."secondary_type" = 2
        GROUP BY recording.id, release_group.id, work.id
    """.format(artist_id)

    songs = {}

    def process_entry(entry):
        if entry['release_year'] is None:
            return

        title = entry['recording_name']
        release_group_mb_id = entry['release_group_mb_id']
        search_key_title = search_key(title)
        is_single_from = search_key_title in single_from_relations and release_group_mb_id in single_from_relations[search_key_title]

        song = Entry(
            title=title,
            recording_id=entry['recording_id'],
            recording_mb_id=entry['recording_mb_id'],
            work_mb_id=entry['work_mb_id'],
            second_artist_id=entry['second_artist_id'],
            release_group_id=entry['release_group_id'],
            release_group_mb_id=release_group_mb_id,
            release_group_name=entry['release_group_name'],
            release_type=entry['release_type'],
            release_secondary_types=entry['secondary_types'],
            release_year=entry['release_year'],
            release_group_year=entry['release_group_year'],
            is_single_from=is_single_from,
            language=entry['language'],
            recording_score=entry['recording_score']
        )

        if song.recording_mb_id not in songs:
            songs[song.recording_mb_id] = []
        songs[song.recording_mb_id].append(song)

    for entry in query(cursor, recordings_query):
        process_entry(entry)
    for entry in query(cursor, recordings_query_soundtrack):
        process_entry(entry)

    album_values = {}
    song_values = {}
    for recording_mb_id, recording_songs in songs.items():
        if args.recording_id:
            if args.recording_id == recording_mb_id:
                for song in recording_songs:
                    print(song)
            else:
                continue

        best_match = min(recording_songs, key=lambda song: song.sort_key())

        if args.recording_id:
            if args.recording_id == recording_mb_id:
                print()
                print(best_match)

        if best_match.release_type == 2:
            is_single = 'TRUE'
        else:
            is_single = 'FALSE'

        if best_match.is_soundtrack_album():
            is_soundtrack = 'TRUE'
        else:
            is_soundtrack = 'FALSE'

        if best_match.is_main_album():
            is_main_album = 'TRUE'
        else:
            is_main_album = 'FALSE'

        album_values[best_match.release_group_id] = "({}, '{}', '{}', {}, {}, {}, {})".format(
            best_match.release_group_id,
            best_match.release_group_mb_id,
            best_match.release_group_name.replace("'", "''"),
            best_match.release_group_year,
            is_soundtrack,
            is_single,
            is_main_album
        )

        language = 'NULL'
        work_mb_id = 'NULL'
        if best_match.work_mb_id:
            work_mb_id = "'{}'".format(best_match.work_mb_id)
        if best_match.language:
            language = "'{}'".format(best_match.language)

        song_values[best_match.recording_id] = "({}, '{}', {}, '{}', {}, {}, {}, {}, {}, {})".format(
            best_match.recording_id,
            best_match.recording_mb_id,
            work_mb_id,
            best_match.title.replace("'", "''"),
            artist_id,
            best_match.second_artist_id or "NULL",
            best_match.release_group_id,
            best_match.is_single_from,
            language,
            best_match.recording_score
        )

    if len(album_values):
        insert_album = """
            INSERT INTO "musicbrainz_export"."mb_album" (id, mb_id, title, release_year, is_soundtrack, is_single, is_main_album)
            VALUES {}
            ON CONFLICT(id) DO UPDATE SET
             mb_id = EXCLUDED.mb_id, 
             title = EXCLUDED.title, 
             release_year = EXCLUDED.release_year,
             is_single = EXCLUDED.is_single,
             is_soundtrack = EXCLUDED.is_soundtrack,
             is_main_album = EXCLUDED.is_main_album;
        """.format(", ".join(album_values.values()))
        cursor.execute(insert_album)

    if len(song_values):
        insert_song = """
            INSERT INTO "musicbrainz_export"."mb_song" (
              id, mb_id, mb_work_id, title, artist_id, second_artist_id, album_id, is_single, language, score
            )
            VALUES {}
            ON CONFLICT(id) DO UPDATE SET
             mb_id = EXCLUDED.mb_id,
             mb_work_id = EXCLUDED.mb_work_id,
             title = EXCLUDED.title, 
             artist_id = EXCLUDED.artist_id,
             second_artist_id = EXCLUDED.second_artist_id,
             album_id = EXCLUDED.album_id,
             is_single = EXCLUDED.is_single,
             language = EXCLUDED.language,
             score = EXCLUDED.score;
        """.format(", ".join(song_values.values()))
        cursor.execute(insert_song)


try:
    parser=argparse.ArgumentParser()
    parser.add_argument("--artist")
    parser.add_argument("--artist_id")
    parser.add_argument("--recording_id")
    args=parser.parse_args()

    with psycopg2.connect(
            host=os.getenv("MB_DB_HOST"),
            database=os.getenv("MB_DB_NAME"),
            user=os.getenv("MB_DB_USER"),
            password=os.getenv("MB_DB_PASSWORD")
    ) as conn:
        with conn.cursor() as cursor:
            if args.artist_id:
                where = """WHERE "mb_artist"."id" = {}""".format(args.artist_id)
            elif args.artist:
                where = """WHERE "mb_artist"."name" = '{}'""".format(args.artist)
            else:
                where = ""
            sql_query = """
                SELECT id, name 
                FROM "musicbrainz_export"."mb_artist"
                {} 
                ORDER BY score DESC;
            """.format(where)
            for artist in tqdm(query(cursor, sql_query)):
                print(artist)
                process_artist(cursor, artist['id'], args)
                conn.commit()
except psycopg2.DatabaseError as error:
    print("Error: {}".format(error))

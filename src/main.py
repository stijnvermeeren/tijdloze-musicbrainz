from util import query, search_key
from dotenv import load_dotenv

from tqdm import tqdm
import psycopg
from psycopg.sql import SQL, Literal
import dataclasses
import os
import argparse
import logging

load_dotenv()

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s.%(msecs)03d %(levelname)s:\t%(message)s',
    datefmt='%Y-%m-%d,%H:%M:%S'
)
logger = logging.getLogger(__name__)

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
    lead_vocals: str
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

    logger.info("check singles")
    single_from_relations = {}
    for entry in query(cursor, singlesQuery):
        single_title = search_key(entry["title"])
        if single_title not in single_from_relations:
            single_from_relations[single_title] = set()
        single_from_relations[single_title].add(entry['album_id'])
    logger.info("singles loaded")

    select = """
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
            "work"."gid" as "work_mb_id",
            (
                select array_agg("artist"."gender")
                from "l_artist_recording"
                join "link" on "link"."id" = "l_artist_recording"."link"
                join "link_attribute" on "link_attribute"."link" = "link"."id"
                join "artist" on "artist"."id" = "l_artist_recording"."entity0"
                where "l_artist_recording"."entity1" = "recording"."id"
                and "link"."link_type" = 149  -- vocals
                and "link_attribute"."attribute_type" = 4  -- lead
            ) as "lead_vocals_1",
            (
                select array_agg("artist"."gender")
                from "l_artist_recording"
                join "link" on "link"."id" = "l_artist_recording"."link"
                join "artist" on "artist"."id" = "l_artist_recording"."entity0"
                where "l_artist_recording"."entity1" = "recording"."id"
                and "link"."link_type" = 149  -- vocals
                and not exists (
                    select 1 from "link_attribute" 
                    where "link_attribute"."link" = "link"."id" and "link_attribute"."attribute_type" = 12  -- background
                )
            ) as "lead_vocals_2",
            (
                select array_agg("artist"."gender")
                from "artist" 
                join "artist_credit_name" on "artist"."id" = "artist_credit_name"."artist"
                where "recording"."artist_credit" = "artist_credit_name"."artist_credit"
            ) as "lead_vocals_3"
        """

    recordings_query = select + SQL("""
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
        WHERE "artist_credit_name"."artist" = {artist_id} AND "release"."status" = 1 AND artist_credit_name_rg.artist = artist_credit_name.artist -- official
        GROUP BY recording.id, release_group.id, work.id
    """).format(artist_id=Literal(artist_id)).as_string()

    recordings_query_soundtrack = select + SQL("""
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
        WHERE "artist_credit_name"."artist" = {artist_id} AND "release"."status" = 1 AND "release_group_secondary_type_join"."secondary_type" = 2
        GROUP BY recording.id, release_group.id, work.id
    """).format(artist_id=Literal(artist_id)).as_string()

    songs = {}

    def process_entry(entry):
        if entry['release_year'] is None:
            return

        title = entry['recording_name']
        release_group_mb_id = entry['release_group_mb_id']
        search_key_title = search_key(title)
        is_single_from = search_key_title in single_from_relations and release_group_mb_id in single_from_relations[search_key_title]

        lead_vocals = None

        # PRIO 1: if lead vocals for the recording are defined, use the gender(s) of the associated person/people
        lead_vocals_1 = set(entry['lead_vocals_1'] or [])
        if 1 in lead_vocals_1 and 2 in lead_vocals_1:
            lead_vocals = "x"
        elif 1 in lead_vocals_1:
            lead_vocals = "m"
        elif 2 in lead_vocals_1:
            lead_vocals = "f"
        else:
            # PRIO 2: if any non-background vocals are defined for the recording, use the gender(s) of the
            # associated person/people
            lead_vocals_2 = set(entry['lead_vocals_2'] or [])
            if 1 in lead_vocals_2 and 2 in lead_vocals_2:
                lead_vocals = "x"
            elif 1 in lead_vocals_2:
                lead_vocals = "m"
            elif 2 in lead_vocals_2:
                lead_vocals = "f"
            else:
                if entry['language'] == 'zxx':
                    # PRIO 3: if no song language and no vocals, then set lead vocals to instrumental as well
                    lead_vocals = "i"
                elif entry['language']:
                    # PRIO 3: if all artists is a persons of the same gender and song language is defined (not
                    # instrumental): use gender of artist(s).
                    # Should not be prio 1, to avoid mistakes with e.g. Mike Oldfield - Moonlight Shadow.
                    lead_vocals_3 = set(entry['lead_vocals_3'])
                    if lead_vocals_3 == {1}:  # only male
                        lead_vocals = "m"
                    elif lead_vocals_3 == {2}:  # only female
                        lead_vocals = "f"

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
            lead_vocals=lead_vocals,
            recording_score=entry['recording_score']
        )

        if song.recording_mb_id not in songs:
            songs[song.recording_mb_id] = [song]
        else:
            songs[song.recording_mb_id].append(song)

    logger.info("start")
    for entry in query(cursor, recordings_query):
        process_entry(entry)
    logger.info("soundtrack")
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

        album_values[best_match.release_group_id] = [
            best_match.release_group_id,
            best_match.release_group_mb_id,
            best_match.release_group_name,
            best_match.release_group_year,
            best_match.is_soundtrack_album(),
            best_match.release_type == 2,
            best_match.is_main_album()
        ]

        song_values[best_match.recording_id] = [
            best_match.recording_id,
            best_match.recording_mb_id,
            best_match.work_mb_id,
            best_match.title,
            artist_id,
            best_match.second_artist_id,
            best_match.release_group_id,
            best_match.is_single_from,
            best_match.language,
            best_match.lead_vocals,
            best_match.recording_score
        ]

    if len(album_values):
        insert_album = """
            INSERT INTO "musicbrainz_export"."mb_album" (id, mb_id, title, release_year, is_soundtrack, is_single, is_main_album)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(id) DO UPDATE SET
             mb_id = EXCLUDED.mb_id, 
             title = EXCLUDED.title, 
             release_year = EXCLUDED.release_year,
             is_single = EXCLUDED.is_single,
             is_soundtrack = EXCLUDED.is_soundtrack,
             is_main_album = EXCLUDED.is_main_album;
        """
        cursor.executemany(insert_album, album_values.values())

    if len(song_values):
        insert_song = """
            INSERT INTO "musicbrainz_export"."mb_song" (
              id, mb_id, mb_work_id, title, artist_id, second_artist_id, album_id, is_single, language, lead_vocals, score
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(id) DO UPDATE SET
             mb_id = EXCLUDED.mb_id,
             mb_work_id = EXCLUDED.mb_work_id,
             title = EXCLUDED.title, 
             artist_id = EXCLUDED.artist_id,
             second_artist_id = EXCLUDED.second_artist_id,
             album_id = EXCLUDED.album_id,
             is_single = EXCLUDED.is_single,
             language = EXCLUDED.language,
             lead_vocals = EXCLUDED.lead_vocals,
             score = EXCLUDED.score;
        """
        cursor.executemany(insert_song, song_values.values())


try:
    parser=argparse.ArgumentParser()
    parser.add_argument("--artist")
    parser.add_argument("--artist_id")
    parser.add_argument("--recording_id")
    args=parser.parse_args()

    conn_str = f"""postgresql://{os.getenv("MB_DB_USER")}:{os.getenv("MB_DB_PASSWORD")}@{os.getenv("MB_DB_HOST")}:5432/{os.getenv("MB_DB_NAME")}"""
    with psycopg.connect(conn_str) as conn:
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
except psycopg.DatabaseError as error:
    print("Error: {}".format(error))

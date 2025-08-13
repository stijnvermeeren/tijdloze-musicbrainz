
class BenchmarkProperty:
    title: str

    @classmethod
    def db_property(cls, db_data):
        pass

    @classmethod
    def mb_property(cls, song):
        pass

    @classmethod
    def log(cls, db_data, song):
        db_value = cls.db_property(db_data)
        mb_value = cls.mb_property(song)

        song_description = f"""({db_data["id"]}) {db_data["artist_name"]} - {db_data["title"]}"""
        if mb_value is None:
            print(f"""{db_value}   {song_description}""")
        else:
            print(f"{mb_value} instead of {db_value}   {song_description}")


class LeadVocals(BenchmarkProperty):
    title = "Lead vocals"

    @classmethod
    def db_property(cls, db_data):
        return db_data["lead_vocals_id"]

    @classmethod
    def mb_property(cls, song):
        return song.lead_vocals_id


class Language(BenchmarkProperty):
    title = "Language"

    @classmethod
    def db_property(cls, db_data):
        language_id = db_data["language_id"]
        if language_id == 'i':
            language_id = 'zxx'
        return language_id

    @classmethod
    def mb_property(cls, song):
        return song.language_id

class Country(BenchmarkProperty):
    title = "Country"

    @classmethod
    def db_property(cls, db_data):
        return db_data["artist_country_id"]

    @classmethod
    def mb_property(cls, song):
        return song.country_id

class Album(BenchmarkProperty):
    title = "Album"

    @classmethod
    def db_property(cls, db_data):
        return db_data["musicbrainz_id"]

    @classmethod
    def mb_property(cls, song):
        return song.album_mb_id if song else None

    def log(cls, db_data, song):
        db_value = cls.db_property(db_data)
        mb_value = cls.mb_property(song)

        print(f"""({db_data["id"]}) {db_data["artist_name"]} - {db_data["title"]}""")
        print(f"""  DB: ({db_value}) {db_data["album_title"]} ({db_data["release_year"]})""")
        if mb_value:
            print(f"""  MB: ({song.album_mb_id}) {song.album_title} ({song.release_year}) [{song.song_mb_id}]""")
        print()

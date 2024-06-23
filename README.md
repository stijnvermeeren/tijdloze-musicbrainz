# tijdloze.rocks MusicBrainz dataset generation

## Background

The website [tijdloze.rocks](https://tijdloze.rocks) provides complete charts and statistics for _De Tijdloze_, an annual "best songs of all time" list from Belgian radio station Studio Brussel. When the chart was first aired in 1987, the list contained 100 songs. However, in recent years, the list has grown to over 2000 songs, with many new songs that need to be added to the database every year. This raises the need to automate the process of adding new songs to the database as much as possible.

Studio Brussel usually publishes the playlist of the chart in a plain text format that is similar to this:
```
...
3	Pink Floyd	Wish you were here
2	Fleetwood Mac	The chain
1	Pearl Jam	Black
```
However, in order to add such songs to the `tijdloze.rocks` database, more information is needed about every song, including:
- The album on which the song first appeared, including release year
- The nationality of the artist
- The Spotify identifier of the song

Initially, the admin interface for _tijdloze.rocks_ used the Spotify API to extract this data automatically, where possible. However, there is also an open music database called [MusicBrainz](https://musicbrainz.org/), with data that is much more complete and accurate. Moreover, once a song, album or artist is matched with the MusicBrainz database, it becomes much easier to retrieve additional data from other databases (e.g. [Wikidata](https://www.wikidata.org/)).

However, querying the relevant information from MusicBrainz is not a trivial task. While MusicBrainz does offer an [API](https://musicbrainz.org/doc/MusicBrainz_API), retrieving all the relevant data would require a large number of API calls, even for a single song. Replicating the full Musicbrainz database, and doing queries directly on that Postgres database, offer more flexibility, but requires a huge amount of disk space (ca. 100 GB), and still the queries can be complex and inefficient. The final solution is to do a significant amount of preprocessing on the MusicBrainz database, creating new tables in a structure that is optimized for the _tijdloze.rocks_ use case, and filled with only the relevant data. These new tables allow for efficient querying, while the total disk space required is only around 4 GB.  This repository contains all the code and instructions required to reproduce this "tijdloze.rocks MusicBrainz dataset".

### MusicBrainz database structure

The most relevant data types from the MusicBrainz database are artists, release groups, releases, recordings and works. As an example: 
- The _artist_ [Nirvana](https://musicbrainz.org/artist/5b11f4ce-a62d-471e-81fc-a69a8278c7da) has a _release group_ [Nevermind](https://musicbrainz.org/release-group/1b022e01-4da6-387b-8658-8678046e4cef).
- In the tijdloze.rocks database, the MusicBrainz _release group_ would correspond to an album. However, in the Musicbrainz database, a single release group can have many different releases, with each their own track listing (e.g. different bonus tracks, special editions, ...), format (CD, vinyl, ...), release date (different release dates in different countries, anniversary editions, ...), etc.
- A song such as [Smells Like Teen Spirit](https://musicbrainz.org/work/9840e142-269d-3fa3-9805-041a9235c18a) is a _work_ in the MusicBrainz database. Usually, there exist many different _recordings_ of a work (early demo version, album version, live recordings, covers by different artists). Often, a single recording can be identified as the "canonical recording" for that work, that is: the recording that you expect to be played on the radio when you request that song (e.g. [Smell Like Teen Spirit](https://musicbrainz.org/recording/5fb524f1-8cc8-4c04-a921-e34c0a911ea7)).
- In some rare cases, a single work might appear divided into several tracks on most releases of the canonical release group (e.g. [Shine On You Crazy Diamond](https://musicbrainz.org/work/c8f8379b-e755-3446-9fac-44c11b8c520f) on [Wish You Were Here](https://musicbrainz.org/release-group/1a272023-10d3-38ee-bab3-317b55fcc21d)). Conversely, sometimes a single recording might contain several works (e.g. TODO).
- Singles will also appear as their own _release group_ (e.g. [Smells Like Teen Spirit](https://musicbrainz.org/release-group/03345972-d2f8-36bb-b49a-03a9ceccb7a7)).

MusicBrainz also releases some ["canonical" data](https://musicbrainz.org/doc/Canonical_MusicBrainz_data), including for each recording a reference to "the most canonical version of that recording, often the version that appears on the first album where it was released." However, the way this "canonical data" is constructed is not very transparent, and we've found that there are too many cases where the chosen recording in this dataset does not match the requirements for our _tijdloze.rocks_ use case. 

### tijdloze.rocks MusicBrainz dataset generation

The dataset is generated as follows:
- Iterate over all artists that are either from Belgium, or have more than 8 URLs linked to them (other artists are ignored, as it is very unlikely that they will have an entry in any Tijdloze chart).
- Iterate over all official release groups that are credited to that artist, and establish which recordings have this release group as their "canonical" release group, taking into account considerations such as the following:
  - A song might have appeared as a single with a release year that is one year before the corresponding album release. However, we would still consider this song to have first appeared on the album, and not as a stand-alone single release (as we would do when the difference in release date is more than one year).
  - Similarly, compilation albums take a lower priority compared to studio albums, though it is still possible that a song was really first released on a compilation album (e.g. Nothing Really Ends on [No More Loud Music: The Singles](https://musicbrainz.org/release-group/80144342-6d1d-3acf-b721-426b672f30d7)).
  - When an explicit "single from" relation exists in the MusicBrainz database between two release groups (the single and the corresponding album), then this is a strong indication that this is the correct "canonical" relationship. However, some relevant songs were never released as a single, and even for those that were, the "single from" relation is now always present in the MusicBrainz database.
- For every recording that was encountered, export the id of the identified canonical release group, as well as all other relevant data, including a score (based on the number of released that this recording appears on) that can later be used to identify the most relevant recording matching a given query.

Later on, when the dataset is used for querying, such as e.g. in the [tijdloze.rocks API](https://github.com/stijnvermeeren/tijdloze-api), the following considerations should be taken into account:
- Artist and songs should also be found when misspelled or under alternative names.
- Only the more relevant matching recording should be considered, ignoring for example live recordings (unless the query explicitly states that we are looking for a live recording) or lesser known recordings (e.g. early demo versions) as identified using the score that is contained in the dataset. When several recordings are sufficiently relevant, then the one with the earliest release date should be returned.

## Instructions

### Replicate the Musicbrainz database

Create a replication of Musicbrainz database, following the instructions from the [musicbrainz-docker](https://github.com/metabrainz/musicbrainz-docker) repository.

We recommend executing these steps on a Virtual machine. For example, on AWS, you could launch a `t2.large` EC2 instance with Ubuntu Linux 24.04 with a 100 GB root volume (cost: ca. 0.12 USD per hour).

Below is a summary of the minimal required steps. More details and other options can be found in the README of the [musicbrainz-docker](https://github.com/metabrainz/musicbrainz-docker) repository. 

#### Install required software

Install the required dependencies from the `musicbrainz-docker`, plus Python and a PostgreSQL client (unless you want to generate the dataset from a different machine).

```bash
sudo apt-get update && \
sudo apt-get -y install docker.io docker-compose-v2 git postgresql-client-common postgresql-client-16 python3-pip python3-venv && \
sudo systemctl enable --now docker.service
```

Note: on Ubuntu 24.04, install `docker-compose-v2` (as in the command above) instead of `docker-compose` (as instructed in the official README). Also, execute all Docker Compose commands using `docker compose` instead of `docker-compose` (space instead of hyphen).

#### Clone the current repository and the musicbrainz-docker repository

```bash
git clone https://github.com/stijnvermeeren/tijdloze-musicbrainz
git clone https://github.com/metabrainz/musicbrainz-docker.git
cd musicbrainz-docker
```

#### Change configuration

Change configuration to "mirror database only":
```bash
admin/configure with alt-db-only-mirror
```

Optionally, give more memory to the database by creating a file `local/compose/memory-settings.yml` containing
```
version: '3.1'

# Description: Customize memory settings

services:
  db:
    command: postgres -c "shared_buffers=6GB" -c "shared_preload_libraries=pg_amqp.so"
```
and then running 
```
admin/configure add local/compose/memory-settings.yml
```
Make sure not to ask for more memory than what is available on the system, or the Postgres Docker container will fail to start. 

Publish the Postgres port in the Docker container by running:
```bash
admin/configure add publishing-db-port
```

#### (Optional) Open up the database to the internet

If you want to open up the Postgres database to the internet (e.g. you are setting up the database on an EC2 VM, but you want to access it using a database tool such as [DBeaver](https://dbeaver.io/) on your local laptop), then follow steps below.
- Set a strong password for the Postgres user by modifying the file `default/postgres.env`.
- When using EC2, change the "Security group" configuration for your EC2 instance on the AWS console, adding an inbound rule allowing traffic on the Postgres port (5432).

#### Build the Docker images

```bash
sudo docker compose build
```

This takes ca. 2 minutes.

#### Load the latest database dump

```bash
sudo docker compose run --rm musicbrainz createdb.sh -fetch
```

After executing this command, you will be asked to confirm whether you are planning to use the Musicbrainz dump for commercial purposes or not. After that, the loading of the database dump will take ca. 75 minutes (on the recommended EC2 instance).

### Create database schema for export

Navigate to the clone of this repository:
```
cd ../tijdloze-musicbrainz
```

Create a new schema `musicbrainz_export` in the database, by executing the commands from [sql/0_set_default_schema.sql](sql/0_set_default_schema.sql). 

```bash
psql -h localhost -U musicbrainz -d musicbrainz_db < sql/0_set_default_schema.sql 
```

Create a mapping from the more fine-grained Musicbrainz `area_id` values to the [ISO 3166-1 alpha-2](https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2) country codes used in the _tijdloze.rocks_ database, by executing the commands from [sql/1_area_id_country_id.sql](sql/1_area_id_country_id.sql).

```bash
psql -h localhost -U musicbrainz -d musicbrainz_db < sql/1_area_id_country_id.sql
```

Create the schema for the tables `mb_artist`, `mb_artist_alias`, `mb_album`, `mb_song` and `mb_song_alias` that will be exported to the _tijdloze.rocks_ database, by executing the commands from [sql/2_export_tables.sql](sql/2_export_tables.sql).

```bash
psql -h localhost -U musicbrainz -d musicbrainz_db < sql/2_export_tables.sql 
```

Fill the `mb_artist` and `mb_artist_alias` tables with data, by executing the commands from [sql/3_artist_data.sql](sql/3_artist_data.sql) and [sql/4_artist_alias_data.sql](sql/4_artist_alias_data.sql).

```bash
psql -h localhost -U musicbrainz -d musicbrainz_db < sql/3_artist_data.sql 
psql -h localhost -U musicbrainz -d musicbrainz_db < sql/4_artist_alias_data.sql 
```

### Run the script to compute the songs and albums

Run the Python script that fill the `mb_album` and `mb_song` tables with data.

Create a virtual environment and install the Python dependencies:
```bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

Create a file `.env` with the following contents, modifying the values where necessary:
```
MB_DB_HOST=localhost
MB_DB_NAME=musicbrainz_db
MB_DB_USER=musicbrainz
MB_DB_PASSWORD=musicbrainz
```

Execute the `main.py` script:
```bash
python src/main.py
```

Executing the script will take ca. 8 hours using the recommended EC2 instance. 

### Fill table `mb_song_alias`

Fill the `mb_song_alias` table with data, by executing the commands from [sql/5_song_alias_data.sql](sql/5_song_alias_data.sql).

```bash
psql -U musicbrainz -d musicbrainz_db < sql/5_song_alias_data.sql 
```

Executing the query will take ca. 12 minutes using the recommended EC2 instance.

### Dump the new tables

```bash
pg_dump -U musicbrainz -h ec2-....compute.amazonaws.com --format=c -t musicbrainz_export.mb_artist musicbrainz_db > mb_artist.dump
pg_dump -U musicbrainz -h ec2-....compute.amazonaws.com --format=c -t musicbrainz_export.mb_artist_alias musicbrainz_db > mb_artist_alias.dump
pg_dump -U musicbrainz -h ec2-....compute.amazonaws.com --format=c -t musicbrainz_export.mb_album musicbrainz_db > mb_artist.dump
pg_dump -U musicbrainz -h ec2-....compute.amazonaws.com --format=c -t musicbrainz_export.mb_song musicbrainz_db > mb_song.dump
pg_dump -U musicbrainz -h ec2-....compute.amazonaws.com --format=c -t musicbrainz_export.mb_song_alias musicbrainz_db > mb_song_alias.dump
```

## Query for creating tijdlozedb.csv dataset

```postgresql
SELECT
song.id, song.title,
album.id as "album_id", album.title as "album_title", album.release_year, album.musicbrainz_id,
artist.id as "artist_id", IFNULL(CONCAT(artist.name_prefix, " ", artist.name), artist.name) as "artist_name", artist.country_id as "artist_country_id", artist.musicbrainz_id as "artist_musicbrainz_id",
artist2.id as "artist2_id", IFNULL(CONCAT(artist2.name_prefix, " ", artist2.name), artist2.name) as "artist2_name", artist2.country_id as "artist2_country_id", artist2.musicbrainz_id as "artist2_musicbrainz_id"
FROM song
JOIN album ON album.id = song.album_id 
JOIN artist ON artist.id = song.artist_id
LEFT JOIN artist AS artist2 ON artist2.id = song.second_artist_id
```
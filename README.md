# tijdloze.rocks MusicBrainz dataset generation

TODO intro

## Steps

### Replicate the Musicbrainz database

Create a replication of Musicbrainz database, following the instructions from the [musicbrainz-docker](https://github.com/metabrainz/musicbrainz-docker) repository.

We recommend executing these steps on a Virtual machine. For example, on AWS, you could launch an Ubuntu Linux `t2.large` EC2 instance with a 100 GB root volume (cost: ca. 0.12 USD per hour).

Below is a summary of the minimal required steps. More details and other options can be found in the README of the [musicbrainz-docker](https://github.com/metabrainz/musicbrainz-docker) repository. 

#### Install required software

```
sudo apt-get update && \
sudo apt-get install docker.io docker-compose-v2 git && \
sudo systemctl enable --now docker.service
```

Note: on Ubuntu 24.04, install `docker-compose-v2` (as in the command above) instead of `docker-compose` (as instructed in the official README). Also, execute all Docker Compose commands using `docker compose` instead of `docker-compose` (space instead of hyphen).

#### Clone the repository

```
git clone https://github.com/metabrainz/musicbrainz-docker.git
cd musicbrainz-docker
```

#### Change configuration

Change configuration to "mirror database only":
```
admin/configure with alt-db-only-mirror
```

Give more memory to the database by creating a file `local/compose/memory-settings.yml` containing
```
```
and then running
```
version: '3.1'

# Description: Customize memory settings

services:
  db:
    command: postgres -c "shared_buffers=6GB" -c "shared_preload_libraries=pg_amqp.so"
```

#### (Optional) Open up the database to the internet

If you want to open up the Postgres database to the internet (e.g. you are setting up the database on an EC2 VM, but you want to access it using a database tool such as [DBeaver](https://dbeaver.io/) on your local laptop), then follow steps below.

Set a strong password for the Postgres user by modifying the file `default/postgres.env`.

Publish the Postgres port in the Docker container by running:
```
admin/configure add publishing-db-port
```

When using EC2, change the "Security group" configuration for your EC2 instance on the AWS console, adding an inbound rule allowing traffic on the Postgres port (5432).

#### Build the Docker images

```
sudo docker compose build
```

#### Load the latest database dump

```
sudo docker compose run --rm musicbrainz createdb.sh -fetch
```

After executing this command, you will be asked to confirm whether you are planning to use the Musicbrainz dump for commercial purposes or not. After that, the loading of the database dump will take another ca. 50 minutes (on the recommended EC2 instance).

### Create database schema for export

Create a new schema `musicbrainz_export` in the database, by executing the commands from [sql/0_set_default_schema.sql](sql/0_set_default_schema.sql). 

Create a mapping from the more fine-grained Musicbrainz `area_id` values to the [ISO 3166-1 alpha-2](https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2) country codes used in the _tijdloze.rocks_ database, by executing the commands from [sql/1_area_id_country_id.sql](sql/1_area_id_country_id.sql).

Create the schema for the tables `mb_artist`, `mb_artist_alias`, `mb_album`, `mb_song` and `mb_song_alias` that will be exported to the _tijdloze.rocks_ database, by executing the commands from [sql/2_export_tables.sql](sql/2_export_tables.sql).

Fill the `mb_artist` and `mb_artist_alias` tables with data, by executing the commands from [sql/3_artist_data.sql](sql/3_artist_data.sql) and [sql/4_artist_alias_data.sql](sql/4_artist_alias_data.sql).

### Run the script to compute the songs and albums

Run the Python script that fill the `mb_album` and `mb_song` tables with data.

Create a virtual environment and install the Python dependencies:
```
python3 -m venv env
source env/bin/activate
pip install requirements.txt
```

Create a file `.env` with the following contents, modifying the values where necessary:
```
MB_DB_HOST=localhost
MB_DB_NAME=musicbrainz_db
MB_DB_USER=musicbrainz
MB_DB_PASSWORD=musicbrainz
```

Execute the `main.py` script:
```
python scr/main.py
```

Executing the script will take ca. xx minutes using the recommended EC2 instance. 

### Fill table `mb_song_alias`

Fill the `mb_artist` and `mb_artist_alias` tables with data, by executing the commands from [sql/5_song_alias_data.sql](sql/5_song_alias_data.sql).


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
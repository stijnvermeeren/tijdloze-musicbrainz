
CREATE TABLE "musicbrainz_export"."tmp_area_country_id" (
  "area_id" integer,
  "country_id" varchar,
  PRIMARY KEY ("area_id")
);

INSERT INTO "musicbrainz_export"."tmp_area_country_id"
SELECT
    "area"."id" as "area_id",
    LOWER(COALESCE("iso_3166_1"."code", i1."code", i2."code", i3."code")) AS "county_id"
FROM "musicbrainz"."area"
         LEFT JOIN "iso_3166_1" ON "area"."id" = "iso_3166_1"."area"
         LEFT JOIN "l_area_area" AS l1 ON l1."link" = 118734 AND l1."entity1" = "area"."id"
         LEFT JOIN "iso_3166_1" AS i1 ON i1."area" = l1."entity0"
         LEFT JOIN "l_area_area" AS l2 ON l2."link" = 118734 AND l2."entity1" = "l1"."entity0"
         LEFT JOIN "iso_3166_1" AS i2 ON i2."area" = l2."entity0"
         LEFT JOIN "l_area_area" AS l3 ON l3."link" = 118734 AND l3."entity1" = "l2"."entity0"
         LEFT JOIN "iso_3166_1" AS i3 ON i3."area" = l3."entity0"
ON CONFLICT ("area_id") DO NOTHING;

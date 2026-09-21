#!/usr/bin/env bash
# The valley's past, into the warehouse — chapter 6.
#
# Every line here is in the codelab too; this just runs them in order and
# prints each one as it goes, so the terminal is the record. Safe to re-run:
# loads use --replace, the model and the embeddings use CREATE OR REPLACE.
#
#     bash scripts/season.sh
#
#   season/*.csv  →  gs://PROJECT-archive  →  BigQuery dataset `archive`
#   → a connection so BigQuery can call Vertex  →  an embedding model
#   → every ask embedded IN PLACE  →  one search by meaning, to prove it
#   → a property graph laid OVER the tables  →  one walk through it, to prove it
set -euo pipefail
cd "$(dirname "$0")/.."

P="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}"
[ -z "$P" ] && { echo "Set a project first: gcloud config set project YOUR_PROJECT_ID"; exit 1; }
B="gs://${P}-archive"
say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

say "1 · the season as five CSVs"
.venv/bin/python scripts/season_csv.py

say "2 · a bucket, and the files in it"
gcloud storage buckets create "$B" --location=US --project="$P" 2>/dev/null \
  || echo "    $B already exists"
gcloud storage cp season/*.csv "$B/"

say "3 · the dataset"
bq --project_id="$P" mk --location=US --dataset archive 2>/dev/null \
  || echo "    archive already exists"

say "4 · five tables, explicit schemas"
bq --project_id="$P" load --replace --source_format=CSV --skip_leading_rows=1 archive.visitors "$B/visitors.csv" id:STRING,name:STRING,species:STRING
bq --project_id="$P" load --replace --source_format=CSV --skip_leading_rows=1 archive.items    "$B/items.csv"    id:STRING,kind:STRING,mark:STRING
bq --project_id="$P" load --replace --source_format=CSV --skip_leading_rows=1 archive.asks     "$B/asks.csv"     id:STRING,visitor_id:STRING,item_id:STRING,day:STRING,season:STRING,said:STRING
bq --project_id="$P" load --replace --source_format=CSV --skip_leading_rows=1 archive.fixes    "$B/fixes.csv"    mark:STRING,what:STRING,found_by:STRING,day:STRING
bq --project_id="$P" load --replace --source_format=CSV --skip_leading_rows=1 archive.seasons  "$B/seasons.csv"  id:STRING,name:STRING,opened:STRING,closed:STRING

say "5 · prove the load"
bq --project_id="$P" query --use_legacy_sql=false "SELECT COUNT(*) AS asks FROM archive.asks"

say "6 · a connection, so BigQuery can call Vertex AI"
bq --project_id="$P" mk --connection --location=US --connection_type=CLOUD_RESOURCE vertex_conn 2>/dev/null \
  || echo "    US.vertex_conn already exists"
SA=$(bq --project_id="$P" show --format=json --connection US.vertex_conn \
     | python3 -c 'import json,sys; print(json.load(sys.stdin)["cloudResource"]["serviceAccountId"])')
echo "    connection service account: $SA"
gcloud projects add-iam-policy-binding "$P" --member="serviceAccount:$SA" \
  --role=roles/aiplatform.user --condition=None --quiet >/dev/null
echo "    granted roles/aiplatform.user"

say "7 · the embedding model — one statement, and it lives in the dataset"
bq --project_id="$P" query --use_legacy_sql=false \
  'CREATE OR REPLACE MODEL archive.embedder REMOTE WITH CONNECTION `US.vertex_conn` OPTIONS (ENDPOINT = "gemini-embedding-001")'

say "8 · every ask, embedded in place"
bq --project_id="$P" query --use_legacy_sql=false \
  'CREATE OR REPLACE TABLE archive.ask_embeddings AS
   SELECT id, content, ml_generate_embedding_result AS embedding
   FROM ML.GENERATE_EMBEDDING(MODEL archive.embedder, (SELECT id, said AS content FROM archive.asks))'
bq --project_id="$P" query --use_legacy_sql=false \
  "SELECT COUNT(*) AS n, ARRAY_LENGTH(ANY_VALUE(embedding)) AS dims FROM archive.ask_embeddings"

say "9 · one question by meaning — no shared words with what it finds"
bq --project_id="$P" query --use_legacy_sql=false '
SELECT base.id, base.content, ROUND(distance, 3) AS distance
FROM VECTOR_SEARCH(
  TABLE archive.ask_embeddings, "embedding",
  (SELECT ml_generate_embedding_result FROM ML.GENERATE_EMBEDDING(
     MODEL archive.embedder, (SELECT "the flame keeps dying on me once the sun is down" AS content))),
  top_k => 3)'

say "10 · the graph — laid over the tables, no rows moved"
bq --project_id="$P" query --use_legacy_sql=false \
  'CREATE OR REPLACE TABLE archive.marks AS SELECT DISTINCT mark FROM archive.items'
bq --project_id="$P" query --use_legacy_sql=false '
CREATE OR REPLACE PROPERTY GRAPH archive.season_graph
  NODE TABLES (
    archive.visitors AS Visitor KEY (id)   PROPERTIES (id, name, species),
    archive.items    AS Item    KEY (id)   PROPERTIES (id, kind, mark),
    archive.marks    AS Mark    KEY (mark) PROPERTIES (mark),
    archive.fixes    AS Fix     KEY (mark) PROPERTIES (mark, what, found_by, day))
  EDGE TABLES (
    archive.asks  AS asked   KEY (id)   SOURCE KEY (visitor_id) REFERENCES Visitor (id)
                                        DESTINATION KEY (item_id) REFERENCES Item (id)
                                        PROPERTIES (day, season, said),
    archive.items AS stamped KEY (id)   SOURCE KEY (id) REFERENCES Item (id)
                                        DESTINATION KEY (mark) REFERENCES Mark (mark),
    archive.fixes AS fixed   KEY (mark) SOURCE KEY (mark) REFERENCES Mark (mark)
                                        DESTINATION KEY (mark) REFERENCES Fix (mark))'

say "11 · one walk through it — a mark, everyone who came about it, and the cause"
bq --project_id="$P" query --use_legacy_sql=false '
SELECT * FROM GRAPH_TABLE(archive.season_graph
  MATCH (m:Mark)<-[:stamped]-(i:Item)<-[a:asked]-(v:Visitor)
  WHERE m.mark = "q7"
  OPTIONAL MATCH (m)-[:fixed]->(f:Fix)
  RETURN m.mark AS mark, COUNT(DISTINCT v.id) AS visitors, COUNT(DISTINCT a.said) AS things_said, ANY_VALUE(f.what) AS fix)'

say "done · floor four is open"
echo "    the app reads GOOGLE_CLOUD_PROJECT=$P from .env and looks for archive.ask_embeddings"

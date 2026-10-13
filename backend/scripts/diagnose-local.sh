#!/bin/bash
# Read-only Docker and runtime diagnostics. Does not restart/delete containers.
set -euo pipefail
cd "$(dirname "$0")/.."
docker info --format '{{.ServerVersion}}'
docker inspect cig-dynamodb-local --format 'State={{.State.Status}} Args={{json .Args}} Networks={{json .NetworkSettings.Networks}} Ports={{json .NetworkSettings.Ports}}'
docker network inspect cig-local --format '{{json .Containers}}'
if [[ ! -f local-env.json || ! -d .aws-sam/build/IntentsFunction ]]; then
  echo 'Need local-env.json and sam build output. See LOCAL_TESTING.md.' >&2
  exit 1
fi
image="${1:-}"
if [[ -z "$image" ]]; then
  echo 'Pass the locally cached Python 3.13 runtime image shown by docker image ls:' >&2
  docker image ls --format '{{.Repository}}:{{.Tag}}' | sed -n '/python3\.13\|lambda\/python:3\.13/p'
  exit 1
fi
docker image inspect "$image" --format '{{.Id}}'
docker run --rm --pull=never --network cig-local --entrypoint python \
  -v "$PWD:/workspace:ro" -w /workspace \
  -e CIG_SOURCE_DIR=/workspace/.aws-sam/build/IntentsFunction \
  "$image" scripts/local_db.py probe --env-file local-env.json
echo 'Runtime DNS/TCP/table probe passed. Next: invoke the actual SAM function to check SAM environment injection.'
sam local invoke IntentsFunction --template .aws-sam/build/template.yaml \
  --env-vars local-env.json --docker-network cig-local --skip-pull-image \
  --region ap-south-1 --event events/create-intent.json

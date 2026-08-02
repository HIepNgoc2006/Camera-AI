# Synthetic test fixtures

Only deterministic, reviewable fake data belongs here. Every data filename must contain
`.synthetic.` or `.sanitized.`. Every JSON file must contain the exact top-level field
`"_fixture": "SYNTHETIC_TEST_DATA_ONLY"`.

Allowed fixtures are small UTF-8 JSON/JSONL/YAML/TOML/CSV/TXT/SQL files. JSON fields ending in `_id`
must use fake values prefixed by `test_`, containing `_test_`, or ending in `_test`. Use reserved
`.invalid` domains if an email or URL is essential.

Never add names or profiles resembling real people, student/parent/staff data, face images,
embeddings, camera frames, base64 media, credentials, RTSP URLs, private media URLs, raw ANSVIS
exports, database dumps, backups, logs, datasets, model artifacts, or externally sourced examples.

ANSVIS fixtures must be minimal normalized contracts built manually from the approved schema. Do
not copy a raw payload from ANSVIS/AIBOX. `ansvis/event.synthetic.json` wraps one valid request under
the required synthetic marker; `ansvis/event-contract-cases.synthetic.json` contains only sanitized
contract mutations and expected stable outcomes. Its schema matrix includes every allowlisted V1
event type plus invalid schema, time-window, media/base64, authentication, idempotency and response
cases. `ansvis/timestamps.synthetic.json` is the
compatibility matrix for `time_policy_v1`; it contains fake instants only and no raw event body. Run
`python scripts/quality.py all` before review.

`web-bff-session/web-bff-session-policy-cases.synthetic.json` contains only synthetic state and
control canaries. It never contains a password, token, MFA value, cookie value, user, tenant, school,
session, endpoint, or production timeout. The checker rejects unsafe browser custody, cookie
downgrade, missing CSRF/origin checks, open redirects, token logging, client-authored authority,
refresh replay, and fail-open dependency behavior.

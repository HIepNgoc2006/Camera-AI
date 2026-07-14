# Fixture and seed-data safety

Fixture data is Low sensitivity only when it is intentionally synthetic, deterministic, and
contains no personal, biometric, evidence, credential, private-network, or production-derived
value. Real or externally sourced student, parent, staff, face, camera, ANSVIS, or school data is
prohibited in source control, CI, demos, screenshots, and test reports.

## Naming and location

Use `packages/test-fixtures/` for shared contracts. A future service may use
`services/<service>/tests/fixtures/`; a seed may use a scoped `seeds/` directory. Data filenames must
contain `.synthetic.` or `.sanitized.` and content must include `SYNTHETIC_TEST_DATA_ONLY`.

IDs must be visibly fake and deterministic, such as `school_test_0001`. Avoid realistic names,
birth dates, addresses, phone numbers, identity numbers, or profiles. If a contract truly needs an
email or URL, use an IANA-reserved `.invalid` domain and never include credentials or private hosts.

## Automated policy

`python scripts/quality.py fixtures` checks tracked fixture/seed paths. It rejects:

- files over 256 KiB, unsupported/binary/media types, unsafe names, or missing markers;
- password, secret, token, API/private-key fields and credentialed URLs;
- RTSP streams, base64 image/media fields, face embeddings, and embedded image data;
- realistic person-profile fields, non-`.invalid` email addresses/URLs, and private media URLs;
- invalid JSON fixtures.

The scanner reports only a stable category and file path. It never prints fixture content. The
runtime canary is generated in the operating-system temporary directory and prints only PASS/FAIL
plus its redaction status.

## Review and response

Review every fixture as data, not only as code. Confirm its origin is manual generation, its fields
are the minimum required by the contract, and no raw vendor/export payload was copied. A suspected
real value blocks the PR. Do not paste it into an issue or log; report path/category only and follow
the security incident process if the value was committed or pushed.

Rollback is a normal commit revert only when all fixture content is synthetic. If real personal,
biometric, evidence, or credential data entered Git history, stop delivery and escalate for access
blocking, credential rotation where relevant, history purge, and breach assessment.

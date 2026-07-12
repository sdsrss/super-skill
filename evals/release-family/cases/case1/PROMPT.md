# Task: make the repo push-safe (secret-scanning block)

Our org's secret scanner (and GitHub push protection) blocks any push whose
source contains a complete `sspk_live_<32 alphanumerics>` credential literal.
`tests/test_detect.py` hardcodes one as a fixture, so every push is rejected.

Fix the repo so that:

- no complete secret-shaped literal remains anywhere in the source, and
- the test suite stays green and still exercises real detection behaviour
  (the detector must still be tested against a full-shaped key at runtime).

Do not weaken `pkg/detect.py`. Work inside this directory.

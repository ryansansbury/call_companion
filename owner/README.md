# Owner steps

Everything here runs in a normal terminal from the build folder.
These steps need the network, a key, the audio tools, or Chrome.
The whole pipeline is three runs with a review between each.

| Run | Command | What it does | Time |
|---|---|---|---|
| 1 | `bash owner/run.sh 1` | Setup, the OpenAI key, the voice samples, and all twelve calls voiced with the provisional voices. Listen and read the scripts while it runs, then pick the voices, approve the scripts, and choose a local model from `ollama list` or "skip" | about 25 minutes |
| 2 | `bash owner/run.sh 2` | After the voices are set and the key is frozen. Lines whose voice or words changed are voiced again, then transcription, the check that every key fact lines up (it stops for a review if one doesn't), the aligned freeze, and the tuning round | about 20 minutes |
| 3 | `bash owner/run.sh 3` | After the prompts are frozen. Every model on every call, the local model if one is set, the real build, and the screenshots | about 30 minutes, or an hour with a local model |

The key is frozen after run 1, the aligned key during run 2 once every check passes, and the prompts after the tuning
round. The recorder refuses any model run until the first two are frozen and refuses the
test and deal runs until the third is.

Each run is safe to start again. Voiced lines and recorded AI steps are skipped.
The mix and its noise are seeded and the audio comes out the same every time.
The single steps inside the runs still work on their own for a partial rerun.

`bash owner/screenshots.sh --dev-preview` takes screenshots of the development preview for a first look at the
layout before the audio exists.

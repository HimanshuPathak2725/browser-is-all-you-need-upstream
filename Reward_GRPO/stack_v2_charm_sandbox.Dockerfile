FROM gcc:13@sha256:3617a214e52a25bde5375dc9503b5e67f01b6c7322a30137e2790aa8e6db5d1f
# Uses the repository's existing gcc:13 sandbox base. No task or reference
# files are installed in this image; each invocation receives only its scratch.
RUN g++ --version && command -v timeout

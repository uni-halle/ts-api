#!/bin/sh
set -e

# Compute Python user-site at runtime (silence errors if python missing)
SITE_DIR="$(python3 -m site --user-site 2>/dev/null || true)"

if [ -n "$SITE_DIR" ]; then
  # Avoid adding duplicates
  case ":$LD_LIBRARY_PATH:" in
    *:"$SITE_DIR":*)
      # already present
      ;;
    *)
      LD_LIBRARY_PATH="${LD_LIBRARY_PATH:+$LD_LIBRARY_PATH:}$SITE_DIR"
      export LD_LIBRARY_PATH
      ;;
  esac
fi

# Replace shell with the command so flask becomes PID 1 and receives signals
exec "$@"

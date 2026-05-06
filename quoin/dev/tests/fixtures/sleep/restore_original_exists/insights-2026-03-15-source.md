### Insight 1: hook timeout calibration

The 5-second timeout for userpromptsubmit.sh is sufficient for jq parsing but tight for slow filesystems. Observed on network-mounted drives where the hook occasionally exceeded 4.8 seconds.

**Promote?:** maybe
**Applies to:** /implement

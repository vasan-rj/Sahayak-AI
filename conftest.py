"""Pytest bootstrap.

Point the witness-log directory at an isolated temp dir BEFORE app.main imports
(the SessionRegistry reads SAHAYAK_LOG_DIR at construction time), so tests never
write into the repo's ./data tree.
"""

import os
import tempfile

os.environ.setdefault("SAHAYAK_LOG_DIR", tempfile.mkdtemp(prefix="sahayak-test-"))
os.environ.setdefault("SAHAYAK_TEMPLATE_DIR", tempfile.mkdtemp(prefix="sahayak-tmpl-"))

"""Server tests.

Runs must never reach the deployed Supabase project. `.env` carries
SUPABASE_PERSISTENCE=true for local demos, and importing the app would
otherwise write every fixture case into the real tables.
"""

import os

os.environ["SUPABASE_PERSISTENCE"] = "false"

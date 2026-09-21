# v3.1 Fix

The v3 build had a Flask session persistence bug: nested changes inside `state["data"]`
could be lost between HTTP requests because Flask's cookie session did not always mark
the session modified.

v3.1 deep-copies and reassigns state after every command/hint, and explicitly marks
the session modified.

Replace all files in the GitHub repository with this ZIP and redeploy.

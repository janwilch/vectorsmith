"""Authorize HTML (paste-secret form)."""

AUTHORIZE_PAGE = """<!doctype html>
<html><body>
<h1>VectorSmith</h1>
<p>Paste the access secret printed when you started <code>vectorsmith serve --http</code>.</p>
<form method="post">
  <input type="hidden" name="client_id" value="{client_id}">
  <input type="hidden" name="redirect_uri" value="{redirect_uri}">
  <input type="hidden" name="state" value="{state}">
  <input type="hidden" name="code_challenge" value="{code_challenge}">
  <label>Secret <input type="password" name="secret" autofocus></label>
  <button type="submit">Authorize</button>
</form>
</body></html>
"""

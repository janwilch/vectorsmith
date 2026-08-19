"""stdio_guard intercepts stray prints after the MCP transport claims stdout."""

from __future__ import annotations

import io
import sys
import warnings

from vectorsmith_cli.stdio_guard import install


def test_injected_print_goes_to_stderr() -> None:
    real_out, real_err = sys.stdout, sys.stderr
    err = io.StringIO()
    try:
        sys.stderr = err
        install()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            print("injected-print")
        assert "injected-print" in err.getvalue()
        assert any("stdout intercepted" in str(w.message) for w in caught)
    finally:
        sys.stdout = real_out
        sys.stderr = real_err

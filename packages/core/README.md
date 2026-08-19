# `vectorsmith_core` (unpublished)

Compiler, validators, and store adapters. This tree is a workspace package for development and import-linter; it is **not** published to PyPI.

`pip install vectorsmith` ships this module inside the `vectorsmith` wheel. Application code still uses:

```python
from vectorsmith import load_tools, connect
```

Authoring / CI can import `load_project` from `vectorsmith_core` after installing `vectorsmith`.

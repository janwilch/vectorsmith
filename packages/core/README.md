# vectorsmith-core

Compiler, validators, and store adapters for VectorSmith `tools.yaml` files.

Application code should depend on [`vectorsmith`](https://pypi.org/project/vectorsmith/), not this package directly, unless you are authoring or validating TDS files:

```python
from vectorsmith_core import load_project
```

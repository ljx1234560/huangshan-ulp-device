# Unit tests

Host-executable tests for hardware-independent application and protocol code belong here.

Run the portable VelaPet core tests from the repository root:

```powershell
.\scripts\test-unit.ps1
```

The script compiles with strict C11 warnings and writes generated output only
under the ignored `test-results/unit/` directory.


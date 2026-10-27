# Hardware-in-the-loop tests

Automated tests in this directory communicate with diagnostic firmware through an explicitly selected COM port. Tests must fail safely when the port is missing or ambiguous and must never flash a device implicitly.


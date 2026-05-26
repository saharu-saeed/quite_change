def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: live external calls (Bedrock LLM, EDINET, etc.); excluded from default sweep",
    )

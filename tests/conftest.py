from datasette.plugins import pm


def pytest_configure(config):
    # datasette-debug-gotham is a dev dependency for `just dev`; its seed hook
    # would add demo users to every test Datasette instance.
    plugin = pm.get_plugin("debug_gotham")
    if plugin:
        pm.unregister(plugin)
